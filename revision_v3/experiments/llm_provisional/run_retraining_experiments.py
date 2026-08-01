"""Part 7: provisional retraining/fine-tuning experiments using ONLY provisional Gold-Dev
labels (never Gold-Test). Starts every method from the same frozen Phase 2
authguard_sequence_dense checkpoint (seed7702_fold0) so methods are compared on equal
footing, then fine-tunes on Gold-Dev's 47 binary-labeled items under a family-grouped
3-fold split (46/47 items are already singleton families -- this is effectively a plain
3-fold CV, verified below) x 3 seeds = 9 runs per method. Given the very small sample size
(47 items), results are reported with explicit stability (std across the 9 runs) rather than
a single point estimate, and should be read as a methodological exercise, not as a claim of
a materially improved model from 47 examples.

Does not modify any Phase 1/2 checkpoint or result file -- every fine-tuned model is a new,
separate in-memory copy; nothing is written back to revision_v3/results/checkpoints/.

LABEL_SOURCE=LLM_PROVISIONAL
STATUS=PROVISIONAL_NOT_FOR_FINAL_CLAIMS

Usage:
    python3 revision_v3/experiments/llm_provisional/run_retraining_experiments.py
"""
from __future__ import annotations

import copy
import csv
import json
import os
import sys

import numpy as np
import torch
from torch import nn

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "revision_v3", "src"))

from evaluation import model_runtime  # noqa: E402
from evaluation.metrics import auprc as auprc_fn, metrics_at_threshold, threshold_at_nominal_fpr  # noqa: E402
from features.encode import encode_bytecode  # noqa: E402
from models.hybrid import HybridConfig, HybridModel  # noqa: E402
from training.harness import SEEDS  # noqa: E402

HUMAN_EVAL_DIR = os.path.join(REPO_ROOT, "revision_v3", "human_eval")
RESULTS_DIR = os.path.join(REPO_ROOT, "revision_v3", "results", "llm_provisional", "retraining")
os.makedirs(RESULTS_DIR, exist_ok=True)
BASE_CKPT = os.path.join(REPO_ROOT, "revision_v3", "results", "checkpoints",
                          "authguard_sequence_dense_seed7702_fold0.pt")
N_INNER_FOLDS = 3
MAX_EPOCHS = 15
PATIENCE = 3
LR = 1e-3
WEIGHT_DECAY = 1e-4
GRAD_CLIP = 5.0

CONFIDENCE_WEIGHT = {"high": 1.0, "medium": 0.66, "low": 0.33}
SOFT_TARGET = {
    ("UNSAFE", "high"): 0.92, ("UNSAFE", "medium"): 0.78, ("UNSAFE", "low"): 0.65,
    ("SAFE", "high"): 0.08, ("SAFE", "medium"): 0.22, ("SAFE", "low"): 0.35,
}


def load_gold_dev_binary():
    with open(os.path.join(HUMAN_EVAL_DIR, "gold_dev_manifest.csv"), newline="") as f:
        manifest = {r["item_id"]: r for r in csv.DictReader(f)}
    with open(os.path.join(REPO_ROOT, "revision_v3", "results", "llm_provisional", "gold_dev_labels.json")) as f:
        labels = {r["item_id"]: r for r in json.load(f)["records"]}
    binary_ids = [iid for iid, r in labels.items() if r["llm_provisional_label"] in ("SAFE", "UNSAFE")]
    uncertain_ids = [iid for iid, r in labels.items() if r["llm_provisional_label"] == "UNCERTAIN"]
    return manifest, labels, binary_ids, uncertain_ids


def build_tensors(item_ids, manifest, labels):
    chunks_list, mask_list, dense_list = [], [], []
    hard_labels, soft_labels, conf_weights, families = [], [], [], []
    for iid in item_ids:
        enc = encode_bytecode(manifest[iid]["runtime_bytecode"], chunk_size=256, max_chunks=64)
        n_chunks = enc.chunks.shape[0]
        padded = np.zeros((64, 256), dtype=np.int64)
        padded[:min(n_chunks, 64)] = enc.chunks[:64]
        mask = np.zeros(64, dtype=np.bool_)
        mask[:min(n_chunks, 64)] = True
        chunks_list.append(padded)
        mask_list.append(mask)
        dense_list.append(enc.dense)

        rec = labels[iid]
        y = 1.0 if rec["llm_provisional_label"] == "UNSAFE" else 0.0
        hard_labels.append(y)
        conf = rec["llm_provisional_confidence"]
        conf_weights.append(CONFIDENCE_WEIGHT.get(conf, 0.5))
        soft_labels.append(SOFT_TARGET.get((rec["llm_provisional_label"], conf), y))
        families.append(manifest[iid]["family_id"])

    return {
        "chunks": np.stack(chunks_list), "chunk_mask": np.stack(mask_list),
        "dense": np.stack(dense_list), "labels": np.array(hard_labels, dtype=np.float32),
        "soft_labels": np.array(soft_labels, dtype=np.float32),
        "confidence_weight": np.array(conf_weights, dtype=np.float32),
        "family_id": np.array(families),
        "source_rule_label": np.array([float(manifest[iid].get("source_label", 0)) for iid in item_ids], dtype=np.float32),
        "item_id": np.array(item_ids),
    }


def group_kfold_indices(family_ids: np.ndarray, n_splits: int, seed: int):
    """Small, dependency-free grouped K-fold: shuffles unique groups, deals them round-robin
    into n_splits buckets (deterministic given seed), each bucket becomes one fold's val set."""
    rng = np.random.default_rng(seed)
    unique_groups = np.unique(family_ids)
    rng.shuffle(unique_groups)
    buckets = [unique_groups[i::n_splits] for i in range(n_splits)]
    for k in range(n_splits):
        val_groups = set(buckets[k])
        val_idx = np.array([i for i, g in enumerate(family_ids) if g in val_groups])
        train_idx = np.array([i for i, g in enumerate(family_ids) if g not in val_groups])
        yield train_idx, val_idx


def make_batch(tensors, idx, device):
    return {
        "chunks": torch.as_tensor(tensors["chunks"][idx]).to(device),
        "chunk_mask": torch.as_tensor(tensors["chunk_mask"][idx]).to(device),
        "dense": torch.as_tensor(tensors["dense"][idx]).to(device),
    }


def score_all(model, tensors, idx, device) -> np.ndarray:
    model.eval()
    with torch.no_grad():
        batch = make_batch(tensors, idx, device)
        logits = model(batch["chunks"].long(), batch["chunk_mask"].bool(), dense=batch["dense"])
    return logits.cpu().numpy()


def gce_loss(logits: torch.Tensor, targets: torch.Tensor, q: float = 0.7) -> torch.Tensor:
    probs = torch.sigmoid(logits)
    p_t = torch.where(targets == 1, probs, 1 - probs).clamp(min=1e-6, max=1 - 1e-6)
    return ((1 - p_t.pow(q)) / q).mean()


def fresh_model(device) -> HybridModel:
    ckpt = torch.load(BASE_CKPT, map_location=device, weights_only=False)
    model = HybridModel(HybridConfig(vocab_size=227, chunk_size=256, max_chunks=64, use_dense=True))
    model.load_state_dict(ckpt["model_state_dict"])
    model.to(device)
    return model, ckpt["temperature"]


def finetune_one_fold(method: str, tensors: dict, train_idx: np.ndarray, val_idx: np.ndarray,
                       seed: int, device, uncertain_tensors: dict | None = None) -> dict:
    torch.manual_seed(seed)
    model, base_temperature = fresh_model(device)

    if method == "baseline_frozen":
        val_logits = score_all(model, tensors, val_idx, device)
        return {"val_auprc": auprc_fn(tensors["labels"][val_idx], val_logits), "epochs_run": 0}

    if method == "threshold_recalibration_only":
        train_logits = score_all(model, tensors, train_idx, device)
        val_logits = score_all(model, tensors, val_idx, device)
        thr = threshold_at_nominal_fpr(train_logits, tensors["labels"][train_idx], 0.05)
        m = metrics_at_threshold(tensors["labels"][val_idx], val_logits, thr)
        return {"val_auprc": auprc_fn(tensors["labels"][val_idx], val_logits),
                "val_recall_at_recalibrated_thr": m["recall"], "val_fpr_at_recalibrated_thr": m["observed_fpr"],
                "recalibrated_threshold": thr, "epochs_run": 0}

    if method == "sequence_dense_weight_adjustment":
        for p in model.sequence_encoder.parameters():
            p.requires_grad_(False)
        for p in model.aggregator.parameters():
            p.requires_grad_(False)
        trainable_params = [p for p in model.parameters() if p.requires_grad]
    else:
        trainable_params = list(model.parameters())

    optimizer = torch.optim.AdamW(trainable_params, lr=LR, weight_decay=WEIGHT_DECAY)

    y_train = tensors["labels"][train_idx]
    n_pos = max(1, int(y_train.sum())); n_neg = max(1, int(len(train_idx) - n_pos))
    pos_weight = torch.tensor([n_neg / n_pos], dtype=torch.float32, device=device)

    best_val_auprc, best_state, epochs_no_improve = -1.0, copy.deepcopy(model.state_dict()), 0
    rng = np.random.default_rng(seed)

    for epoch in range(MAX_EPOCHS):
        model.train()
        order = train_idx.copy()
        rng.shuffle(order)
        batch_size = min(8, len(order))
        for start in range(0, len(order), batch_size):
            idx = order[start:start + batch_size]
            batch = make_batch(tensors, idx, device)
            optimizer.zero_grad()
            logits = model(batch["chunks"].long(), batch["chunk_mask"].bool(), dense=batch["dense"])

            if method == "plain_finetune" or method == "sequence_dense_weight_adjustment":
                targets = torch.as_tensor(tensors["labels"][idx], dtype=torch.float32, device=device)
                loss = nn.functional.binary_cross_entropy_with_logits(logits, targets, pos_weight=pos_weight)
            elif method == "confidence_weighted":
                targets = torch.as_tensor(tensors["labels"][idx], dtype=torch.float32, device=device)
                weights = torch.as_tensor(tensors["confidence_weight"][idx], dtype=torch.float32, device=device)
                per_sample = nn.functional.binary_cross_entropy_with_logits(logits, targets, reduction="none")
                loss = (per_sample * weights).mean()
            elif method == "source_plus_provisional_weighting":
                targets = torch.as_tensor(tensors["labels"][idx], dtype=torch.float32, device=device)
                agree = (tensors["source_rule_label"][idx] == tensors["labels"][idx]).astype(np.float32)
                weights = torch.as_tensor(np.where(agree, 1.0, 0.5), dtype=torch.float32, device=device)
                per_sample = nn.functional.binary_cross_entropy_with_logits(logits, targets, reduction="none")
                loss = (per_sample * weights).mean()
            elif method == "label_smoothing_noise_aware":
                raw = tensors["labels"][idx]
                smoothed = raw * 0.9 + 0.05
                targets = torch.as_tensor(smoothed, dtype=torch.float32, device=device)
                loss = nn.functional.binary_cross_entropy_with_logits(logits, targets, pos_weight=pos_weight)
            elif method == "generalized_cross_entropy":
                targets = torch.as_tensor(tensors["labels"][idx], dtype=torch.float32, device=device)
                loss = gce_loss(logits, targets)
            elif method == "soft_label_confidence":
                targets = torch.as_tensor(tensors["soft_labels"][idx], dtype=torch.float32, device=device)
                loss = nn.functional.binary_cross_entropy_with_logits(logits, targets)
            elif method == "positive_unlabeled_nnpu":
                targets = torch.as_tensor(tensors["labels"][idx], dtype=torch.float32, device=device)
                is_pos = targets == 1
                pi_p = float(tensors["labels"].mean())
                sig = torch.sigmoid(logits)
                # nnPU with sigmoid loss l(z)=sigmoid(-z) surrogate on {+1,-1} margins.
                pos_logits = logits[is_pos]
                unl_idx_local = np.arange(len(idx))  # in this simplified single-batch nnPU,
                # treat every item in the batch as part of the "unlabeled" risk term too
                # (standard nnPU marginal-risk formulation), plus a separate held-out
                # UNCERTAIN-item batch drawn each step for the unlabeled risk if available.
                if uncertain_tensors is not None and len(uncertain_tensors["labels"]) > 0:
                    u_batch = make_batch(uncertain_tensors, np.arange(len(uncertain_tensors["labels"])), device)
                    u_logits = model(u_batch["chunks"].long(), u_batch["chunk_mask"].bool(), dense=u_batch["dense"])
                else:
                    u_logits = logits
                r_p_pos = torch.sigmoid(-pos_logits).mean() if pos_logits.numel() else torch.tensor(0.0, device=device)
                r_p_neg = torch.sigmoid(pos_logits).mean() if pos_logits.numel() else torch.tensor(0.0, device=device)
                r_u_neg = torch.sigmoid(u_logits).mean()
                neg_risk = r_u_neg - pi_p * r_p_neg
                loss = pi_p * r_p_pos + torch.clamp(neg_risk, min=0.0)
            else:
                raise ValueError(method)

            loss.backward()
            nn.utils.clip_grad_norm_(trainable_params, GRAD_CLIP)
            optimizer.step()

        val_logits = score_all(model, tensors, val_idx, device)
        val_auprc = auprc_fn(tensors["labels"][val_idx], val_logits) if len(np.unique(tensors["labels"][val_idx])) > 1 else 0.5
        if val_auprc > best_val_auprc:
            best_val_auprc, best_state, epochs_no_improve = val_auprc, copy.deepcopy(model.state_dict()), 0
        else:
            epochs_no_improve += 1
            if epochs_no_improve >= PATIENCE:
                break

    model.load_state_dict(best_state)
    val_logits = score_all(model, tensors, val_idx, device)
    return {"val_auprc": auprc_fn(tensors["labels"][val_idx], val_logits) if len(np.unique(tensors["labels"][val_idx])) > 1 else float("nan"),
            "epochs_run": epoch + 1}


METHODS = [
    "baseline_frozen", "plain_finetune", "confidence_weighted",
    "source_plus_provisional_weighting", "label_smoothing_noise_aware",
    "generalized_cross_entropy", "positive_unlabeled_nnpu", "soft_label_confidence",
    "sequence_dense_weight_adjustment", "threshold_recalibration_only",
]


def main() -> int:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[retraining] device={device}")

    manifest, labels, binary_ids, uncertain_ids = load_gold_dev_binary()
    tensors = build_tensors(binary_ids, manifest, labels)
    uncertain_tensors = build_tensors(uncertain_ids, manifest, labels) if uncertain_ids else None
    print(f"[retraining] {len(binary_ids)} binary-labeled Gold-Dev items, "
          f"{len(uncertain_ids)} UNCERTAIN (used only by positive_unlabeled_nnpu)")

    n_families = len(np.unique(tensors["family_id"]))
    print(f"[retraining] {n_families} unique families among {len(binary_ids)} items "
          f"(family leakage check: {'OK, near-singleton families' if n_families >= len(binary_ids) - 2 else 'CLUSTERED'})")

    results = {method: [] for method in METHODS}
    for method in METHODS:
        print(f"[retraining] method={method}")
        for seed in SEEDS:
            for fold_i, (train_idx, val_idx) in enumerate(group_kfold_indices(tensors["family_id"], N_INNER_FOLDS, seed)):
                if len(np.unique(tensors["labels"][val_idx])) < 2:
                    continue  # skip degenerate folds where val has only one class
                run = finetune_one_fold(method, tensors, train_idx, val_idx, seed + fold_i, device, uncertain_tensors)
                run.update({"seed": seed, "fold": fold_i, "n_train": len(train_idx), "n_val": len(val_idx)})
                results[method].append(run)

    summary = {"LABEL_SOURCE": "LLM_PROVISIONAL", "STATUS": "PROVISIONAL_NOT_FOR_FINAL_CLAIMS",
               "n_binary_gold_dev_items": len(binary_ids), "n_uncertain_gold_dev_items": len(uncertain_ids),
               "n_unique_families": int(n_families), "n_inner_folds": N_INNER_FOLDS, "seeds": list(SEEDS),
               "caveat": "Extremely small sample (47 items). Report as methodological "
                         "exercise; std across runs is large relative to point estimates.",
               "methods": {}}
    for method, runs in results.items():
        aups = [r["val_auprc"] for r in runs if not np.isnan(r.get("val_auprc", float("nan")))]
        summary["methods"][method] = {
            "n_runs": len(runs),
            "val_auprc_mean": float(np.mean(aups)) if aups else None,
            "val_auprc_std": float(np.std(aups)) if aups else None,
            "runs": runs,
        }

    out_path = os.path.join(RESULTS_DIR, "retraining_results.json")
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)

    print(f"\nWrote {out_path}")
    for method, m in summary["methods"].items():
        mean = m["val_auprc_mean"]
        std = m["val_auprc_std"]
        print(f"  {method}: val AUPRC = {mean:.3f} +/- {std:.3f}" if mean is not None else f"  {method}: no valid runs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
