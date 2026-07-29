"""Matched-budget Flood-200% robustness: every model is inference-scored on clean and
flooded test rows under the SAME token budget it was trained with (never uncapped in the
main comparison table -- an uncapped diagnostic is written separately, see
run_uncapped_diagnostic.py). Uses saved fold/seed checkpoints from controlled_ablation and
reference_validation; no retraining happens here.
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
from models.chunk_model import ChunkModel, ChunkModelConfig  # noqa: E402
from models.flat_cnn import FlatCNN, FlatCNNConfig, downsample_to_budget  # noqa: E402
from models.forward_fns import chunk_forward, flat_forward  # noqa: E402
from robustness.flooding import build_donor_pool, flood_bytecode  # noqa: E402
from training.calibration import apply_temperature  # noqa: E402
from training.harness import SEEDS, fold_indices  # noqa: E402
from evaluation.metrics import auprc as auprc_fn, metrics_at_threshold  # noqa: E402

RESULTS_DIR = os.path.join(REPO_ROOT, "revision_v3", "results")
CHECKPOINT_DIR = os.path.join(RESULTS_DIR, "checkpoints")

BUDGET_SPECS = [
    {"name": "flat_cnn_2048", "kind": "flat", "budget": 2048},
    {"name": "chunk_attention_2048", "kind": "chunk", "budget": 2048, "max_chunks": 8},
    {"name": "flat_cnn_8192", "kind": "flat", "budget": 8192},
    {"name": "chunk_attention_8192", "kind": "chunk", "budget": 8192, "max_chunks": 32},
    {"name": "flat_cnn_16384", "kind": "flat", "budget": 16384},
    {"name": "chunk_attention_16384", "kind": "chunk", "budget": 16384, "max_chunks": 64,
     "checkpoint_alias": "authguard_reference_v3"},
]


def build_model(spec: dict):
    if spec["kind"] == "flat":
        return FlatCNN(FlatCNNConfig(vocab_size=VOCAB_SIZE, max_len=spec["budget"]))
    return ChunkModel(ChunkModelConfig(
        vocab_size=VOCAB_SIZE, chunk_size=256, max_chunks=spec["max_chunks"], aggregation="attention",
    ))


def score_one(spec: dict, model, device, hex_bc: str) -> tuple[float, int]:
    """Returns (raw_logit, raw_token_count_before_budget_cap)."""
    if spec["kind"] == "flat":
        tokens, _, _ = linear_sweep(normalize_hex(hex_bc))
        ids = tokens_to_ids(tokens)
        arr = downsample_to_budget(ids, spec["budget"])
        batch = {"tokens": torch.as_tensor(arr[None, :].astype(np.int64)).to(device)}
        with torch.no_grad():
            logit = flat_forward(model, batch).cpu().numpy()[0]
        return float(logit), len(tokens)
    else:
        hex_norm = normalize_hex(hex_bc)
        tokens, _, _ = linear_sweep(hex_norm)
        ids = tokens_to_ids(tokens)
        chunks_arr = chunk_token_ids(ids, chunk_size=256, max_chunks=spec["max_chunks"])
        mask_arr = np.ones(len(chunks_arr), dtype=np.bool_)
        chunks = torch.as_tensor(chunks_arr[None, :, :].astype(np.int64)).to(device)
        mask = torch.as_tensor(mask_arr[None, :]).to(device)
        with torch.no_grad():
            logit_t = chunk_forward(model, {"chunks": chunks, "chunk_mask": mask})
        return float(logit_t.cpu().numpy()[0]), len(tokens)


def main() -> int:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[matched_robustness] device={device}", flush=True)

    full_df = pd.read_csv(os.path.join(REPO_ROOT, load_config()["benchmark_csv_gz"]))
    primary_df = load_primary_dataset()
    donor_pool = build_donor_pool(full_df)

    summary_rows = []
    prediction_rows = []
    length_rows = []

    for spec in BUDGET_SPECS:
        ckpt_name = spec.get("checkpoint_alias", spec["name"])
        budget = spec["budget"] if spec["kind"] == "flat" else spec["max_chunks"] * 256

        for seed in SEEDS:
            for test_fold in range(5):
                ckpt_path = os.path.join(CHECKPOINT_DIR, f"{ckpt_name}_seed{seed}_fold{test_fold}.pt")
                if not os.path.exists(ckpt_path):
                    print(f"[matched_robustness] MISSING checkpoint: {ckpt_path} -- skipping", flush=True)
                    continue
                ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
                model = build_model(spec)
                model.load_state_dict(ckpt["model_state_dict"])
                model.to(device).eval()
                temperature = ckpt["temperature"]
                threshold_5pct = ckpt["threshold_5pct"]

                _, _, test_idx, _ = fold_indices(primary_df["fold_id"].to_numpy(), test_fold)
                test_rows = primary_df.iloc[test_idx]

                for _, row in test_rows.iterrows():
                    clean_logit, clean_tok = score_one(spec, model, device, row["runtime_bytecode"])
                    flooded_hex = flood_bytecode(
                        row["runtime_bytecode"], row["sample_id"], row["family_id"],
                        donor_pool, seed=seed, fraction=2.0, condition="flood200",
                    )
                    flood_logit, flood_tok = score_one(spec, model, device, flooded_hex)

                    clean_score = float(apply_temperature(torch.as_tensor(clean_logit), temperature))
                    flood_score = float(apply_temperature(torch.as_tensor(flood_logit), temperature))

                    prediction_rows.append({
                        "model": spec["name"], "seed": seed, "test_fold": test_fold,
                        "sample_id": row["sample_id"], "family_id": row["family_id"],
                        "label": int(row["label"]),
                        "clean_score": clean_score, "flood200_score": flood_score,
                        "threshold_5pct": threshold_5pct,
                    })
                    length_rows.append({
                        "model": spec["name"], "sample_id": row["sample_id"],
                        "clean_token_count": clean_tok, "flood200_token_count": flood_tok,
                        "budget": budget, "exceeds_budget": flood_tok > budget,
                    })
        print(f"[matched_robustness] scored {spec['name']}", flush=True)

    pred_df = pd.DataFrame(prediction_rows)
    pred_df.to_csv(os.path.join(RESULTS_DIR, "matched_robustness_predictions.csv.gz"), index=False, compression="gzip")
    length_df = pd.DataFrame(length_rows)
    length_df.to_csv(os.path.join(RESULTS_DIR, "transformed_length_distribution.csv"), index=False)

    for spec in BUDGET_SPECS:
        sub = pred_df[pred_df["model"] == spec["name"]]
        if len(sub) == 0:
            continue
        row = {"model": spec["name"], "budget": spec["budget"] if spec["kind"] == "flat" else spec["max_chunks"] * 256}
        seed_clean_auprc, seed_flood_auprc = [], []
        seed_clean_recall, seed_flood_recall, seed_flood_fpr = [], [], []
        # Aggregation order matters (the "aggregation trap"): compute each metric PER FOLD
        # first, average over the 5 folds within a seed, THEN average over seeds. Pooling all
        # folds together per seed before computing AUPRC is a different (and wrong) number --
        # this bug was caught by comparing this summary against controlled_ablation_summary.csv
        # for the same model and is intentionally avoided here.
        for seed in SEEDS:
            per_fold_clean_auprc, per_fold_flood_auprc = [], []
            per_fold_clean_recall, per_fold_flood_recall, per_fold_flood_fpr = [], [], []
            for test_fold in sorted(sub["test_fold"].unique()):
                s = sub[(sub["seed"] == seed) & (sub["test_fold"] == test_fold)]
                if len(s) == 0:
                    continue
                y = s["label"].to_numpy()
                per_fold_clean_auprc.append(auprc_fn(y, s["clean_score"].to_numpy()))
                per_fold_flood_auprc.append(auprc_fn(y, s["flood200_score"].to_numpy()))
                clean_m = metrics_at_threshold(y, s["clean_score"].to_numpy(), s["threshold_5pct"].to_numpy())
                flood_m = metrics_at_threshold(y, s["flood200_score"].to_numpy(), s["threshold_5pct"].to_numpy())
                per_fold_clean_recall.append(clean_m["recall"])
                per_fold_flood_recall.append(flood_m["recall"])
                per_fold_flood_fpr.append(flood_m["observed_fpr"])
            seed_clean_auprc.append(np.mean(per_fold_clean_auprc))
            seed_flood_auprc.append(np.mean(per_fold_flood_auprc))
            seed_clean_recall.append(np.mean(per_fold_clean_recall))
            seed_flood_recall.append(np.mean(per_fold_flood_recall))
            seed_flood_fpr.append(np.mean(per_fold_flood_fpr))

        row.update({
            "clean_auprc_mean": float(np.mean(seed_clean_auprc)), "clean_auprc_std": float(np.std(seed_clean_auprc, ddof=1)),
            "flood200_auprc_mean": float(np.mean(seed_flood_auprc)), "flood200_auprc_std": float(np.std(seed_flood_auprc, ddof=1)),
            "absolute_degradation_auprc": float(np.mean(seed_clean_auprc) - np.mean(seed_flood_auprc)),
            "clean_recall_at_5pct_mean": float(np.mean(seed_clean_recall)),
            "flood200_recall_at_frozen_threshold_mean": float(np.mean(seed_flood_recall)),
            "flood200_observed_fpr_mean": float(np.mean(seed_flood_fpr)),
            "pct_flooded_exceeding_budget": float(
                length_df[length_df["model"] == spec["name"]]["exceeds_budget"].mean() * 100
            ),
        })
        summary_rows.append(row)

    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(os.path.join(RESULTS_DIR, "matched_robustness_summary.csv"), index=False)
    print(summary_df.to_string())
    print("[matched_robustness] DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
