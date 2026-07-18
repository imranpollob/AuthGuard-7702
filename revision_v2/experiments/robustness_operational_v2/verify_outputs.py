#!/usr/bin/env python3
"""Fail-fast schema and completeness checks for the final robustness outputs."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
REQUIRED = [
    "ROBUSTNESS_EVALUATION_REPORT.md",
    "robustness_summary.csv",
    "robustness_fold_seed_results.csv",
    "robustness_predictions.csv.gz",
    "robustness_deltas.csv",
    "external_benign_control_results.csv",
    "qualitative_control_results.csv",
    "operational_latency_results.csv",
    "OPERATIONAL_EVALUATION_REPORT.md",
    "ROBUSTNESS_OPERATIONAL_FINAL_SUMMARY.md",
]


def main() -> None:
    missing = [name for name in REQUIRED if not (HERE / name).is_file()]
    assert not missing, f"missing required outputs: {missing}"

    folds = pd.read_csv(HERE / "robustness_fold_seed_results.csv")
    assert len(folds) == 3 * 3 * 3 * 5
    assert set(folds["model"]) == {"authguard_seq", "flat_cnn", "hist_ngram_xgb"}
    assert set(folds["condition"]) == {"M0", "F200", "M3+F200"}
    assert set(folds["seed"]) == {7702, 7703, 7704}
    assert set(folds["fold"]) == set(range(5))
    required_metrics = ["AUPRC", "AUROC", "Recall_01", "FPR_01", "Recall_05",
                        "FPR_05", "Recall_10", "FPR_10", "Brier"]
    assert folds[required_metrics].notna().all().all()

    predictions = pd.read_csv(HERE / "robustness_predictions.csv.gz")
    assert len(predictions) == 3 * 3 * 3 * 2190
    assert predictions["calibrated_score"].between(0, 1).all()
    assert predictions.groupby(["model", "condition", "seed"])["sample_id"].size().eq(2190).all()

    external = pd.read_csv(HERE / "external_benign_control_results.csv")
    assert len(external[external["seed"] != "mean_across_seed_means"]) == 15
    qualitative = pd.read_csv(HERE / "qualitative_control_results.csv")
    assert len(qualitative[qualitative["seed"] != "aggregate"]) == 75
    assert len(qualitative[qualitative["seed"] == "aggregate"]) == 5

    latency = pd.read_csv(HERE / "operational_latency_results.csv")
    assert set(latency["measurement"]) == {
        "full_local_screening_pipeline", "model_load", "model_forward_reference_baseline"
    }
    full = latency[latency["measurement"] == "full_local_screening_pipeline"].iloc[0]
    assert int(full["n_contracts"]) >= 300 and int(full["total_calls"]) >= 1500

    donor = json.load(open(HERE / "donor_isolation_audit.json"))
    reproduction = json.load(open(HERE / "baseline_reproduction_check.json"))
    assert donor["status"] == "PASS"
    assert reproduction["status"] in {"PASS", "PASS_WITH_EXPECTED_GPU_VARIANCE"}
    assert reproduction["xgboost_exact_reproduction"]
    assert reproduction["ranking_preserved"]

    summary = pd.read_csv(HERE / "robustness_summary.csv")
    for condition in ("M0", "F200", "M3+F200"):
        ranked = summary[summary["condition"] == condition].sort_values(
            "AUPRC_mean", ascending=False)
        assert ranked.iloc[0]["model"] == "authguard_seq"

    print("robustness_operational_v2 outputs: PASS")


if __name__ == "__main__":
    main()
