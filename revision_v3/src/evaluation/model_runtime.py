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
from data.loader import canonical_family_ids, family_to_fold_map  # noqa: E402

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


def _load_checkpoint_model(model_name: str, seed: int, test_fold: int, device):
    """Load one checkpoint and verify that its embedded split provenance matches its name."""
    spec = MODEL_REGISTRY[model_name]
    ckpt_path = os.path.join(
        spec["checkpoint_dir"], f"{model_name}_seed{seed}_fold{test_fold}.pt"
    )
    if not os.path.exists(ckpt_path):
        raise FileNotFoundError(ckpt_path)
    ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
    if int(ckpt.get("seed", seed)) != seed or int(ckpt.get("test_fold", test_fold)) != test_fold:
        raise ValueError(
            f"checkpoint provenance mismatch for {ckpt_path}: "
            f"embedded seed={ckpt.get('seed')} test_fold={ckpt.get('test_fold')}"
        )
    model = build_model(spec)
    model.load_state_dict(ckpt["model_state_dict"])
    model.to(device).eval()
    return spec, model, ckpt


def score_dataset_out_of_fold(model_name: str, bytecodes: list[str], fold_ids,
                              device=None) -> tuple[dict[int, np.ndarray],
                                                   dict[int, np.ndarray]]:
    """Score benchmark members using only their family's held-out-test checkpoint.

    Returns ``(scores_by_seed, thresholds_by_seed)``.  Each threshold array is item-aligned:
    the value for an item comes from the same fold checkpoint that produced its score.  This
    prevents both training leakage and the subtler error of applying an average threshold from
    checkpoints with different validation populations.
    """
    if model_name not in MODEL_REGISTRY:
        raise ValueError(f"unknown model_name {model_name!r}; known: {list(MODEL_REGISTRY)}")
    folds = np.asarray(list(fold_ids), dtype=np.int64)
    if len(bytecodes) != len(folds):
        raise ValueError(f"bytecodes/fold_ids length mismatch: {len(bytecodes)} != {len(folds)}")
    if np.any((folds < 0) | (folds >= 5)):
        raise ValueError(f"fold_ids must be in [0, 4], got {sorted(set(folds.tolist()))}")
    device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")

    scores_by_seed: dict[int, np.ndarray] = {}
    thresholds_by_seed: dict[int, np.ndarray] = {}
    for seed in SEEDS:
        scores = np.empty(len(bytecodes), dtype=np.float64)
        thresholds = np.empty(len(bytecodes), dtype=np.float64)
        for test_fold in sorted(set(folds.tolist())):
            item_indices = np.flatnonzero(folds == test_fold)
            spec, model, ckpt = _load_checkpoint_model(model_name, seed, test_fold, device)
            temperature = ckpt["temperature"]
            for index in item_indices:
                raw_logit = score_one(spec, model, device, bytecodes[int(index)])
                scores[index] = float(
                    apply_temperature(torch.as_tensor(raw_logit), temperature)
                )
                thresholds[index] = float(ckpt["threshold_5pct"])
        scores_by_seed[seed] = scores
        thresholds_by_seed[seed] = thresholds
    return scores_by_seed, thresholds_by_seed


def score_dataset_with_ensemble(model_name: str, bytecodes: list[str], device=None,
                                *, external_only: bool = False) -> dict[int, np.ndarray]:
    """Score genuinely external bytecodes with all five fold checkpoints per seed.

    This API is intentionally opt-in.  Gold-Dev, Gold-Test, Pilot, and any control/temporal
    bytecode belonging to a canonical benchmark family must use
    :func:`score_dataset_out_of_fold`.  An all-fold ensemble would otherwise contain three
    checkpoints that trained on each benchmark family.

    Returns {seed: np.ndarray of shape (len(bytecodes),)} -- the per-seed calibrated-score
    array format expected by evaluation.bootstrap_v2.seed_aware_paired_bootstrap_ci.
    """
    if not external_only:
        raise ValueError(
            "all-fold ensembling is valid only for verified external families; pass "
            "external_only=True after checking provenance, or use score_dataset_out_of_fold"
        )
    if model_name not in MODEL_REGISTRY:
        raise ValueError(f"unknown model_name {model_name!r}; known: {list(MODEL_REGISTRY)}")
    spec = MODEL_REGISTRY[model_name]
    device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")

    scores_by_seed: dict[int, list[np.ndarray]] = {seed: [] for seed in SEEDS}
    n_missing = 0
    for seed in SEEDS:
        for test_fold in range(5):
            try:
                _, model, ckpt = _load_checkpoint_model(model_name, seed, test_fold, device)
            except FileNotFoundError:
                n_missing += 1
                continue
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


def score_dataset_provenance_aware(model_name: str, bytecodes: list[str], family_ids,
                                   device=None) -> dict:
    """Score a mixture of canonical-family and genuinely external bytecodes safely.

    A family in the primary training population is scored by exactly the checkpoint holding
    it out. A family appearing only in a frozen non-primary population was absent from all
    training folds and may use the five-fold ensemble, as may an empty/``None`` family after
    explicit upstream provenance matching. Unknown non-empty identifiers are rejected instead
    of silently being treated as external.

    ``decision_fraction`` is the fraction of eligible checkpoints whose calibrated score meets
    *that checkpoint's own* validation-derived threshold.  It is the appropriate operating
    statistic for mixed-provenance controls; the mean external score must not be compared with
    an averaged threshold as though that threshold had itself been calibrated.
    """
    if model_name not in MODEL_REGISTRY:
        raise ValueError(f"unknown model_name {model_name!r}; known: {list(MODEL_REGISTRY)}")
    families = [None if value is None or str(value).strip() == "" else str(value).strip()
                for value in family_ids]
    if len(bytecodes) != len(families):
        raise ValueError(
            f"bytecodes/family_ids length mismatch: {len(bytecodes)} != {len(families)}"
        )
    canonical = family_to_fold_map()
    all_canonical_families = canonical_family_ids()
    unknown = sorted({family for family in families
                      if family is not None and family not in all_canonical_families})
    if unknown:
        raise KeyError(
            "non-empty family IDs are not in the canonical primary population: "
            + ", ".join(unknown[:10])
        )

    device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
    n_items = len(bytecodes)
    scores_by_seed = {seed: np.empty(n_items, dtype=np.float64) for seed in SEEDS}
    thresholds_by_seed = {seed: np.empty(n_items, dtype=np.float64) for seed in SEEDS}
    decision_votes: list[list[bool]] = [[] for _ in bytecodes]
    sources = ["" for _ in bytecodes]

    known_indices = [i for i, family in enumerate(families) if family in canonical]
    if known_indices:
        known_bytecodes = [bytecodes[i] for i in known_indices]
        known_folds = [canonical[families[i]] for i in known_indices]
        known_scores, known_thresholds = score_dataset_out_of_fold(
            model_name, known_bytecodes, known_folds, device=device
        )
        for seed in SEEDS:
            for local_i, global_i in enumerate(known_indices):
                score = float(known_scores[seed][local_i])
                threshold = float(known_thresholds[seed][local_i])
                scores_by_seed[seed][global_i] = score
                thresholds_by_seed[seed][global_i] = threshold
                decision_votes[global_i].append(score >= threshold)
                sources[global_i] = (
                    f"canonical_family_oof:test_fold={known_folds[local_i]}"
                )

    external_indices = [i for i, family in enumerate(families) if family not in canonical]
    if external_indices:
        spec = MODEL_REGISTRY[model_name]
        external_bytecodes = [bytecodes[i] for i in external_indices]
        for seed in SEEDS:
            fold_scores = []
            fold_thresholds = []
            for test_fold in range(5):
                _, model, ckpt = _load_checkpoint_model(model_name, seed, test_fold, device)
                temperature = ckpt["temperature"]
                scores = np.array([
                    float(apply_temperature(
                        torch.as_tensor(score_one(spec, model, device, bytecode)), temperature
                    ))
                    for bytecode in external_bytecodes
                ], dtype=np.float64)
                threshold = float(ckpt["threshold_5pct"])
                fold_scores.append(scores)
                fold_thresholds.append(threshold)
                for local_i, global_i in enumerate(external_indices):
                    decision_votes[global_i].append(float(scores[local_i]) >= threshold)
            mean_scores = np.mean(np.stack(fold_scores, axis=0), axis=0)
            mean_threshold = float(np.mean(fold_thresholds))
            for local_i, global_i in enumerate(external_indices):
                scores_by_seed[seed][global_i] = mean_scores[local_i]
                # Descriptive only. Operating decisions use decision_fraction below.
                thresholds_by_seed[seed][global_i] = mean_threshold
                family = families[global_i]
                sources[global_i] = (
                    "canonical_non_primary:five_fold_ensemble"
                    if family is not None else "verified_external:five_fold_ensemble"
                )

    return {
        "scores_by_seed": scores_by_seed,
        "thresholds_by_seed": thresholds_by_seed,
        "decision_fraction": np.asarray(
            [np.mean(votes) if votes else np.nan for votes in decision_votes], dtype=np.float64
        ),
        "score_source_by_item": sources,
        "n_canonical_family_items": len(known_indices),
        "n_canonical_non_primary_items": sum(
            families[index] is not None for index in external_indices
        ),
        "n_verified_external_items": sum(
            families[index] is None for index in external_indices
        ),
        "decision_rule": (
            "fraction of eligible checkpoints with calibrated score >= that checkpoint's "
            "own validation-derived 5%-FPR threshold"
        ),
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
