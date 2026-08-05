#!/usr/bin/env python3
"""Development-only proxy evaluation of the coverage-correct DCRG ablations.

The provisional Gold-Test labels have already been inspected during method development.  This
script therefore cannot create a final-evaluation artifact and explicitly marks the 150 items as
development evidence for any method selected using this output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
V3 = os.path.join(REPO_ROOT, "revision_v3")
sys.path.insert(0, os.path.join(V3, "src"))
sys.path.insert(0, os.path.dirname(__file__))

from evaluate_against_human_labels import evaluate_dcrg_ablation_predictions  # noqa: E402
from run_current_label_oracle_what_if import human_view, load_proxy_labels  # noqa: E402


PREDICTIONS = os.path.join(
    V3, "results", "delegation_context_coverage_v2", "dcrg_ablation_predictions.csv.gz"
)
OUTPUT = os.path.join(
    V3, "results", "delegation_context_coverage_v2", "coverage_v2_proxy_what_if.json"
)


def sha256_file(path: str) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def sensitivity(proxy: pd.DataFrame, predictions: pd.DataFrame, assignment: int | None) -> dict:
    binary = human_view(proxy, assignment)
    binary = binary[~binary["excluded_from_binary"]][["item_id", "binary_label"]]
    merged = predictions[predictions["sample_id"].isin(binary["item_id"])].merge(
        binary, left_on="sample_id", right_on="item_id", validate="many_to_one"
    )
    means = {
        str(model): float(np.mean([
            average_precision_score(seed_rows["binary_label"], seed_rows["score"])
            for _, seed_rows in rows.groupby("seed")
        ]))
        for model, rows in merged.groupby("model")
    }
    return {
        "mean_seed_auprc": means,
        "full_minus_baselines": {
            name: means["dcrg_full"] - value
            for name, value in means.items() if name != "dcrg_full"
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", default=PREDICTIONS)
    parser.add_argument("--output", default=OUTPUT)
    args = parser.parse_args()
    proxy = load_proxy_labels()
    predictions = pd.read_csv(args.predictions)
    report = evaluate_dcrg_ablation_predictions(
        human_view(proxy, None), predictions, bootstrap_replicates=10000
    )
    report["status"] = "DEVELOPMENT_ONLY_CURRENT_LABEL_PROXY_ABLATION"
    output = {
        "status": "DEVELOPMENT_ONLY_CURRENT_LABEL_PROXY_NOT_FINAL_EVIDENCE",
        "fatal_validity_warning": (
            "These 150 provisional-label items have been inspected during method development. "
            "Any method selected using this report requires a new untouched human-labeled test set."
        ),
        "assumption": "SAFE/UNSAFE provisional labels act as human-label proxy; UNCERTAIN is excluded.",
        "binary_proxy_count": int(proxy["llm_provisional_label"].isin({"SAFE", "UNSAFE"}).sum()),
        "excluded_uncertain_count": int(proxy["llm_provisional_label"].eq("UNCERTAIN").sum()),
        "ablation": report,
        "uncertain_sensitivity": {
            "exclude": sensitivity(proxy, predictions, None),
            "all_uncertain_as_negative": sensitivity(proxy, predictions, 0),
            "all_uncertain_as_unsafe": sensitivity(proxy, predictions, 1),
        },
        "prediction_sha256": sha256_file(args.predictions),
    }
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w") as handle:
        json.dump(output, handle, indent=2, sort_keys=True)
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
