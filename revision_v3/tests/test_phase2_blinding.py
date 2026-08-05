"""Tests for model-score and source-label blinding in the evidence-packet / annotation
pipeline, and for legitimate-control provenance fields (Parts 5, 6, 9)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from evidence.packet_builder import FORBIDDEN_FIELDS, build_evidence_packet
from revision_v3.annotation_app.seed_from_packets import _validate_primary_pair


def test_forbidden_fields_list_covers_scores_and_labels():
    expected = {"label", "authguard_score", "authguard_prediction", "raw_score",
                "calibrated_score", "reviewer_judgment"}
    assert expected.issubset(FORBIDDEN_FIELDS)


def test_evidence_packet_builder_rejects_label_field():
    row = {"sample_id": "x", "chain": "ethereum", "address": "0x0", "runtime_bytecode": "00",
           "label": 1}
    with pytest.raises(ValueError):
        build_evidence_packet(row)


def test_evidence_packet_builder_rejects_model_score_field():
    row = {"sample_id": "x", "chain": "ethereum", "address": "0x0", "runtime_bytecode": "00",
           "calibrated_score": 0.9}
    with pytest.raises(ValueError):
        build_evidence_packet(row)


def test_evidence_packet_contains_no_score_or_label_keys():
    row = {"sample_id": "x", "chain": "ethereum", "address": "0x0", "runtime_bytecode": "6000"}
    packet = build_evidence_packet(row)
    packet_keys_lower = {k.lower() for k in packet.keys()}
    assert not (FORBIDDEN_FIELDS & packet_keys_lower)


def test_evidence_packet_accepts_neutral_authorization_provenance():
    packet = build_evidence_packet({
        "sample_id": "postcutoff:x",
        "chain": "ethereum",
        "address": "0x" + "11" * 20,
        "runtime_bytecode": "6000",
        "authority_address": "0x" + "22" * 20,
        "authorization_count": "7",
        "first_block": "123",
        "first_tx_hash": "0x" + "33" * 32,
        "runtime_changed_since_first_authorization": False,
    })
    context = packet["authorization_history"]
    assert context["status"] == "AVAILABLE_FROM_FROZEN_COLLECTOR"
    assert context["authorizing_eoa"] == "0x" + "22" * 20
    assert context["observed_authorization_count"] == 7
    assert context["runtime_changed_since_first_observation"] is False
    assert "score" not in context

    packet_from_csv = build_evidence_packet({
        "sample_id": "postcutoff:y",
        "chain": "ethereum",
        "address": "0x" + "11" * 20,
        "runtime_bytecode": "6000",
        "authority_address": "0x" + "22" * 20,
        "runtime_changed_since_first_authorization": "False",
    })
    assert packet_from_csv["authorization_history"][
        "runtime_changed_since_first_observation"
    ] is False


def test_dual_review_seeding_requires_two_distinct_reviewer_ids():
    assert _validate_primary_pair([" R1 ", "R2"]) == ["R1", "R2"]
    with pytest.raises(ValueError, match="two distinct"):
        _validate_primary_pair(["R1", "R1"])


def test_legitimate_candidates_have_required_provenance_fields():
    path = os.path.join(os.path.dirname(__file__), "..", "external_controls",
                        "legitimate_candidates_all_deployments.csv")
    if not os.path.exists(path):
        pytest.skip("legitimate_candidates_all_deployments.csv not generated in this environment")
    import pandas as pd
    df = pd.read_csv(path)
    required = {"project", "chain", "address", "runtime_bytecode_sha256", "documentation_url",
                "audit_evidence", "evidence_of_actual_eip7702_use", "deployment_date"}
    assert required.issubset(set(df.columns))
    assert df["documentation_url"].notna().all()
