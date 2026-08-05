"""Phase 2, Part 3: final paper-grade matched-budget Flood-200% evaluation.

Uses the executable-region-aware, multi-donor flooding_v2 reimplementation, 3 independent
transformation seeds per recipient (to measure donor-selection variance, independent of
model-training seed), on 5 models at their native 16,384-token budget: authguard_reference_v3,
chunk_max_16384, authguard_sequence_dense, the parameter-matched Flat CNN, and the original
(large) Flat CNN. All models are scored from already-trained Phase 1 / Phase 2 Part 2
checkpoints -- no retraining. Writes exclusively under revision_v3/results/final_robustness/.
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
from features.encode import VOCAB_SIZE, chunk_token_ids, encode_bytecode, tokens_to_ids  # noqa: E402
from models.chunk_model import ChunkModel, ChunkModelConfig  # noqa: E402
from models.flat_cnn import FlatCNN, FlatCNNConfig, downsample_to_budget  # noqa: E402
from models.forward_fns import chunk_forward, flat_forward, hybrid_forward  # noqa: E402
from models.hybrid import HybridConfig, HybridModel  # noqa: E402
from robustness.flooding_v2 import build_donor_pool_v2, flood_bytecode_v2  # noqa: E402
from training.calibration import apply_temperature  # noqa: E402
from training.harness import SEEDS, fold_indices  # noqa: E402
from evaluation.metrics import auprc as auprc_fn, metrics_at_threshold  # noqa: E402

RESULTS_DIR = os.path.join(REPO_ROOT, "revision_v3", "results", "final_robustness")
os.makedirs(RESULTS_DIR, exist_ok=True)
PHASE1_CKPT_DIR = os.path.join(REPO_ROOT, "revision_v3", "results", "checkpoints")
PHASE2_CKPT_DIR = os.path.join(REPO_ROOT, "revision_v3", "results", "parameter_matched", "checkpoints")

TRANSFORM_SEEDS = (1, 2, 3)

MODEL_SPECS = [
    {"name": "authguard_reference_v3", "kind": "chunk", "checkpoint_dir": PHASE1_CKPT_DIR},
    {"name": "chunk_max_16384", "kind": "chunk", "checkpoint_dir": PHASE1_CKPT_DIR},
    {"name": "authguard_sequence_dense", "kind": "hybrid", "checkpoint_dir": PHASE1_CKPT_DIR},
    {"name": "flat_cnn_matched_16384", "kind": "flat_matched", "checkpoint_dir": PHASE2_CKPT_DIR},
    {"name": "flat_cnn_16384", "kind": "flat", "checkpoint_dir": PHASE1_CKPT_DIR},
]


def build_model(spec):
    if spec["kind"] == "flat":
        return FlatCNN(FlatCNNConfig(vocab_size=VOCAB_SIZE, max_len=16384))
    if spec["kind"] == "flat_matched":
        return FlatCNN(FlatCNNConfig(vocab_size=VOCAB_SIZE, max_len=16384, embedding_dim=32, channels=60))
    if spec["kind"] == "hybrid":
        return HybridModel(HybridConfig(vocab_size=VOCAB_SIZE, chunk_size=256, max_chunks=64, use_dense=True))
    aggregation = "max" if spec["name"] == "chunk_max_16384" else "attention"
    return ChunkModel(ChunkModelConfig(vocab_size=VOCAB_SIZE, chunk_size=256, max_chunks=64, aggregation=aggregation))


def score_one(spec, model, device, hex_bc: str) -> float:
    if spec["kind"] in ("flat", "flat_matched"):
        tokens, _, _ = linear_sweep(normalize_hex(hex_bc))
        ids = tokens_to_ids(tokens)
        arr = downsample_to_budget(ids, 16384)
        batch = {"tokens": torch.as_tensor(arr[None, :].astype(np.int64)).to(device)}
        with torch.no_grad():
            logit = flat_forward(model, batch).cpu().numpy()[0]
        return float(logit)
    if spec["kind"] == "hybrid":
        enc = encode_bytecode(hex_bc, chunk_size=256, max_chunks=64)
        chunks = torch.as_tensor(enc.chunks[None, :, :].astype(np.int64)).to(device)
        mask = torch.as_tensor(enc.chunk_mask[None, :]).to(device)
        dense = torch.as_tensor(enc.dense[None, :]).to(device)
        with torch.no_grad():
            logit = hybrid_forward(model, {"chunks": chunks, "chunk_mask": mask, "dense": dense})
        return float(logit.cpu().numpy()[0])
    hex_norm = normalize_hex(hex_bc)
    tokens, _, _ = linear_sweep(hex_norm)
    ids = tokens_to_ids(tokens)
    chunks_arr = chunk_token_ids(ids, chunk_size=256, max_chunks=64)
    mask_arr = np.ones(len(chunks_arr), dtype=np.bool_)
    chunks = torch.as_tensor(chunks_arr[None, :, :].astype(np.int64)).to(device)
    mask = torch.as_tensor(mask_arr[None, :]).to(device)
    with torch.no_grad():
        logit_t = chunk_forward(model, {"chunks": chunks, "chunk_mask": mask})
    return float(logit_t.cpu().numpy()[0])


def main() -> int:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[final_robustness] device={device}", flush=True)

    full_df = pd.read_csv(os.path.join(REPO_ROOT, load_config()["benchmark_csv_gz"]))
    primary_df = load_primary_dataset()
    donor_pool = build_donor_pool_v2(full_df)

    prediction_rows = []
    provenance_rows = []

    for spec in MODEL_SPECS:
        for seed in SEEDS:
            for test_fold in range(5):
                ckpt_path = os.path.join(spec["checkpoint_dir"], f"{spec['name']}_seed{seed}_fold{test_fold}.pt")
                if not os.path.exists(ckpt_path):
                    print(f"[final_robustness] MISSING {ckpt_path}", flush=True)
                    continue
                ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
                model = build_model(spec)
                model.load_state_dict(ckpt["model_state_dict"])
                model.to(device).eval()
                temperature = ckpt["temperature"]
                threshold_5pct = ckpt["threshold_5pct"]

                _, _, test_idx, _ = fold_indices(primary_df["fold_id"].to_numpy(), test_fold)
                for _, row in primary_df.iloc[test_idx].iterrows():
                    clean_logit = score_one(spec, model, device, row["runtime_bytecode"])
                    clean_score = float(apply_temperature(torch.as_tensor(clean_logit), temperature))

                    flood_scores = []
                    for t_seed in TRANSFORM_SEEDS:
                        flooded_hex, prov = flood_bytecode_v2(
                            row["runtime_bytecode"], row["sample_id"], row["family_id"],
                            donor_pool, model_seed=seed, transform_seed=t_seed, fraction=2.0,
                        )
                        flood_logit = score_one(spec, model, device, flooded_hex)
                        flood_score = float(apply_temperature(torch.as_tensor(flood_logit), temperature))
                        flood_scores.append(flood_score)
                        if spec is MODEL_SPECS[0] and seed == SEEDS[0] and test_fold == 0:
                            provenance_rows.append(prov)

                    prediction_rows.append({
                        "model": spec["name"], "seed": seed, "test_fold": test_fold,
                        "sample_id": row["sample_id"], "family_id": row["family_id"], "label": int(row["label"]),
                        "clean_score": clean_score,
                        "flood_score_t1": flood_scores[0], "flood_score_t2": flood_scores[1], "flood_score_t3": flood_scores[2],
                        "flood_score_mean": float(np.mean(flood_scores)),
                        "flood_score_std_across_transform_seeds": float(np.std(flood_scores, ddof=1)),
                        "threshold_5pct": threshold_5pct,
                    })
        print(f"[final_robustness] scored {spec['name']}", flush=True)

    pred_df = pd.DataFrame(prediction_rows)
    pred_df.to_csv(os.path.join(RESULTS_DIR, "final_robustness_predictions.csv.gz"), index=False, compression="gzip")
    with open(os.path.join(RESULTS_DIR, "donor_provenance_sample.json"), "w") as f:
        json.dump(provenance_rows[:50], f, indent=2, default=str)

    print("[final_robustness] DONE scoring, computing summary...", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
