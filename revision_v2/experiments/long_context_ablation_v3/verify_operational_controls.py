#!/usr/bin/env python3
"""Verify promoted-model external controls and latency outputs."""
from __future__ import annotations

import argparse
import json
import os

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RV2 = os.path.abspath(os.path.join(HERE, "..", ".."))
DEFAULT_OUT = os.path.join(
    RV2, "results", "long_context_ablation_v3", "operational_controls")


def require(value, message):
    if not value:
        raise AssertionError(message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=DEFAULT_OUT)
    args = parser.parse_args()
    output = os.path.abspath(args.output_dir)
    required = (
        "control_predictions.csv.gz", "external_fold_metrics.csv",
        "external_seed_metrics.csv", "external_summary.csv",
        "qualitative_summary.csv", "runtime.json", "control_tokens.npz",
    )
    for name in required:
        require(os.path.exists(os.path.join(output, name)), f"missing {name}")
    predictions = pd.read_csv(os.path.join(output, "control_predictions.csv.gz"))
    external = predictions[
        predictions["population"] == "EXTERNAL_BENIGN_CONTROL"]
    qualitative = predictions[
        predictions["population"] == "QUALITATIVE_CONTROL"]
    require(len(external) == 797 * 15, "external prediction count mismatch")
    require(len(qualitative) == 5 * 15, "qualitative prediction count mismatch")
    require(
        not predictions.duplicated(["seed", "fold", "sid"]).any(),
        "duplicate control prediction",
    )
    require(
        (predictions["retained_token_count"] <= predictions["token_budget"]).all(),
        "control input bypassed token cap",
    )
    require(predictions["score"].between(0, 1).all(), "score outside [0,1]")
    fold = pd.read_csv(os.path.join(output, "external_fold_metrics.csv"))
    require(len(fold) == 15, "expected 15 external fold rows")
    qualitative_summary = pd.read_csv(
        os.path.join(output, "qualitative_summary.csv"))
    require(len(qualitative_summary) == 5, "expected five qualitative controls")
    runtime = json.load(open(os.path.join(output, "runtime.json"), encoding="utf-8"))
    require(runtime["trainable_params"] == 30_050, "unexpected model parameter count")
    require(runtime["sample_rows"] == 500, "unexpected latency sample count")
    require(runtime["checkpoint_bytes"] > 0, "empty checkpoint")
    for section in ("model_only", "complete_local_path"):
        require(runtime[section]["median_ms"] > 0, f"invalid {section} latency")
        require(
            runtime[section]["p95_ms"] >= runtime[section]["median_ms"],
            f"invalid {section} percentile ordering",
        )
    print(
        "OPERATIONAL_CONTROLS_VERIFY_PASS "
        f"external_predictions={len(external)} "
        f"qualitative_predictions={len(qualitative)} "
        f"latency_rows={runtime['sample_rows']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

