"""Phase 2, Part 2: corrected seed-aware bootstrap for parameter-matched Flat CNN vs
chunk_attention, on clean data (AUPRC/Recall@5%) and on Flood-200% (reusing Phase 1's
matched-robustness flooding implementation for direct comparability with the existing
flat_cnn_* vs chunk_attention_* Flood-200% numbers already in
revision_v3/results/matched_robustness_predictions.csv.gz -- Part 3 builds the more elaborate
paper-grade flooding protocol separately).
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd
import torch

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "revision_v3", "src"))

from data.loader import load_config, load_primary_dataset  # noqa: E402
from evaluation.bootstrap_v2 import align_wide_by_sample_id, seed_aware_paired_bootstrap_ci  # noqa: E402
from evaluation.metrics import auprc as auprc_fn  # noqa: E402
from features.disassembler import linear_sweep, normalize_hex  # noqa: E402
from features.encode import VOCAB_SIZE, tokens_to_ids  # noqa: E402
from models.flat_cnn import FlatCNN, FlatCNNConfig, downsample_to_budget  # noqa: E402
from models.forward_fns import flat_forward  # noqa: E402
from robustness.flooding import build_donor_pool, flood_bytecode  # noqa: E402
from training.calibration import apply_temperature  # noqa: E402
from training.harness import SEEDS, fold_indices  # noqa: E402

RESULTS_DIR = os.path.join(REPO_ROOT, "revision_v3", "results")
PM_DIR = os.path.join(RESULTS_DIR, "parameter_matched")
PM_CKPT_DIR = os.path.join(PM_DIR, "checkpoints")

BUDGETS = [2048, 8192, 16384]


def recall_from_flags(y_true, flags):
    tp = int(((flags == 1) & (y_true == 1)).sum())
    fn = int(((flags == 0) & (y_true == 1)).sum())
    return tp / (tp + fn) if (tp + fn) > 0 else 0.0


def load_with_flag(pred_df, fold_seed, model_name):
    sub = pred_df[pred_df["model"] == model_name].copy()
    fs = fold_seed[["seed", "test_fold", "threshold_5pct"]]
    merged = sub.merge(fs, on=["seed", "test_fold"], how="left")
    merged["predicted_positive_5pct"] = (merged["calibrated_score"] >= merged["threshold_5pct"]).astype(int)
    return merged


def clean_comparison(budget):
    chunk_pred = pd.read_csv(os.path.join(RESULTS_DIR, f"chunk_attention_{budget}_predictions.csv.gz")) \
        if budget != 16384 else pd.read_csv(os.path.join(RESULTS_DIR, "authguard_reference_v3_predictions.csv.gz"))
    if budget == 16384:
        chunk_pred = chunk_pred.copy()
        chunk_pred["model"] = "chunk_attention_16384"
    chunk_fs = pd.read_csv(os.path.join(RESULTS_DIR, f"{'authguard_reference_v3' if budget == 16384 else f'chunk_attention_{budget}'}_fold_seed.csv"))

    matched_pred = pd.read_csv(os.path.join(PM_DIR, f"flat_cnn_matched_{budget}_predictions.csv.gz"))
    matched_fs = pd.read_csv(os.path.join(PM_DIR, f"flat_cnn_matched_{budget}_fold_seed.csv"))

    aug = pd.concat([
        load_with_flag(chunk_pred, chunk_fs, f"chunk_attention_{budget}"),
        load_with_flag(matched_pred, matched_fs, f"flat_cnn_matched_{budget}"),
    ], ignore_index=True)

    sa, fa, ya = align_wide_by_sample_id(aug, f"chunk_attention_{budget}", "calibrated_score")
    sb, fb, yb = align_wide_by_sample_id(aug, f"flat_cnn_matched_{budget}", "calibrated_score")
    assert np.array_equal(fa, fb) and np.array_equal(ya, yb)
    auprc_res = seed_aware_paired_bootstrap_ci(fa, ya, sa, sb, metric_fn=auprc_fn, n_replicates=10000, seed=89012026)

    flags_a, _, _ = align_wide_by_sample_id(aug, f"chunk_attention_{budget}", "predicted_positive_5pct")
    flags_b, _, _ = align_wide_by_sample_id(aug, f"flat_cnn_matched_{budget}", "predicted_positive_5pct")
    recall_res = seed_aware_paired_bootstrap_ci(fa, ya, flags_a, flags_b, metric_fn=recall_from_flags, n_replicates=10000, seed=89022026)

    return {
        "budget": budget,
        "auprc_delta": auprc_res["point_delta"], "auprc_ci_low": auprc_res["ci_low"], "auprc_ci_high": auprc_res["ci_high"],
        "auprc_excludes_zero": auprc_res["excludes_zero"],
        "recall_5pct_delta": recall_res["point_delta"], "recall_5pct_ci_low": recall_res["ci_low"], "recall_5pct_ci_high": recall_res["ci_high"],
        "recall_5pct_excludes_zero": recall_res["excludes_zero"],
    }


def run_flood_scoring():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    full_df = pd.read_csv(os.path.join(REPO_ROOT, load_config()["benchmark_csv_gz"]))
    primary_df = load_primary_dataset()
    donor_pool = build_donor_pool(full_df)

    rows = []
    for budget in BUDGETS:
        for seed in SEEDS:
            for test_fold in range(5):
                ckpt_path = os.path.join(PM_CKPT_DIR, f"flat_cnn_matched_{budget}_seed{seed}_fold{test_fold}.pt")
                ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
                model = FlatCNN(FlatCNNConfig(vocab_size=VOCAB_SIZE, max_len=budget, embedding_dim=32, channels=60))
                model.load_state_dict(ckpt["model_state_dict"])
                model.to(device).eval()
                temperature = ckpt["temperature"]
                threshold_5pct = ckpt["threshold_5pct"]

                _, _, test_idx, _ = fold_indices(primary_df["fold_id"].to_numpy(), test_fold)
                for _, row in primary_df.iloc[test_idx].iterrows():
                    tokens, _, _ = linear_sweep(normalize_hex(row["runtime_bytecode"]))
                    ids = tokens_to_ids(tokens)
                    arr = downsample_to_budget(ids, budget)
                    with torch.no_grad():
                        clean_logit = flat_forward(model, {"tokens": torch.as_tensor(arr[None, :].astype(np.int64)).to(device)}).cpu().numpy()[0]
                    flooded_hex = flood_bytecode(row["runtime_bytecode"], row["sample_id"], row["family_id"],
                                                  donor_pool, seed=seed, fraction=2.0, condition="flood200")
                    f_tokens, _, _ = linear_sweep(normalize_hex(flooded_hex))
                    f_ids = tokens_to_ids(f_tokens)
                    f_arr = downsample_to_budget(f_ids, budget)
                    with torch.no_grad():
                        flood_logit = flat_forward(model, {"tokens": torch.as_tensor(f_arr[None, :].astype(np.int64)).to(device)}).cpu().numpy()[0]

                    rows.append({
                        "model": f"flat_cnn_matched_{budget}", "seed": seed, "test_fold": test_fold,
                        "sample_id": row["sample_id"], "family_id": row["family_id"], "label": int(row["label"]),
                        "clean_score": float(apply_temperature(torch.as_tensor(clean_logit), temperature)),
                        "flood200_score": float(apply_temperature(torch.as_tensor(flood_logit), temperature)),
                        "threshold_5pct": threshold_5pct,
                    })
        print(f"[pm_bootstrap] flood-scored budget {budget}", flush=True)

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(PM_DIR, "parameter_matched_flood_predictions.csv.gz"), index=False, compression="gzip")
    return df


def flood_comparison(budget, pm_flood_df):
    chunk_flood = pd.read_csv(os.path.join(RESULTS_DIR, "matched_robustness_predictions.csv.gz"))
    chunk_flood = chunk_flood[chunk_flood["model"] == f"chunk_attention_{budget}"]
    matched_flood = pm_flood_df[pm_flood_df["model"] == f"flat_cnn_matched_{budget}"]

    aug = pd.concat([chunk_flood, matched_flood], ignore_index=True)
    sa, fa, ya = align_wide_by_sample_id(aug, f"chunk_attention_{budget}", "flood200_score")
    sb, fb, yb = align_wide_by_sample_id(aug, f"flat_cnn_matched_{budget}", "flood200_score")
    assert np.array_equal(fa, fb) and np.array_equal(ya, yb)
    res = seed_aware_paired_bootstrap_ci(fa, ya, sa, sb, metric_fn=auprc_fn, n_replicates=10000, seed=89032026)
    return {
        "budget": budget, "condition": "flood200",
        "auprc_delta": res["point_delta"], "auprc_ci_low": res["ci_low"], "auprc_ci_high": res["ci_high"],
        "auprc_excludes_zero": res["excludes_zero"],
    }


def main():
    clean_results = [clean_comparison(b) for b in BUDGETS]
    pd.DataFrame(clean_results).to_csv(os.path.join(PM_DIR, "parameter_matched_clean_bootstrap.csv"), index=False)
    print(pd.DataFrame(clean_results).to_string())

    pm_flood_df = run_flood_scoring()
    flood_results = [flood_comparison(b, pm_flood_df) for b in BUDGETS]
    pd.DataFrame(flood_results).to_csv(os.path.join(PM_DIR, "parameter_matched_flood_bootstrap.csv"), index=False)
    print(pd.DataFrame(flood_results).to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
