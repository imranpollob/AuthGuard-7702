"""Family-clustered paired bootstrap CIs for the 7 required controlled-ablation comparisons.

Method (documented explicitly, since it is a Phase-1 simplification of the full
fold-then-seed hierarchical bootstrap): for each seed, pool the per-row test predictions
across the 5 outer folds (every primary row is tested exactly once per seed, so this pooling
does not mix train/test or duplicate rows). AUPRC is bootstrapped directly on pooled
calibrated scores; Recall@5%FPR is bootstrapped on the already-decided prediction outcome
using each row's OWN fold-specific frozen 5%-FPR threshold (never recomputed on resampled
data). The three per-seed bootstrap results are then averaged (point delta and CI bounds) to
give one final interval per comparison — this is a mean-of-seed-level-bootstraps, not a
pooled-across-seed bootstrap (which would over-weight families that recur across seeds'
identical fold structure).
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "revision_v3", "src"))
sys.path.insert(0, os.path.join(REPO_ROOT, "revision_v3", "experiments", "controlled_ablation"))

from evaluation.bootstrap import paired_family_bootstrap_ci  # noqa: E402
from evaluation.metrics import auprc as auprc_fn  # noqa: E402
from model_specs import REQUIRED_COMPARISONS  # noqa: E402

RESULTS_DIR = os.path.join(REPO_ROOT, "revision_v3", "results")


def recall_from_flags(y_true: np.ndarray, flags: np.ndarray) -> float:
    tp = int(((flags == 1) & (y_true == 1)).sum())
    fn = int(((flags == 0) & (y_true == 1)).sum())
    return tp / (tp + fn) if (tp + fn) > 0 else 0.0


# chunk_attention_16384 is architecturally identical to authguard_reference_v3 (chunk_size=256,
# max_chunks=64, aggregation="attention") and is NOT retrained separately -- its results are
# the reference-validation run's own predictions, aliased here for the comparison table.
MODEL_ALIASES = {"chunk_attention_16384": "authguard_reference_v3"}


def load_predictions_with_flags(model_name: str) -> pd.DataFrame:
    """Loads {model}_predictions.csv.gz + {model}_fold_seed.csv, joins in each row's
    fold-specific frozen threshold_5pct, and derives predicted_positive_5pct."""
    file_name = MODEL_ALIASES.get(model_name, model_name)
    pred_path = os.path.join(RESULTS_DIR, f"{file_name}_predictions.csv.gz")
    fold_seed_path = os.path.join(RESULTS_DIR, f"{file_name}_fold_seed.csv")
    preds = pd.read_csv(pred_path)
    fold_seed = pd.read_csv(fold_seed_path)[["seed", "test_fold", "threshold_5pct"]]
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
            metric_fn=auprc_fn, n_replicates=10000, seed=77032026 + seed,
        )
        recall_res = paired_family_bootstrap_ci(
            fam, y, merged["predicted_positive_5pct_a"].to_numpy(), merged["predicted_positive_5pct_b"].to_numpy(),
            metric_fn=recall_from_flags, n_replicates=10000, seed=77042026 + seed,
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
    rows = []
    for model_a, model_b in REQUIRED_COMPARISONS:
        print(f"[bootstrap] {model_a} vs {model_b} ...", flush=True)
        rows.append(compare(model_a, model_b))
    out_df = pd.DataFrame(rows)
    out_df.to_csv(os.path.join(RESULTS_DIR, "controlled_ablation_bootstrap.csv"), index=False)
    print(out_df.to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
