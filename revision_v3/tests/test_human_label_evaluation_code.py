"""Unit tests for the Part 10 evaluation code, using SYNTHETIC data only -- these tests prove
the metric functions are correct; they are not, and must never be mistaken for, a real
human-label evaluation result. No file under revision_v3/reports/ should ever cite numbers
from this test file.
"""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "experiments", "human_label_evaluation"))
from evaluate_against_human_labels import (  # noqa: E402
    binary_rule_metrics,
    continuous_score_metrics,
    evaluate_dcrg_ablation_predictions,
    evaluate_dcrg_predictions,
    expected_calibration_error,
    load_human_reference,
    run_evaluation,
    validate_agreement_report,
    validate_review_protocol,
)
from analysis.dcrg_feature_groups import FEATURE_GROUPS  # noqa: E402


def test_binary_rule_metrics_perfect_predictor():
    y_true = np.array([1, 1, 0, 0])
    y_pred = np.array([1, 1, 0, 0])
    m = binary_rule_metrics(y_true, y_pred)
    assert m["precision"] == 1.0
    assert m["recall"] == 1.0
    assert m["specificity"] == 1.0
    assert m["fpr"] == 0.0
    assert m["f1"] == 1.0
    assert m["balanced_accuracy"] == 1.0


def test_binary_rule_metrics_all_wrong():
    y_true = np.array([1, 1, 0, 0])
    y_pred = np.array([0, 0, 1, 1])
    m = binary_rule_metrics(y_true, y_pred)
    assert m["recall"] == 0.0
    assert m["specificity"] == 0.0
    assert m["balanced_accuracy"] == 0.0


def test_expected_calibration_error_perfect_calibration():
    rng = np.random.default_rng(0)
    scores = rng.uniform(0, 1, 2000)
    y_true = (rng.uniform(0, 1, 2000) < scores).astype(int)  # scores ARE the true probabilities
    ece = expected_calibration_error(y_true, scores, n_bins=10)
    assert ece < 0.05  # should be well-calibrated by construction


def test_continuous_score_metrics_runs():
    rng = np.random.default_rng(0)
    y_true = rng.integers(0, 2, 200)
    scores = rng.uniform(0, 1, 200)
    m = continuous_score_metrics(y_true, scores, threshold=0.5)
    assert "auprc" in m and "auroc" in m and "brier" in m


def test_load_human_reference_raises_on_empty_release():
    import json
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump([], f)
        path = f.name
    try:
        with pytest.raises(ValueError):
            load_human_reference(path)
    finally:
        os.unlink(path)


def test_load_human_reference_requires_exact_complete_manifest(tmp_path):
    import json

    path = tmp_path / "release.json"
    path.write_text(json.dumps([
        {"item_id": "a", "final_label": "NO_CONCRETE_UNSAFE_BEHAVIOR_FOUND"},
        {"item_id": "b", "final_label": None},
    ]))
    with pytest.raises(ValueError, match="unresolved"):
        load_human_reference(
            str(path), expected_item_ids=["a", "b"], require_complete=True
        )
    with pytest.raises(ValueError, match="exactly match"):
        load_human_reference(
            str(path), expected_item_ids=["a", "b", "c"], require_complete=False
        )


def test_load_human_reference_rejects_unknown_label(tmp_path):
    import json

    path = tmp_path / "release.json"
    path.write_text(json.dumps([{"item_id": "a", "final_label": "PROBABLY_SAFE"}]))
    with pytest.raises(ValueError, match="unknown final labels"):
        load_human_reference(str(path))


def test_gold_test_requires_dual_review_and_adjudication_resolution():
    incomplete = pd.DataFrame({
        "item_id": ["a"],
        "final_label": ["NO_CONCRETE_UNSAFE_BEHAVIOR_FOUND"],
        "n_primary_reviews": [1],
        "resolution": ["single_review"],
    })
    with pytest.raises(ValueError, match="dual-review"):
        validate_review_protocol(incomplete, "gold_test")

    complete = incomplete.assign(n_primary_reviews=2, resolution="unanimous")
    validate_review_protocol(complete, "gold_test")


def test_postcutoff_evaluation_checks_scoring_provenance_before_human_labels(tmp_path):
    import json

    manifest = tmp_path / "manifest.csv"
    release = tmp_path / "release.json"
    manifest.write_text("item_id\na\n")
    release.write_text(json.dumps([]))
    with pytest.raises(ValueError, match="locked scoring provenance"):
        run_evaluation(
            str(release),
            "postcutoff",
            str(manifest),
            str(tmp_path / "missing_predictions.csv"),
            bootstrap_replicates=10,
        )


def test_agreement_report_is_bound_to_manifest_and_complete(tmp_path):
    import hashlib
    import json

    ids = ["a", "b"]
    report_path = tmp_path / "agreement.json"
    report_path.write_text(json.dumps({
        "status": "COMPLETE_DUAL_REVIEW_AND_ADJUDICATION",
        "sample_set": "gold_test",
        "item_ids_sha256": hashlib.sha256("a\nb".encode()).hexdigest(),
        "n_manifest_items": 2,
        "n_exactly_dual_reviewed": 2,
        "n_pending_adjudications": 0,
        "n_primary_disagreements": 1,
        "n_adjudicated_disagreements": 1,
    }))
    report = validate_agreement_report(
        str(report_path), expected_item_ids=ids, sample_set="gold_test"
    )
    assert report["agreement_report_sha256"]

    payload = json.loads(report_path.read_text())
    payload["n_pending_adjudications"] = 1
    report_path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="pending adjudications"):
        validate_agreement_report(
            str(report_path), expected_item_ids=ids, sample_set="gold_test"
        )


def test_human_dcrg_evaluation_uses_item_specific_thresholds_and_all_seeds():
    human = pd.DataFrame({
        "item_id": ["a", "b", "c", "d"],
        "final_label": [
            "NO_CONCRETE_UNSAFE_BEHAVIOR_FOUND",
            "NO_CONCRETE_UNSAFE_BEHAVIOR_FOUND",
            "UNSAFE",
            "UNSAFE",
        ],
        "binary_label": [0, 0, 1, 1],
        "excluded_from_binary": [False] * 4,
    })
    rows = []
    for seed in (7702, 7703):
        for sample_id, family_id, label, sequence, dcrg, fusion, threshold, coverage in (
            ("a", "F1", 0, 0.10, 0.05, 0.15, 0.20, "COMPLETE"),
            ("b", "F2", 0, 0.80, 0.10, 0.82, 0.90, "PARTIAL"),
            ("c", "F3", 1, 0.40, 0.95, 0.97, 0.50, "COMPLETE"),
            ("d", "F4", 1, 0.30, 0.85, 0.90, 0.50, "PARTIAL"),
        ):
            rows.append({
                "seed": seed,
                "sample_id": sample_id,
                "family_id": family_id,
                "coverage": coverage,
                "sequence_score": sequence,
                "hist_ngram_xgb_score": sequence,
                "dcrg_score": dcrg,
                "dcrg_project_balanced_score": dcrg,
                "fusion_score": fusion,
                "sequence_threshold_5pct": threshold,
                "hist_ngram_xgb_threshold_5pct": threshold,
                "dcrg_threshold_5pct": threshold,
                "dcrg_project_balanced_threshold_5pct": threshold,
                "fusion_threshold_5pct": threshold,
                "label": label,
            })
    report = evaluate_dcrg_predictions(
        human, pd.DataFrame(rows), bootstrap_replicates=100
    )
    assert report["models"]["sequence"]["mean_across_seeds"]["observed_fpr"] == 0.0
    assert report["models"]["dcrg"]["mean_across_seeds"]["recall"] == 1.0
    policy = report["coverage_aware_selective_policy"]["mean_across_seeds"]
    assert policy["n_unsafe_within_low_observed_risk"] == 0.0
    assert len(report["paired_family_bootstrap"]) == 5
    assert report["models"]["hist_ngram_xgb"]["mean_across_seeds"]["observed_fpr"] == 0.0


def _synthetic_ablation_predictions() -> pd.DataFrame:
    rows = []
    scores = {
        "cfg_capability_only": [0.20, 0.80, 0.30, 0.70],
        "dcrg_untyped_guards": [0.10, 0.60, 0.70, 0.80],
        "dcrg_without_protocol_actors": [0.10, 0.40, 0.80, 0.90],
        "dcrg_full": [0.05, 0.10, 0.90, 0.95],
    }
    for seed in (7702, 7703):
        for model in FEATURE_GROUPS:
            for index, (sample_id, family_id) in enumerate(
                (("a", "F1"), ("b", "F2"), ("c", "F3"), ("d", "F4"))
            ):
                rows.append({
                    "seed": seed,
                    "sample_id": sample_id,
                    "family_id": family_id,
                    "model": model,
                    "score": scores[model][index],
                    "threshold_5pct": 0.5,
                })
    return pd.DataFrame(rows)


def _synthetic_human_binary() -> pd.DataFrame:
    return pd.DataFrame({
        "item_id": ["a", "b", "c", "d"],
        "binary_label": [0, 0, 1, 1],
        "excluded_from_binary": [False] * 4,
    })


def test_human_dcrg_ablation_evaluates_every_predeclared_group():
    report = evaluate_dcrg_ablation_predictions(
        _synthetic_human_binary(),
        _synthetic_ablation_predictions(),
        bootstrap_replicates=100,
    )
    assert set(report["models"]) == set(FEATURE_GROUPS)
    assert len(report["paired_family_bootstrap"]) == len(FEATURE_GROUPS) - 1
    assert all(
        comparison["candidate"] == "dcrg_full"
        for comparison in report["paired_family_bootstrap"]
    )
    assert report["models"]["dcrg_full"]["mean_across_seeds"]["auprc"] == 1.0


def test_human_dcrg_ablation_rejects_missing_model_or_item_coverage():
    predictions = _synthetic_ablation_predictions()
    missing_model = predictions[predictions["model"] != "cfg_capability_only"]
    with pytest.raises(ValueError, match="ablation model coverage mismatch"):
        evaluate_dcrg_ablation_predictions(
            _synthetic_human_binary(), missing_model, bootstrap_replicates=10
        )

    missing_item = predictions[~(
        (predictions["model"] == "dcrg_full")
        & (predictions["seed"] == 7702)
        & (predictions["sample_id"] == "a")
    )]
    with pytest.raises(ValueError, match="ablation coverage mismatch"):
        evaluate_dcrg_ablation_predictions(
            _synthetic_human_binary(), missing_item, bootstrap_replicates=10
        )
