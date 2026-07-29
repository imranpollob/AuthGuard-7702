"""Retrains authguard_sequence_dense (the strongest exploratory candidate per
MODEL_CANDIDATE_REPORT.md -- statistically tied with authguard_reference_v3 on clean AUPRC,
0.929 vs 0.929) WITH checkpoint saving, then scores it clean vs Flood-200% at its native
16,384-token budget, appended to matched_robustness_summary.csv as a labeled addendum row.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd
import torch

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "revision_v3", "src"))

from data.loader import load_config, load_primary_dataset  # noqa: E402
from features.disassembler import linear_sweep, normalize_hex  # noqa: E402
from features.encode import VOCAB_SIZE, chunk_token_ids, tokens_to_ids  # noqa: E402
from models.forward_fns import hybrid_forward  # noqa: E402
from models.hybrid import HybridConfig, HybridModel  # noqa: E402
from robustness.flooding import build_donor_pool, flood_bytecode  # noqa: E402
from training.calibration import apply_temperature  # noqa: E402
from training.dataset import build_token_cache, chunks_array_for_spec  # noqa: E402
from training.harness import SEEDS, fold_indices, run_full_protocol  # noqa: E402
from evaluation.metrics import auprc as auprc_fn, metrics_at_threshold  # noqa: E402

RESULTS_DIR = os.path.join(REPO_ROOT, "revision_v3", "results")
CHECKPOINT_DIR = os.path.join(RESULTS_DIR, "checkpoints")
MODEL_NAME = "authguard_sequence_dense"


def build_model():
    return HybridModel(HybridConfig(vocab_size=VOCAB_SIZE, chunk_size=256, max_chunks=64, use_dense=True))


def score_one(model, device, hex_bc: str, token_cache_entry=None):
    hex_norm = normalize_hex(hex_bc)
    tokens, _, _ = linear_sweep(hex_norm)
    ids = tokens_to_ids(tokens)
    chunks_arr = chunk_token_ids(ids, chunk_size=256, max_chunks=64)
    mask_arr = np.ones(len(chunks_arr), dtype=np.bool_)
    chunks = torch.as_tensor(chunks_arr[None, :, :].astype(np.int64)).to(device)
    mask = torch.as_tensor(mask_arr[None, :]).to(device)
    # dense view needs the structural feature vector; recompute via the cached encoder
    from features.encode import encode_bytecode
    enc = encode_bytecode(hex_bc, chunk_size=256, max_chunks=64)
    dense = torch.as_tensor(enc.dense[None, :]).to(device)
    with torch.no_grad():
        logit = hybrid_forward(model, {"chunks": chunks, "chunk_mask": mask, "dense": dense})
    return float(logit.cpu().numpy()[0]), len(tokens)


def main() -> int:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[strongest_candidate_robustness] device={device}", flush=True)

    df = load_primary_dataset()
    token_cache = build_token_cache(df)
    tensors = chunks_array_for_spec(df, token_cache, chunk_size=256, max_chunks=64)

    ckpt_glob_ready = os.path.exists(os.path.join(CHECKPOINT_DIR, f"{MODEL_NAME}_seed7702_fold0.pt"))
    if not ckpt_glob_ready:
        print(f"[strongest_candidate_robustness] retraining {MODEL_NAME} with checkpoints ...", flush=True)
        run_full_protocol(
            model_name=MODEL_NAME, build_model_fn=build_model, forward_fn=hybrid_forward,
            tensors=tensors, results_dir=RESULTS_DIR, device=device, checkpoint_dir=CHECKPOINT_DIR,
        )

    full_df = pd.read_csv(os.path.join(REPO_ROOT, load_config()["benchmark_csv_gz"]))
    primary_df = load_primary_dataset()
    donor_pool = build_donor_pool(full_df)

    prediction_rows = []
    for seed in SEEDS:
        for test_fold in range(5):
            ckpt_path = os.path.join(CHECKPOINT_DIR, f"{MODEL_NAME}_seed{seed}_fold{test_fold}.pt")
            ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
            model = build_model()
            model.load_state_dict(ckpt["model_state_dict"])
            model.to(device).eval()
            temperature = ckpt["temperature"]
            threshold_5pct = ckpt["threshold_5pct"]

            _, _, test_idx, _ = fold_indices(primary_df["fold_id"].to_numpy(), test_fold)
            for _, row in primary_df.iloc[test_idx].iterrows():
                clean_logit, _ = score_one(model, device, row["runtime_bytecode"])
                flooded_hex = flood_bytecode(row["runtime_bytecode"], row["sample_id"], row["family_id"],
                                              donor_pool, seed=seed, fraction=2.0, condition="flood200")
                flood_logit, _ = score_one(model, device, flooded_hex)
                prediction_rows.append({
                    "model": MODEL_NAME, "seed": seed, "test_fold": test_fold,
                    "sample_id": row["sample_id"], "family_id": row["family_id"], "label": int(row["label"]),
                    "clean_score": float(apply_temperature(torch.as_tensor(clean_logit), temperature)),
                    "flood200_score": float(apply_temperature(torch.as_tensor(flood_logit), temperature)),
                    "threshold_5pct": threshold_5pct,
                })
        print(f"[strongest_candidate_robustness] seed {seed} done", flush=True)

    pred_df = pd.DataFrame(prediction_rows)
    pred_df.to_csv(os.path.join(RESULTS_DIR, "strongest_candidate_robustness_predictions.csv.gz"),
                    index=False, compression="gzip")

    seed_clean_auprc, seed_flood_auprc = [], []
    seed_clean_recall, seed_flood_recall, seed_flood_fpr = [], [], []
    for seed in SEEDS:
        pf_c, pf_f, pf_cr, pf_fr, pf_ffpr = [], [], [], [], []
        for test_fold in range(5):
            s = pred_df[(pred_df.seed == seed) & (pred_df.test_fold == test_fold)]
            y = s["label"].to_numpy()
            pf_c.append(auprc_fn(y, s["clean_score"].to_numpy()))
            pf_f.append(auprc_fn(y, s["flood200_score"].to_numpy()))
            cm = metrics_at_threshold(y, s["clean_score"].to_numpy(), s["threshold_5pct"].to_numpy())
            fm = metrics_at_threshold(y, s["flood200_score"].to_numpy(), s["threshold_5pct"].to_numpy())
            pf_cr.append(cm["recall"]); pf_fr.append(fm["recall"]); pf_ffpr.append(fm["observed_fpr"])
        seed_clean_auprc.append(np.mean(pf_c)); seed_flood_auprc.append(np.mean(pf_f))
        seed_clean_recall.append(np.mean(pf_cr)); seed_flood_recall.append(np.mean(pf_fr)); seed_flood_fpr.append(np.mean(pf_ffpr))

    row = {
        "model": MODEL_NAME, "budget": 16384,
        "clean_auprc_mean": float(np.mean(seed_clean_auprc)), "clean_auprc_std": float(np.std(seed_clean_auprc, ddof=1)),
        "flood200_auprc_mean": float(np.mean(seed_flood_auprc)), "flood200_auprc_std": float(np.std(seed_flood_auprc, ddof=1)),
        "absolute_degradation_auprc": float(np.mean(seed_clean_auprc) - np.mean(seed_flood_auprc)),
        "clean_recall_at_5pct_mean": float(np.mean(seed_clean_recall)),
        "flood200_recall_at_frozen_threshold_mean": float(np.mean(seed_flood_recall)),
        "flood200_observed_fpr_mean": float(np.mean(seed_flood_fpr)),
        "pct_flooded_exceeding_budget": None,
        "note": "strongest exploratory candidate, evaluated separately (not part of the main matched-budget table)",
    }
    summary_path = os.path.join(RESULTS_DIR, "matched_robustness_summary.csv")
    existing = pd.read_csv(summary_path)
    if "note" not in existing.columns:
        existing["note"] = ""
    existing = existing[existing["model"] != MODEL_NAME]
    out = pd.concat([existing, pd.DataFrame([row])], ignore_index=True)
    out.to_csv(summary_path, index=False)
    print(json.dumps(row, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
