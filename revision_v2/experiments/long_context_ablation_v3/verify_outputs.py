#!/usr/bin/env python3
"""Verify protocol invariants and completeness for long-context ablation v3."""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RV2 = os.path.abspath(os.path.join(HERE, "..", ".."))
RESULT_ROOT = os.path.join(RV2, "results", "long_context_ablation_v3")
BENCH_PATH = os.path.join(RV2, "data", "authguardbench_7702_v2.csv.gz")

sys.path.insert(0, os.path.join(RV2, "experiments", "common"))
from frozen import verify as verify_frozen  # noqa: E402

MODELS = (
    "flat_control_2048",
    "flat_control_16384",
    "chunk_attention_control_2048",
    "chunk_mean_control_16384",
    "chunk_attention_control_16384",
    "authguard_reference_16384",
)
SEEDS = (7702, 7703, 7704)
FOLDS = tuple(range(5))
METRICS = (
    "AUPRC", "AUROC", "Brier", "Recall_01", "FPR_01",
    "Recall_05", "FPR_05", "Recall_10", "FPR_10",
)


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--output-dir", default=RESULT_ROOT)
    args = parser.parse_args()
    output = os.path.abspath(args.output_dir)
    if args.smoke:
        output = os.path.join(output, "smoke")

    require(verify_frozen() == 0, "frozen-artifact verification failed")
    required_files = (
        "checkpoint.json", "metrics.csv", "predictions.csv.gz", "history.csv",
        "complexity.csv", "seed_summary.csv", "summary.csv", "capacity_audit.csv",
        "length_stratified_fold_metrics.csv",
    )
    for name in required_files:
        require(os.path.exists(os.path.join(output, name)), f"missing {name}")

    metrics = pd.read_csv(os.path.join(output, "metrics.csv"))
    predictions = pd.read_csv(os.path.join(output, "predictions.csv.gz"))
    complexity = pd.read_csv(os.path.join(output, "complexity.csv"))
    bench = pd.read_csv(BENCH_PATH)
    primary = bench[bench["population"] == "PRIMARY_EVALUATION"].reset_index(drop=True)

    expected_seeds = (SEEDS[0],) if args.smoke else SEEDS
    expected_folds = (FOLDS[0],) if args.smoke else FOLDS
    expected_units = {
        f"{model}:{seed}:{fold}"
        for model in MODELS
        for seed in expected_seeds
        for fold in expected_folds
    }
    require(set(metrics["unit_key"]) == expected_units, "metric unit set is incomplete")
    require(
        not metrics.duplicated(["unit_key", "condition"]).any(),
        "duplicate unit/condition metric row",
    )
    require(
        len(metrics) == 2 * len(expected_units),
        "each completed unit must have M0 and F200 metrics",
    )
    require(set(metrics["condition"]) == {"M0", "F200"}, "unexpected condition")
    require(set(metrics["model"]) == set(MODELS), "unexpected model set")

    for column in METRICS:
        require(np.isfinite(metrics[column]).all(), f"non-finite {column}")
        require(metrics[column].between(0, 1).all(), f"{column} outside [0,1]")
    require(
        (metrics["threshold_01"] >= metrics["threshold_05"]).all()
        and (metrics["threshold_05"] >= metrics["threshold_10"]).all(),
        "warning thresholds are not monotone",
    )

    require(
        not predictions.duplicated(["unit_key", "condition", "sid"]).any(),
        "duplicate per-row prediction",
    )
    require(set(predictions["unit_key"]) == expected_units, "prediction unit set incomplete")
    require(
        (predictions["retained_token_count"] > 0).all(),
        "empty retained representation",
    )
    require(
        (predictions["retained_token_count"] <= predictions["token_budget"]).all(),
        "an input bypassed its declared token cap",
    )
    capacity = pd.read_csv(os.path.join(output, "capacity_audit.csv"))
    require(
        (capacity["max_retained_token_count"] <= capacity["token_budget"]).all(),
        "capacity audit found a cap violation",
    )
    require(
        (predictions["condition_opcode_count"] > 0).all(),
        "invalid condition opcode count",
    )
    require(
        predictions["calibrated_score"].between(0, 1).all()
        and predictions["raw_score"].between(0, 1).all(),
        "prediction score outside [0,1]",
    )
    require(
        np.allclose(
            predictions.loc[predictions["condition"] == "M0",
                            "original_to_condition_ratio"],
            1.0,
        ),
        "clean token-count ratio is not one",
    )

    expected_test_rows = 8 if args.smoke else len(primary)
    expected_prediction_rows = (
        len(MODELS) * len(expected_seeds) * 2 * expected_test_rows
    )
    require(
        len(predictions) == expected_prediction_rows,
        f"expected {expected_prediction_rows} predictions, found {len(predictions)}",
    )
    if not args.smoke:
        for (model, seed, condition), group in predictions.groupby(
                ["model", "seed", "condition"]):
            require(
                set(group["sid"]) == set(primary["sample_id"]),
                f"incomplete held-out coverage: {model} seed={seed} {condition}",
            )

    param_counts = complexity.drop_duplicates("model").set_index("model")[
        "trainable_params"].to_dict()
    require(
        param_counts["flat_control_2048"] == param_counts["flat_control_16384"]
        == param_counts["chunk_mean_control_16384"],
        "flat and mean controls are not parameter matched",
    )
    require(
        param_counts["chunk_attention_control_2048"]
        == param_counts["chunk_attention_control_16384"]
        == param_counts["flat_control_2048"] + 65,
        "attention controls do not differ by exactly 65 parameters",
    )

    for fold in expected_folds:
        ledger_path = os.path.join(
            output, "data", f"f200_donor_ledger_fold{fold}.csv.gz")
        require(os.path.exists(ledger_path), f"missing fold-{fold} donor ledger")
        ledger = pd.read_csv(ledger_path)
        require(len(ledger) > 0, f"empty fold-{fold} donor ledger")
        require((ledger["condition"] == "F200").all(), "non-F200 donor ledger row")
        require(
            (ledger["recipient_partition"] == "test").all(),
            "F200 donor came from a non-test role",
        )
        require(
            (ledger["recipient_family"] != ledger["donor_family"]).all(),
            "recipient family reused as a donor",
        )

    model_dir = os.path.join(output, "models")
    checkpoints = [
        name for name in os.listdir(model_dir) if name.endswith(".pt")
    ]
    require(
        len(checkpoints) == len(expected_units),
        "model checkpoint count does not match completed units",
    )

    if not args.smoke:
        for name in (
            "family_bootstrap_contrasts.csv", "CONTRIBUTION_DECISION.md",
            "PAPER_RESULT_PACKET.md", "paper_tables_v3.tex",
            "length_stratified_summary.csv",
        ):
            require(os.path.exists(os.path.join(output, name)), f"missing {name}")
        bootstrap = pd.read_csv(
            os.path.join(output, "family_bootstrap_contrasts.csv"))
        require(len(bootstrap) == 6, "expected three contrasts under two conditions")
        require(
            np.isfinite(bootstrap[
                ["AUPRC_delta", "ci95_low", "ci95_high", "probability_positive"]
            ]).all().all()
            and (bootstrap["ci95_low"] <= bootstrap["ci95_high"]).all(),
            "invalid bootstrap contrast output",
        )

    print(
        "LONG_CONTEXT_ABLATION_V3_VERIFY_PASS "
        f"mode={'smoke' if args.smoke else 'full'} "
        f"units={len(expected_units)} predictions={len(predictions)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
