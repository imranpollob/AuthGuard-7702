"""Phase 2, Part 3 analysis: summary statistics + corrected seed-aware bootstrap answers to
questions A-D, from final_robustness_predictions.csv.gz (already scored)."""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "revision_v3", "src"))

from evaluation.bootstrap_v2 import seed_aware_paired_bootstrap_ci  # noqa: E402
from evaluation.metrics import auprc as auprc_fn  # noqa: E402

RESULTS_DIR = os.path.join(REPO_ROOT, "revision_v3", "results", "final_robustness")


def align(pred_df, model_name, score_col):
    sub = pred_df[pred_df["model"] == model_name]
    seeds = sorted(sub["seed"].unique())
    pivot = sub.pivot(index="sample_id", columns="seed", values=score_col).sort_index()
    meta = sub[["sample_id", "family_id", "label"]].drop_duplicates("sample_id").set_index("sample_id").sort_index()
    assert list(pivot.index) == list(meta.index)
    return {s: pivot[s].to_numpy() for s in seeds}, meta["family_id"].to_numpy(), meta["label"].to_numpy()


def compare(pred_df, model_a, model_b, score_col="flood_score_mean"):
    sa, fa, ya = align(pred_df, model_a, score_col)
    sb, fb, yb = align(pred_df, model_b, score_col)
    assert np.array_equal(fa, fb) and np.array_equal(ya, yb)
    res = seed_aware_paired_bootstrap_ci(fa, ya, sa, sb, metric_fn=auprc_fn, n_replicates=10000, seed=90012026)
    return {
        "model_a": model_a, "model_b": model_b, "metric": "flood_auprc_mean_across_3_transform_seeds",
        "delta": res["point_delta"], "ci_low": res["ci_low"], "ci_high": res["ci_high"],
        "excludes_zero": res["excludes_zero"],
    }


def main():
    pred_df = pd.read_csv(os.path.join(RESULTS_DIR, "final_robustness_predictions.csv.gz"))

    # --- descriptive summary per model ---
    summary_rows = []
    for model in pred_df["model"].unique():
        sub = pred_df[pred_df["model"] == model]
        seed_clean, seed_flood = [], []
        for seed in sorted(sub["seed"].unique()):
            pf_c, pf_f = [], []
            for fold in sorted(sub["test_fold"].unique()):
                s = sub[(sub["seed"] == seed) & (sub["test_fold"] == fold)]
                y = s["label"].to_numpy()
                pf_c.append(auprc_fn(y, s["clean_score"].to_numpy()))
                pf_f.append(auprc_fn(y, s["flood_score_mean"].to_numpy()))
            seed_clean.append(np.mean(pf_c))
            seed_flood.append(np.mean(pf_f))
        summary_rows.append({
            "model": model,
            "clean_auprc_mean": float(np.mean(seed_clean)), "clean_auprc_std": float(np.std(seed_clean, ddof=1)),
            "flood_auprc_mean": float(np.mean(seed_flood)), "flood_auprc_std": float(np.std(seed_flood, ddof=1)),
            "absolute_degradation": float(np.mean(seed_clean) - np.mean(seed_flood)),
            "donor_variance_mean_std_across_transform_seeds": float(sub["flood_score_std_across_transform_seeds"].mean()),
            "donor_variance_p95_std_across_transform_seeds": float(sub["flood_score_std_across_transform_seeds"].quantile(0.95)),
        })
    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(os.path.join(RESULTS_DIR, "final_robustness_summary.csv"), index=False)
    print(summary_df.to_string())

    # --- A, B, C ---
    answers = {
        "A_chunk_attention_vs_chunk_max": compare(pred_df, "authguard_reference_v3", "chunk_max_16384"),
        "B_sequence_dense_vs_reference": compare(pred_df, "authguard_sequence_dense", "authguard_reference_v3"),
        "C_reference_vs_parameter_matched_flat": compare(pred_df, "authguard_reference_v3", "flat_cnn_matched_16384"),
        "C2_reference_vs_original_large_flat": compare(pred_df, "authguard_reference_v3", "flat_cnn_16384"),
    }
    with open(os.path.join(RESULTS_DIR, "final_robustness_ABC_bootstrap.json"), "w") as f:
        json.dump(answers, f, indent=2, default=str)
    print(json.dumps(answers, indent=2, default=str))

    # --- D: donor-selection variance ---
    donor_variance = pred_df.groupby("model")["flood_score_std_across_transform_seeds"].agg(["mean", "median", "max"])
    donor_variance.to_csv(os.path.join(RESULTS_DIR, "donor_selection_variance.csv"))
    print(donor_variance.to_string())

    return 0


if __name__ == "__main__":
    sys.exit(main())
