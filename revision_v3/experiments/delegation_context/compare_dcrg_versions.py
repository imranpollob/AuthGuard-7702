#!/usr/bin/env python3
"""Paired family-bootstrap comparison of two full-DCRG OOF prediction artifacts."""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
V3 = os.path.join(REPO_ROOT, "revision_v3")
sys.path.insert(0, os.path.join(V3, "src"))

from evaluation.bootstrap_v2 import seed_aware_paired_bootstrap_ci  # noqa: E402
from evaluation.metrics import auprc  # noqa: E402


def arrays(path: str):
    frame = pd.read_csv(path)
    frame = frame[frame["model"] == "dcrg_full"].copy()
    pivot = frame.pivot(index="sample_id", columns="seed", values="score").sort_index()
    metadata = (
        frame[["sample_id", "family_id", "label"]].drop_duplicates("sample_id")
        .set_index("sample_id").loc[pivot.index]
    )
    return (
        {int(seed): pivot[seed].to_numpy(dtype=np.float64) for seed in pivot.columns},
        metadata["family_id"].to_numpy(), metadata["label"].to_numpy(dtype=np.int64),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    baseline, families, labels = arrays(args.baseline)
    candidate, candidate_families, candidate_labels = arrays(args.candidate)
    if set(baseline) != set(candidate):
        raise ValueError("prediction seeds differ")
    if not np.array_equal(families, candidate_families) or not np.array_equal(labels, candidate_labels):
        raise ValueError("prediction population metadata differs")
    report = {
        "status": "PROVISIONAL_INHERITED_LABEL_VERSION_COMPARISON",
        "candidate": "jump_fenced_metadata_plus_state_widening",
        "baseline": "original_bounded_cfg",
        "mean_seed_auprc": {
            "baseline": float(np.mean([auprc(labels, scores) for scores in baseline.values()])),
            "candidate": float(np.mean([auprc(labels, scores) for scores in candidate.values()])),
        },
        "paired_family_bootstrap_auprc": seed_aware_paired_bootstrap_ci(
            family_ids=families, y_true=labels, scores_a_by_seed=candidate,
            scores_b_by_seed=baseline, metric_fn=auprc, n_replicates=10000,
            seed=77032026,
        ),
        "claim_boundary": (
            "The comparison uses inherited labels. Coverage correctness is independently "
            "label-free; predictive improvement requires independent-label confirmation."
        ),
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
