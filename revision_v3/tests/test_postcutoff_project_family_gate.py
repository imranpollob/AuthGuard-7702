from __future__ import annotations

import pandas as pd
import pytest

from revision_v3.experiments.temporal_v2.validate_postcutoff_project_families import (
    build_audit_template,
    summarize_project_family_audit_progress,
    validate_project_family_audit,
)


def _manifest():
    return pd.DataFrame([
        {"item_id": "ethereum:0x01", "family_id": "T0001"},
        {"item_id": "ethereum:0x02", "family_id": "T0002"},
    ])


def test_unresolved_template_fails_closed():
    audit = build_audit_template(_manifest())
    with pytest.raises(ValueError, match="UNRESOLVED"):
        validate_project_family_audit(_manifest(), audit, {"F00001"})


def test_confirmed_project_family_materializes_union_of_training_holds():
    audit = build_audit_template(_manifest())
    audit["postcutoff_project_family_id"] = "PF_ZERODEV"
    audit["provenance_status"] = "CONFIRMED"
    audit["evidence_reference"] = ["https://example.org/a", "https://example.org/b"]
    audit["auditor_id"] = "A1"
    audit["related_canonical_family_ids"] = ["F00001", "F00002"]
    report = validate_project_family_audit(_manifest(), audit, {"F00001", "F00002"})
    hold = report["project_family_holds"]["PF_ZERODEV"]
    assert report["status"] == "READY_FOR_PROJECT_FAMILY_RETRAINING_HOLDS"
    assert hold["canonical_family_ids_to_hold_out"] == ["F00001", "F00002"]
    assert hold["item_ids"] == ["ethereum:0x01", "ethereum:0x02"]


def test_unknown_canonical_family_is_rejected():
    audit = build_audit_template(_manifest())
    audit["postcutoff_project_family_id"] = "PF_X"
    audit["provenance_status"] = "CONFIRMED"
    audit["evidence_reference"] = "dossier:x"
    audit["auditor_id"] = "A1"
    audit["related_canonical_family_ids"] = "F99999"
    with pytest.raises(ValueError, match="unknown canonical family"):
        validate_project_family_audit(_manifest(), audit, {"F00001"})


def test_progress_report_accepts_unresolved_but_does_not_call_it_complete():
    audit = build_audit_template(_manifest())
    audit.loc[0, [
        "postcutoff_project_family_id", "provenance_status", "evidence_reference", "auditor_id"
    ]] = ["PF_ONE", "CONFIRMED", "https://example.org/evidence", "A1"]
    report = summarize_project_family_audit_progress(_manifest(), audit, {"F00001"})
    assert report["status"] == "INCOMPLETE_PROJECT_FAMILY_AUDIT"
    assert report["status_counts"] == {"CONFIRMED": 1, "UNRESOLVED": 1}


def test_progress_report_rejects_invalid_terminal_row():
    audit = build_audit_template(_manifest())
    audit.loc[0, "provenance_status"] = "EXCLUDED"
    with pytest.raises(ValueError, match="requires auditor_id"):
        summarize_project_family_audit_progress(_manifest(), audit, {"F00001"})


def test_conservative_cluster_is_terminal_without_claiming_brand_ownership():
    audit = build_audit_template(_manifest())
    audit["postcutoff_project_family_id"] = ["PF_ANON_A", "PF_ANON_B"]
    audit["provenance_status"] = "CONSERVATIVE_CLUSTER"
    audit["evidence_reference"] = ["artifact:a", "artifact:b"]
    audit["evidence_notes"] = (
        "NO_BRAND_OWNERSHIP_CLAIM; conservative signer and deployer linkage only"
    )
    audit["auditor_id"] = "PIPELINE_V1"
    report = validate_project_family_audit(_manifest(), audit, {"F00001"})
    assert report["status"] == "READY_FOR_PROJECT_FAMILY_RETRAINING_HOLDS"
    assert report["n_confirmed_items"] == 0
    assert report["n_conservative_cluster_items"] == 2


def test_conservative_cluster_must_disclose_no_brand_claim():
    audit = build_audit_template(_manifest())
    audit["postcutoff_project_family_id"] = "PF_ANON"
    audit["provenance_status"] = "CONSERVATIVE_CLUSTER"
    audit["evidence_reference"] = "artifact:x"
    audit["evidence_notes"] = "looks related"
    audit["auditor_id"] = "PIPELINE_V1"
    with pytest.raises(ValueError, match="NO_BRAND_OWNERSHIP_CLAIM"):
        validate_project_family_audit(_manifest(), audit, {"F00001"})
