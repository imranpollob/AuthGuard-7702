"""Independent Revision v3 training/evaluation harness.

Protocol (fixed, matches the canonical Revision v2 protocol so results are comparable):
- 5 stored family-disjoint outer folds; test = fold f, validation = fold (f+1) % 5,
  training = the remaining 3 folds.
- seeds 7702, 7703, 7704 (actual seed used for a given fold is `seed + fold`).
- class-weighted BCE-with-logits (pos_weight = n_neg/n_pos on the train fold).
- AdamW, lr=1e-3, weight_decay=1e-4, gradient-norm clip 5.0, batch size 16.
- early stopping on validation AUPRC, patience 5, max 30 epochs.
- temperature scaling fit on validation logits only.
- nominal 1%/5%/10% FPR thresholds derived from validation negatives only.
- test labels are never used for training, calibration, or threshold selection.
- aggregation: metrics computed per fold -> averaged over the 5 folds within a seed ->
  mean and sample standard deviation across the 3 seed-level means (never pooled).
"""
from __future__ import annotations

import copy
import os
import sys
import time

import numpy as np
import pandas as pd
import torch
from torch import nn

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "revision_v3", "src"))

from evaluation.metrics import full_metrics  # noqa: E402
from training.calibration import apply_temperature, fit_temperature  # noqa: E402

# Two independent runs of authguard_reference_v3 under nominally identical seeds produced
# AUPRC 0.9216/0.9180 and Recall@5% 0.8522/0.8583 -- a ~0.006-0.007 swing purely from
# non-deterministic GPU convolution kernels (cuDNN algorithm selection is not seed-controlled
# by torch.manual_seed alone). Since the protocol names explicit seeds (7702/7703/7704), a
# seed should reproduce its own run; forcing deterministic algorithms below closes that gap
# (see REFERENCE_VALIDATION_REPORT.md for the before/after comparison).
torch.backends.cudnn.deterministic = True
torch.backends.cudnn.benchmark = False

SEEDS = (7702, 7703, 7704)
N_FOLDS = 5
BATCH_SIZE = 16
LR = 1e-3
WEIGHT_DECAY = 1e-4
GRAD_CLIP = 5.0
MAX_EPOCHS = 30
PATIENCE = 5


def fold_indices(fold_id: np.ndarray, test_fold: int, n_folds: int = N_FOLDS):
    val_fold = (test_fold + 1) % n_folds
    test_idx = np.where(fold_id == test_fold)[0]
    val_idx = np.where(fold_id == val_fold)[0]
    train_idx = np.where(~np.isin(fold_id, [test_fold, val_fold]))[0]
    return train_idx, val_idx, test_idx, val_fold


def make_batches(n: int, batch_size: int, rng: np.random.Generator, shuffle: bool):
    order = rng.permutation(n) if shuffle else np.arange(n)
    for start in range(0, n, batch_size):
        yield order[start:start + batch_size]


EVAL_BATCH_SIZE = 32


@torch.no_grad()
def score_indices(model: nn.Module, forward_fn, tensors: dict, idx: np.ndarray, device: torch.device) -> np.ndarray:
    """Batched scoring (never the whole fold in one forward pass) -- a single unbatched
    forward over ~450 rows at a 16,384-token budget can exceed GPU memory (observed: CUDA OOM
    on flat_cnn_16384 before this fix)."""
    model.eval()
    outputs = []
    for start in range(0, len(idx), EVAL_BATCH_SIZE):
        chunk_idx = idx[start:start + EVAL_BATCH_SIZE]
        batch = {k: torch.as_tensor(v[chunk_idx]).to(device) for k, v in tensors.items()
                 if k not in ("labels", "family_id", "fold_id", "sample_id")}
        outputs.append(forward_fn(model, batch).cpu().numpy())
    return np.concatenate(outputs)


def train_one_model(
    model: nn.Module,
    forward_fn,
    tensors: dict,
    train_idx: np.ndarray,
    val_idx: np.ndarray,
    device: torch.device,
    seed: int,
) -> nn.Module:
    torch.manual_seed(seed)
    model.to(device)

    labels_np = tensors["labels"]
    n_pos = max(1, int(labels_np[train_idx].sum()))
    n_neg = max(1, int(len(train_idx) - n_pos))
    pos_weight = torch.tensor([n_neg / n_pos], dtype=torch.float32, device=device)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    optimizer = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)

    rng = np.random.default_rng(seed)
    best_val_auprc = -1.0
    best_state = copy.deepcopy(model.state_dict())
    epochs_without_improve = 0

    for epoch in range(MAX_EPOCHS):
        model.train()
        for batch_idx in make_batches(len(train_idx), BATCH_SIZE, rng, shuffle=True):
            idx = train_idx[batch_idx]
            batch = {k: torch.as_tensor(v[idx]).to(device) for k, v in tensors.items()
                     if k not in ("labels", "family_id", "fold_id", "sample_id")}
            labels = torch.as_tensor(labels_np[idx], dtype=torch.float32, device=device)
            optimizer.zero_grad()
            logits = forward_fn(model, batch)
            loss = loss_fn(logits, labels)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), GRAD_CLIP)
            optimizer.step()

        val_logits = score_indices(model, forward_fn, tensors, val_idx, device)
        val_labels = labels_np[val_idx]
        from evaluation.metrics import auprc as _auprc
        val_auprc = _auprc(val_labels, val_logits)

        if val_auprc > best_val_auprc:
            best_val_auprc = val_auprc
            best_state = copy.deepcopy(model.state_dict())
            epochs_without_improve = 0
        else:
            epochs_without_improve += 1
            if epochs_without_improve >= PATIENCE:
                break

    model.load_state_dict(best_state)
    return model


def run_full_protocol(
    model_name: str,
    build_model_fn,
    forward_fn,
    tensors: dict,
    results_dir: str,
    device: torch.device,
    seeds=SEEDS,
    n_folds: int = N_FOLDS,
    checkpoint_dir: str | None = None,
) -> dict:
    """Runs the complete canonical protocol for one model spec; writes per-fold-seed
    results, per-observation predictions, and a final summary; returns the summary dict."""
    os.makedirs(results_dir, exist_ok=True)
    fold_seed_rows = []
    prediction_rows = []

    labels_np = tensors["labels"]

    for seed in seeds:
        for test_fold in range(n_folds):
            t0 = time.time()
            train_idx, val_idx, test_idx, val_fold = fold_indices(tensors["fold_id"], test_fold, n_folds)
            fold_seed = seed + test_fold

            model = build_model_fn()
            model = train_one_model(model, forward_fn, tensors, train_idx, val_idx, device, seed=fold_seed)

            val_logits = torch.as_tensor(score_indices(model, forward_fn, tensors, val_idx, device))
            val_labels_t = torch.as_tensor(labels_np[val_idx], dtype=torch.float32)
            temperature = fit_temperature(val_logits, val_labels_t)

            val_calibrated = apply_temperature(val_logits, temperature).numpy()
            test_logits = score_indices(model, forward_fn, tensors, test_idx, device)
            test_calibrated = apply_temperature(torch.as_tensor(test_logits), temperature).numpy()

            m = full_metrics(labels_np[test_idx], test_calibrated, val_calibrated, labels_np[val_idx])
            m.update({
                "model": model_name, "seed": seed, "test_fold": test_fold, "val_fold": val_fold,
                "temperature": temperature, "n_train": len(train_idx), "n_val": len(val_idx),
                "n_test": len(test_idx), "wall_seconds": time.time() - t0,
            })
            fold_seed_rows.append(m)

            if checkpoint_dir is not None:
                os.makedirs(checkpoint_dir, exist_ok=True)
                ckpt_path = os.path.join(checkpoint_dir, f"{model_name}_seed{seed}_fold{test_fold}.pt")
                torch.save({
                    "model_state_dict": model.state_dict(),
                    "temperature": temperature,
                    "seed": seed, "test_fold": test_fold, "val_fold": val_fold,
                    "threshold_5pct": m.get("threshold_5pct"),
                }, ckpt_path)

            for i, row_idx in enumerate(test_idx):
                prediction_rows.append({
                    "model": model_name, "seed": seed, "test_fold": test_fold,
                    "sample_id": tensors["sample_id"][row_idx],
                    "family_id": tensors["family_id"][row_idx],
                    "label": int(labels_np[row_idx]),
                    "raw_score": float(torch.sigmoid(torch.as_tensor(test_logits[i])).item()),
                    "calibrated_score": float(test_calibrated[i]),
                })

    fold_seed_df = pd.DataFrame(fold_seed_rows)
    fold_seed_df.to_csv(os.path.join(results_dir, f"{model_name}_fold_seed.csv"), index=False)
    pred_df = pd.DataFrame(prediction_rows)
    pred_df.to_csv(os.path.join(results_dir, f"{model_name}_predictions.csv.gz"), index=False, compression="gzip")

    metric_cols = [c for c in fold_seed_df.columns if c not in
                   ("model", "seed", "test_fold", "val_fold", "n_train", "n_val", "n_test", "wall_seconds")]
    per_seed = fold_seed_df.groupby("seed")[metric_cols].mean()
    summary = {"model": model_name}
    for col in metric_cols:
        summary[f"{col}_mean"] = float(per_seed[col].mean())
        summary[f"{col}_std"] = float(per_seed[col].std(ddof=1)) if len(per_seed) > 1 else 0.0
    summary["n_seeds"] = len(seeds)
    summary["n_folds"] = n_folds
    summary["total_wall_seconds"] = float(fold_seed_df["wall_seconds"].sum())
    return summary
