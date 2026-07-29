"""Family-clustered paired bootstrap: each exploratory candidate vs. authguard_reference_v3.
Same method as controlled_ablation/run_controlled_bootstrap.py (see that file's docstring).
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
CANDIDATES = ["authguard_multiscale", "authguard_sequence_dense", "authguard_sequence_ngram", "authguard_all_views"]
REFERENCE = "authguard_reference_v3"


def recall_from_flags(y_true: np.ndarray, flags: np.ndarray) -> float:
    tp = int(((flags == 1) & (y_true == 1)).sum())
    fn = int(((flags == 0) & (y_true == 1)).sum())
    return tp / (tp + fn) if (tp + fn) > 0 else 0.0


def load_predictions_with_flags(model_name: str) -> pd.DataFrame:
    preds = pd.read_csv(os.path.join(RESULTS_DIR, f"{model_name}_predictions.csv.gz"))
    fold_seed = pd.read_csv(os.path.join(RESULTS_DIR, f"{model_name}_fold_seed.csv"))[["seed", "test_fold", "threshold_5pct"]]
    merged = preds.merge(fold_seed, on=["seed", "test_fold"], how="left")
    merged["predicted_positive_5pct"] = (merged["calibrated_score"] >= merged["threshold_5pct"]).astype(int)
    return merged


def compare(model_a: str, model_b: str) -> dict:
    df_a = load_predictions_with_flags(model_a)
    df_b = load_predictions_with_flags(model_b)

    auprc_deltas, auprc_los, auprc_his = [], [], []
    recall_deltas, recall_los, recall_his = [], [], []

    for seed in sorted(df_a["seed"].unique()):
        a_seed = df_a[df_a["seed"] == seed]
        b_seed = df_b[df_b["seed"] == seed]
        merged = a_seed.merge(b_seed, on=["sample_id", "family_id", "label"], suffixes=("_a", "_b"))
        assert len(merged) == 2190, f"expected 2190 pooled rows for seed {seed}, got {len(merged)}"
        y = merged["label"].to_numpy()
        fam = merged["family_id"].to_numpy()

        auprc_res = paired_family_bootstrap_ci(
            fam, y, merged["calibrated_score_a"].to_numpy(), merged["calibrated_score_b"].to_numpy(),
            metric_fn=auprc_fn, n_replicates=10000, seed=77052026 + seed,
        )
        recall_res = paired_family_bootstrap_ci(
            fam, y, merged["predicted_positive_5pct_a"].to_numpy(), merged["predicted_positive_5pct_b"].to_numpy(),
            metric_fn=recall_from_flags, n_replicates=10000, seed=77062026 + seed,
        )
        auprc_deltas.append(auprc_res["delta"]); auprc_los.append(auprc_res["ci_low"]); auprc_his.append(auprc_res["ci_high"])
        recall_deltas.append(recall_res["delta"]); recall_los.append(recall_res["ci_low"]); recall_his.append(recall_res["ci_high"])

    return {
        "model_a": model_a, "model_b": model_b,
        "auprc_delta_mean": float(np.mean(auprc_deltas)),
        "auprc_ci_low_mean": float(np.mean(auprc_los)),
        "auprc_ci_high_mean": float(np.mean(auprc_his)),
        "auprc_excludes_zero": bool(np.mean(auprc_los) > 0 or np.mean(auprc_his) < 0),
        "recall_5pct_delta_mean": float(np.mean(recall_deltas)),
        "recall_5pct_ci_low_mean": float(np.mean(recall_los)),
        "recall_5pct_ci_high_mean": float(np.mean(recall_his)),
        "recall_5pct_excludes_zero": bool(np.mean(recall_los) > 0 or np.mean(recall_his) < 0),
    }


def main() -> int:
    rows = [compare(c, REFERENCE) for c in CANDIDATES]
    out_df = pd.DataFrame(rows)
    out_df.to_csv(os.path.join(RESULTS_DIR, "model_candidate_bootstrap.csv"), index=False)
    print(out_df.to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
