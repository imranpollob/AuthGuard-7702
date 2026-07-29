"""Family-clustered paired bootstrap: chunk_attention vs flat_cnn on Flood-200% AUPRC, at
each matched budget. Same method as controlled_ablation's bootstrap (pool per-seed across
folds, bootstrap resample families, average delta/CI across seeds).
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "revision_v3", "src"))

from evaluation.bootstrap import paired_family_bootstrap_ci  # noqa: E402
from evaluation.metrics import auprc as auprc_fn  # noqa: E402

RESULTS_DIR = os.path.join(REPO_ROOT, "revision_v3", "results")
PAIRS = [("chunk_attention_2048", "flat_cnn_2048"), ("chunk_attention_8192", "flat_cnn_8192"),
         ("chunk_attention_16384", "flat_cnn_16384")]


def compare(pred_df: pd.DataFrame, model_a: str, model_b: str) -> dict:
    a = pred_df[pred_df["model"] == model_a]
    b = pred_df[pred_df["model"] == model_b]
    deltas, los, his = [], [], []
    for seed in sorted(a["seed"].unique()):
        merged = a[a["seed"] == seed].merge(
            b[b["seed"] == seed], on=["sample_id", "family_id", "label"], suffixes=("_a", "_b"))
        y = merged["label"].to_numpy()
        fam = merged["family_id"].to_numpy()
        res = paired_family_bootstrap_ci(
            fam, y, merged["flood200_score_a"].to_numpy(), merged["flood200_score_b"].to_numpy(),
            metric_fn=auprc_fn, n_replicates=10000, seed=77072026 + seed,
        )
        deltas.append(res["delta"]); los.append(res["ci_low"]); his.append(res["ci_high"])
    return {
        "model_a": model_a, "model_b": model_b,
        "flood200_auprc_delta_mean": float(np.mean(deltas)),
        "flood200_auprc_ci_low_mean": float(np.mean(los)),
        "flood200_auprc_ci_high_mean": float(np.mean(his)),
        "excludes_zero": bool(np.mean(los) > 0 or np.mean(his) < 0),
    }


def main() -> int:
    pred_df = pd.read_csv(os.path.join(RESULTS_DIR, "matched_robustness_predictions.csv.gz"))
    rows = [compare(pred_df, a, b) for a, b in PAIRS]
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(RESULTS_DIR, "matched_robustness_bootstrap.csv"), index=False)
    print(out.to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
