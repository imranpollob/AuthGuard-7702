"""Reusable "load checkpoint(s) + score raw bytecode" runtime, generalized from the inline
pattern duplicated across revision_v3/experiments/{final_robustness,parameter_matched,
matched_robustness}/*.py. Used by the Part 6/7/8/9/14 provisional-pipeline scripts so that
model-loading/scoring logic exists in exactly one place.

Does not modify any existing experiment script or checkpoint file -- purely additive.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import torch

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "revision_v3", "src"))

from features.disassembler import linear_sweep, normalize_hex  # noqa: E402
from features.encode import VOCAB_SIZE, chunk_token_ids, encode_bytecode, tokens_to_ids  # noqa: E402
from models.chunk_model import ChunkModel, ChunkModelConfig  # noqa: E402
from models.flat_cnn import FlatCNN, FlatCNNConfig, downsample_to_budget  # noqa: E402
from models.forward_fns import chunk_forward, flat_forward, hybrid_forward  # noqa: E402
from models.hybrid import HybridConfig, HybridModel  # noqa: E402
from training.calibration import apply_temperature  # noqa: E402
from training.harness import SEEDS  # noqa: E402

PHASE1_CKPT_DIR = os.path.join(REPO_ROOT, "revision_v3", "results", "checkpoints")
PHASE2_MATCHED_CKPT_DIR = os.path.join(REPO_ROOT, "revision_v3", "results", "parameter_matched", "checkpoints")

# Canonical registry of every model this provisional pipeline evaluates. "kind" selects the
# build_model()/score_one() branch; "checkpoint_dir" + "name" determine the 15
# (3 seeds x 5 folds) checkpoint files.
MODEL_REGISTRY = {
    "authguard_sequence_dense": {"kind": "hybrid", "checkpoint_dir": PHASE1_CKPT_DIR},
    "authguard_reference_v3": {"kind": "chunk", "checkpoint_dir": PHASE1_CKPT_DIR, "aggregation": "attention"},
    "flat_cnn_matched_16384": {"kind": "flat_matched", "checkpoint_dir": PHASE2_MATCHED_CKPT_DIR},
    "flat_cnn_16384": {"kind": "flat", "checkpoint_dir": PHASE1_CKPT_DIR},
}


def build_model(spec: dict):
    if spec["kind"] == "flat":
        return FlatCNN(FlatCNNConfig(vocab_size=VOCAB_SIZE, max_len=16384))
    if spec["kind"] == "flat_matched":
        return FlatCNN(FlatCNNConfig(vocab_size=VOCAB_SIZE, max_len=16384, embedding_dim=32, channels=60))
    if spec["kind"] == "hybrid":
        return HybridModel(HybridConfig(vocab_size=VOCAB_SIZE, chunk_size=256, max_chunks=64, use_dense=True))
    aggregation = spec.get("aggregation", "attention")
    return ChunkModel(ChunkModelConfig(vocab_size=VOCAB_SIZE, chunk_size=256, max_chunks=64, aggregation=aggregation))


def score_one(spec: dict, model, device, hex_bc: str) -> float:
    """Raw (uncalibrated) logit for one bytecode string."""
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


def score_dataset_with_ensemble(model_name: str, bytecodes: list[str], device=None) -> dict[int, np.ndarray]:
    """Scores every bytecode string in `bytecodes` with all 5 fold-checkpoints for each of the
    3 training seeds, temperature-calibrates each, and averages across folds within a seed
    (since none of Gold-Dev/Gold-Test/Pilot/temporal items were in any training fold, using
    all 5 fold-checkpoints per seed is a valid ensemble, not a leakage risk).

    Returns {seed: np.ndarray of shape (len(bytecodes),)} -- the per-seed calibrated-score
    array format expected by evaluation.bootstrap_v2.seed_aware_paired_bootstrap_ci.
    """
    if model_name not in MODEL_REGISTRY:
        raise ValueError(f"unknown model_name {model_name!r}; known: {list(MODEL_REGISTRY)}")
    spec = MODEL_REGISTRY[model_name]
    device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")

    scores_by_seed: dict[int, list[np.ndarray]] = {seed: [] for seed in SEEDS}
    n_missing = 0
    for seed in SEEDS:
        for test_fold in range(5):
            ckpt_path = os.path.join(spec["checkpoint_dir"], f"{model_name}_seed{seed}_fold{test_fold}.pt")
            if not os.path.exists(ckpt_path):
                n_missing += 1
                continue
            ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
            model = build_model(spec)
            model.load_state_dict(ckpt["model_state_dict"])
            model.to(device).eval()
            temperature = ckpt["temperature"]
            fold_scores = np.array([
                float(apply_temperature(torch.as_tensor(score_one(spec, model, device, bc)), temperature))
                for bc in bytecodes
            ], dtype=np.float64)
            scores_by_seed[seed].append(fold_scores)

    if n_missing:
        print(f"[model_runtime] WARNING: {n_missing}/15 checkpoints missing for {model_name}")

    return {
        seed: np.mean(np.stack(fold_list, axis=0), axis=0)
        for seed, fold_list in scores_by_seed.items() if fold_list
    }


def score_dataset_single_checkpoint(model_name: str, seed: int, test_fold: int,
                                     bytecodes: list[str], device=None) -> tuple[np.ndarray, dict]:
    """Scores with exactly one (seed, fold) checkpoint -- used by retraining/fine-tuning
    experiments that need a single starting point rather than the full 15-checkpoint ensemble."""
    spec = MODEL_REGISTRY[model_name]
    device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ckpt_path = os.path.join(spec["checkpoint_dir"], f"{model_name}_seed{seed}_fold{test_fold}.pt")
    ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
    model = build_model(spec)
    model.load_state_dict(ckpt["model_state_dict"])
    model.to(device).eval()
    scores = np.array([
        float(apply_temperature(torch.as_tensor(score_one(spec, model, device, bc)), ckpt["temperature"]))
        for bc in bytecodes
    ], dtype=np.float64)
    return scores, ckpt
