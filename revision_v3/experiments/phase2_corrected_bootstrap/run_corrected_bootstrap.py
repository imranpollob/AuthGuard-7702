"""Phase 2, Part 1: recompute all 14 Phase 1 paired comparisons using the corrected
seed-aware paired family-clustered bootstrap (revision_v3/src/evaluation/bootstrap_v2.py).

Reads only Phase 1 result files (read-only); writes exclusively under
revision_v3/results/phase2_corrected_bootstrap/ -- Phase 1 files are never modified.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "revision_v3", "src"))

from evaluation.bootstrap_v2 import align_wide_by_sample_id, seed_aware_paired_bootstrap_ci  # noqa: E402
from evaluation.metrics import auprc as auprc_fn  # noqa: E402

RESULTS_DIR = os.path.join(REPO_ROOT, "revision_v3", "results")
OUT_DIR = os.path.join(RESULTS_DIR, "phase2_corrected_bootstrap")
os.makedirs(OUT_DIR, exist_ok=True)

CONTROLLED_COMPARISONS = [
    ("chunk_attention_2048", "flat_cnn_2048"),
    ("chunk_attention_8192", "flat_cnn_8192"),
    ("chunk_attention_16384", "flat_cnn_16384"),
    ("chunk_attention_16384", "chunk_mean_16384"),
    ("chunk_attention_16384", "chunk_max_16384"),
    ("chunk_attention_2048", "chunk_attention_8192"),
    ("chunk_attention_8192", "chunk_attention_16384"),
]
CANDIDATE_COMPARISONS = [
    ("authguard_multiscale", "authguard_reference_v3"),
    ("authguard_sequence_dense", "authguard_reference_v3"),
    ("authguard_sequence_ngram", "authguard_reference_v3"),
    ("authguard_all_views", "authguard_reference_v3"),
]
MATCHED_ROBUSTNESS_COMPARISONS = [
    ("chunk_attention_2048", "flat_cnn_2048"),
    ("chunk_attention_8192", "flat_cnn_8192"),
    ("chunk_attention_16384", "flat_cnn_16384"),
]

MODEL_ALIASES = {"chunk_attention_16384": "authguard_reference_v3"}


def recall_from_flags(y_true: np.ndarray, flags: np.ndarray) -> float:
    tp = int(((flags == 1) & (y_true == 1)).sum())
    fn = int(((flags == 0) & (y_true == 1)).sum())
    return tp / (tp + fn) if (tp + fn) > 0 else 0.0


def load_with_5pct_flag(pred_df: pd.DataFrame, fold_seed_lookup: dict, model_name: str) -> pd.DataFrame:
    file_name = MODEL_ALIASES.get(model_name, model_name)
    sub = pred_df[pred_df["model"] == model_name].copy()
    fs = fold_seed_lookup[file_name][["seed", "test_fold", "threshold_5pct"]]
    merged = sub.merge(fs, on=["seed", "test_fold"], how="left")
    merged["predicted_positive_5pct"] = (merged["calibrated_score"] >= merged["threshold_5pct"]).astype(int)
    merged["model"] = model_name  # restore requested name for downstream pivot
    return merged


def run_auprc_and_recall(pred_df_aug: pd.DataFrame, model_a: str, model_b: str) -> dict:
    scores_a, fam_a, y_a = align_wide_by_sample_id(pred_df_aug, model_a, "calibrated_score")
    scores_b, fam_b, y_b = align_wide_by_sample_id(pred_df_aug, model_b, "calibrated_score")
    assert np.array_equal(fam_a, fam_b) and np.array_equal(y_a, y_b)

    auprc_res = seed_aware_paired_bootstrap_ci(
        fam_a, y_a, scores_a, scores_b, metric_fn=auprc_fn, n_replicates=10000, seed=88012026,
    )

    flags_a, _, _ = align_wide_by_sample_id(pred_df_aug, model_a, "predicted_positive_5pct")
    flags_b, _, _ = align_wide_by_sample_id(pred_df_aug, model_b, "predicted_positive_5pct")
    recall_res = seed_aware_paired_bootstrap_ci(
        fam_a, y_a, flags_a, flags_b, metric_fn=recall_from_flags, n_replicates=10000, seed=88022026,
    )
    return {
        "model_a": model_a, "model_b": model_b,
        "auprc_delta": auprc_res["point_delta"], "auprc_ci_low": auprc_res["ci_low"], "auprc_ci_high": auprc_res["ci_high"],
        "auprc_excludes_zero": auprc_res["excludes_zero"],
        "recall_5pct_delta": recall_res["point_delta"], "recall_5pct_ci_low": recall_res["ci_low"], "recall_5pct_ci_high": recall_res["ci_high"],
        "recall_5pct_excludes_zero": recall_res["excludes_zero"],
        "auprc_per_seed_point_deltas": auprc_res["per_seed_point_deltas"],
        "recall_per_seed_point_deltas": recall_res["per_seed_point_deltas"],
    }


def main() -> int:
    controlled_pred = pd.read_csv(os.path.join(RESULTS_DIR, "controlled_ablation_predictions.csv.gz"))
    ref_pred = pd.read_csv(os.path.join(RESULTS_DIR, "authguard_reference_v3_predictions.csv.gz"))
    ref_pred_as_alias = ref_pred.copy()
    ref_pred_as_alias["model"] = "chunk_attention_16384"
    controlled_pred_full = pd.concat([controlled_pred, ref_pred_as_alias], ignore_index=True)

    fold_seed_lookup = {}
    for name in ["flat_cnn_2048", "flat_cnn_8192", "flat_cnn_16384",
                 "chunk_mean_2048", "chunk_attention_2048", "chunk_mean_8192", "chunk_attention_8192",
                 "chunk_mean_16384", "chunk_max_16384", "authguard_reference_v3",
                 "authguard_multiscale", "authguard_sequence_dense", "authguard_sequence_ngram", "authguard_all_views"]:
        fs_path = os.path.join(RESULTS_DIR, f"{name}_fold_seed.csv")
        fold_seed_lookup[name] = pd.read_csv(fs_path)

    controlled_results = []
    controlled_aug = pd.concat([
        load_with_5pct_flag(controlled_pred_full, fold_seed_lookup, m)
        for m in ["flat_cnn_2048", "flat_cnn_8192", "flat_cnn_16384", "chunk_mean_2048",
                  "chunk_attention_2048", "chunk_mean_8192", "chunk_attention_8192",
                  "chunk_mean_16384", "chunk_max_16384", "chunk_attention_16384"]
    ], ignore_index=True)
    for a, b in CONTROLLED_COMPARISONS:
        print(f"[corrected_bootstrap] controlled: {a} vs {b}", flush=True)
        controlled_results.append(run_auprc_and_recall(controlled_aug, a, b))
    pd.DataFrame(controlled_results).to_csv(os.path.join(OUT_DIR, "controlled_ablation_bootstrap_corrected.csv"), index=False)

    candidate_pred = pd.read_csv(os.path.join(RESULTS_DIR, "model_candidate_predictions.csv.gz"))
    candidate_pred_full = pd.concat([candidate_pred, ref_pred], ignore_index=True)
    candidate_aug = pd.concat([
        load_with_5pct_flag(candidate_pred_full, fold_seed_lookup, m)
        for m in ["authguard_multiscale", "authguard_sequence_dense", "authguard_sequence_ngram",
                  "authguard_all_views", "authguard_reference_v3"]
    ], ignore_index=True)
    candidate_results = []
    for a, b in CANDIDATE_COMPARISONS:
        print(f"[corrected_bootstrap] candidate: {a} vs {b}", flush=True)
        candidate_results.append(run_auprc_and_recall(candidate_aug, a, b))
    pd.DataFrame(candidate_results).to_csv(os.path.join(OUT_DIR, "model_candidate_bootstrap_corrected.csv"), index=False)

    mr_pred = pd.read_csv(os.path.join(RESULTS_DIR, "matched_robustness_predictions.csv.gz"))
    mr_results = []
    for a, b in MATCHED_ROBUSTNESS_COMPARISONS:
        print(f"[corrected_bootstrap] matched_robustness: {a} vs {b}", flush=True)
        scores_a, fam_a, y_a = align_wide_by_sample_id(mr_pred, a, "flood200_score")
        scores_b, fam_b, y_b = align_wide_by_sample_id(mr_pred, b, "flood200_score")
        assert np.array_equal(fam_a, fam_b) and np.array_equal(y_a, y_b)
        res = seed_aware_paired_bootstrap_ci(fam_a, y_a, scores_a, scores_b, metric_fn=auprc_fn,
                                              n_replicates=10000, seed=88032026)
        mr_results.append({
            "model_a": a, "model_b": b, "condition": "flood200",
            "auprc_delta": res["point_delta"], "auprc_ci_low": res["ci_low"], "auprc_ci_high": res["ci_high"],
            "auprc_excludes_zero": res["excludes_zero"],
            "per_seed_point_deltas": res["per_seed_point_deltas"],
        })
    pd.DataFrame(mr_results).to_csv(os.path.join(OUT_DIR, "matched_robustness_bootstrap_corrected.csv"), index=False)

    with open(os.path.join(OUT_DIR, "all_corrected_results.json"), "w") as f:
        json.dump({
            "controlled_ablation": controlled_results,
            "model_candidates": candidate_results,
            "matched_robustness": mr_results,
        }, f, indent=2, default=str)

    print("[corrected_bootstrap] DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
