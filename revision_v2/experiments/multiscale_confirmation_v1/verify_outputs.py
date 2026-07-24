#!/usr/bin/env python3
"""Verify AuthGuard-MSP confirmatory outputs and fold isolation."""
from __future__ import annotations

import argparse
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RV2 = os.path.abspath(os.path.join(HERE, "..", ".."))
DEFAULT_OUT = os.path.join(RV2, "results", "multiscale_confirmation_v1")
MODEL = "authguard_msp_16384"
SEEDS = (7702, 7703, 7704)
FOLDS = (1, 2, 3, 4)


def require(value, message):
    if not value:
        raise AssertionError(message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=DEFAULT_OUT)
    args = parser.parse_args()
    output = os.path.abspath(args.output_dir)
    required = (
        "metrics.csv", "predictions.csv.gz", "history.csv", "complexity.csv",
        "checkpoint.json", "seed_summary.csv", "summary.csv",
        "confirmation_bootstrap.csv", "CONFIRMATION_DECISION.md",
    )
    for name in required:
        require(os.path.exists(os.path.join(output, name)), f"missing {name}")

    metrics = pd.read_csv(os.path.join(output, "metrics.csv"))
    predictions = pd.read_csv(os.path.join(output, "predictions.csv.gz"))
    expected_units = {
        f"{MODEL}:{seed}:{fold}" for seed in SEEDS for fold in FOLDS
    }
    require(set(metrics["unit_key"]) == expected_units, "incomplete metric units")
    require(set(predictions["unit_key"]) == expected_units, "incomplete prediction units")
    require(set(metrics["fold"]) == set(FOLDS), "development fold leaked into metrics")
    require(set(predictions["fold"]) == set(FOLDS), "development fold leaked into predictions")
    require(len(metrics) == 24, "expected clean and F200 metrics for 12 units")
    require(
        not predictions.duplicated(["unit_key", "condition", "sid"]).any(),
        "duplicate prediction",
    )
    require(
        (predictions["retained_token_count"] <= 16_384).all(),
        "token cap violation",
    )
    require(
        predictions["calibrated_score"].between(0, 1).all(),
        "invalid calibrated score",
    )
    expected_per_seed_condition = 2_190 - 446
    require(
        len(predictions) == len(SEEDS) * 2 * expected_per_seed_condition,
        "incorrect confirmatory prediction count",
    )
    checkpoints = [
        name for name in os.listdir(os.path.join(output, "models"))
        if name.endswith(".pt")
    ]
    require(len(checkpoints) == 12, "incorrect model-checkpoint count")
    bootstrap = pd.read_csv(os.path.join(output, "confirmation_bootstrap.csv"))
    require(len(bootstrap) == 12, "expected 12 predeclared contrast rows")
    require(
        np.isfinite(bootstrap[
            ["delta", "ci95_low", "ci95_high", "probability_positive"]
        ]).all().all(),
        "non-finite bootstrap result",
    )
    require(
        (bootstrap["ci95_low"] <= bootstrap["ci95_high"]).all(),
        "invalid bootstrap interval",
    )
    print(
        "MULTISCALE_CONFIRMATION_V1_VERIFY_PASS "
        f"units={len(expected_units)} predictions={len(predictions)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

