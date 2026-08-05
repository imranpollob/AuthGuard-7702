from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from revision_v3.experiments.human_label_evaluation.freeze_postcutoff_decision_contract import (
    MODEL_COLUMNS,
    build_consensus_decisions,
    consensus_decision,
)
from revision_v3.experiments.human_label_evaluation.evaluate_frozen_postcutoff_decisions import (
    _wilson_interval,
    evaluate_decisions,
)


ROOT = Path(__file__).resolve().parents[2]


def test_consensus_rule_warns_defers_and_never_calls_partial_no_warning():
    assert consensus_decision([True, True, False], coverage="PARTIAL", authority_available=False) == "WARN"
    assert consensus_decision([True, False, False], coverage="COMPLETE", authority_available=True) == "DEFER"
    assert consensus_decision([False, False, False], coverage="PARTIAL", authority_available=True) == "DEFER"
    assert consensus_decision([False, False, False], coverage="COMPLETE", authority_available=False) == "DEFER"
    assert consensus_decision([False, False, False], coverage="COMPLETE", authority_available=True) == "NO_MODEL_WARNING"


def test_consensus_rule_requires_exactly_three_seeds():
    with pytest.raises(ValueError, match="exactly three"):
        consensus_decision([False, False], coverage="COMPLETE", authority_available=True)


def test_decision_builder_is_label_free_and_uses_frozen_exclusion():
    manifest_rows = [
        {"item_id": f"i{index:03d}", "authority_address": "0xabc"} for index in range(150)
    ]
    prediction_rows = []
    for item in manifest_rows[1:]:
        for seed in (7702, 7703, 7704):
            row = {"sample_id": item["item_id"], "seed": seed, "coverage": "COMPLETE"}
            for score_column, threshold_column in MODEL_COLUMNS.values():
                row[score_column] = 0.1
                row[threshold_column] = 0.5
            prediction_rows.append(row)
    decisions = build_consensus_decisions(
        pd.DataFrame(prediction_rows), pd.DataFrame(manifest_rows), {"i000"}
    )
    assert decisions["sample_id"].nunique() == 149
    assert len(decisions) == 149 * len(MODEL_COLUMNS)
    assert set(decisions["consensus_decision"]) == {"NO_MODEL_WARNING"}
    assert not any("label" in column for column in decisions.columns)


def test_wilson_interval_handles_boundaries_and_empty_denominator():
    assert _wilson_interval(0, 0) is None
    zero = _wilson_interval(0, 10)
    full = _wilson_interval(10, 10)
    assert zero is not None and zero[0] == 0.0 and 0.0 < zero[1] < 0.5
    assert full is not None and 0.5 < full[0] < 1.0 and full[1] == pytest.approx(1.0)


def test_frozen_decision_evaluator_accepts_only_complete_bound_human_release(tmp_path):
    manifest_path = ROOT / "revision_v3/results/postcutoff_snapshot/postcutoff_review_manifest.csv"
    hold_plan_path = ROOT / "revision_v3/results/postcutoff_snapshot/postcutoff_family_holdout_plan.json"
    decisions_path = ROOT / "revision_v3/results/postcutoff_retraining/postcutoff_consensus_decisions.csv.gz"
    lock_path = ROOT / "revision_v3/results/postcutoff_retraining/postcutoff_decision_contract_lock.json"
    item_ids = pd.read_csv(manifest_path, usecols=["item_id"])["item_id"].astype(str).tolist()
    release = [
        {
            "item_id": item_id,
            "final_label": (
                "UNSAFE" if index % 2 else "NO_CONCRETE_UNSAFE_BEHAVIOR_FOUND"
            ),
            "n_primary_reviews": 2,
            "resolution": "unanimous",
        }
        for index, item_id in enumerate(item_ids)
    ]
    release_path = tmp_path / "synthetic_release.json"
    release_path.write_text(json.dumps(release))
    agreement = {
        "status": "COMPLETE_DUAL_REVIEW_AND_ADJUDICATION",
        "sample_set": "postcutoff",
        "item_ids_sha256": hashlib.sha256(
            "\n".join(sorted(item_ids)).encode()
        ).hexdigest(),
        "n_manifest_items": 150,
        "n_exactly_dual_reviewed": 150,
        "n_pending_adjudications": 0,
        "n_primary_disagreements": 0,
        "n_adjudicated_disagreements": 0,
        "raw_agreement_rate": 1.0,
        "cohens_kappa": 1.0,
    }
    agreement_path = tmp_path / "synthetic_agreement.json"
    agreement_path.write_text(json.dumps(agreement))
    report = evaluate_decisions(
        release_path=release_path,
        agreement_path=agreement_path,
        manifest_path=manifest_path,
        hold_plan_path=hold_plan_path,
        decisions_path=decisions_path,
        lock_path=lock_path,
    )
    assert report["n_scored_items"] == 149
    assert report["n_binary_scored_items"] == 149
    assert set(report["models"]) == set(MODEL_COLUMNS)
    assert all(
        model_report["warning_recall_wilson_95ci"] is not None
        for model_report in report["models"].values()
    )
