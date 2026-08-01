"""Part 8: selects a PROVISIONAL FINAL MODEL from the Part 7 retraining results (Gold-Dev
only -- Gold-Test is never touched here), then actually fine-tunes and freezes it (3 seeds,
trained on all 47 binary-labeled Gold-Dev items using the winning method) so Part 9 has a
real artifact to evaluate.

Selection is NOT by point-estimate AUPRC alone: confidence_weighted fine-tuning won on
(a) highest mean val AUPRC across the 9 Part-7 CV runs, (b) lowest std across those runs
(most stable), (c) no architecture change / no added complexity over the frozen baseline,
(d) same UNCERTAIN-exclusion behavior as the frozen model. See
PROVISIONAL_FINAL_MODEL_SELECTION.md for the full writeup.

Does not replace revision_v3/configs/final_model.json (the Phase 2 frozen model config) --
that file, and the phase2_frozen_model checkpoints, are left untouched. This writes a
SEPARATE config/checkpoint set for the provisional model.

LABEL_SOURCE=LLM_PROVISIONAL
STATUS=PROVISIONAL_NOT_FOR_FINAL_CLAIMS

Usage:
    python3 revision_v3/experiments/llm_provisional/select_provisional_final_model.py
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
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from evaluation.metrics import auprc as auprc_fn, threshold_at_nominal_fpr  # noqa: E402
from training.calibration import fit_temperature  # noqa: E402
from run_retraining_experiments import (  # noqa: E402
    BASE_CKPT, CONFIDENCE_WEIGHT, build_tensors, fresh_model, load_gold_dev_binary, make_batch,
    score_all,
)

WINNING_METHOD = "confidence_weighted"
CONFIG_DIR = os.path.join(REPO_ROOT, "revision_v3", "configs")
RESULTS_DIR = os.path.join(REPO_ROOT, "revision_v3", "results", "llm_provisional")
CKPT_DIR = os.path.join(RESULTS_DIR, "provisional_final_model_checkpoints")
os.makedirs(CKPT_DIR, exist_ok=True)

SEEDS = (7702, 7703, 7704)
LR = 1e-3
WEIGHT_DECAY = 1e-4
GRAD_CLIP = 5.0
MAX_EPOCHS = 20


def train_final(tensors: dict, seed: int, device) -> dict:
    torch.manual_seed(seed)
    model, _ = fresh_model(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
    rng = np.random.default_rng(seed)
    n_items = len(tensors["labels"])
    idx_all = np.arange(n_items)

    for epoch in range(MAX_EPOCHS):
        model.train()
        order = idx_all.copy()
        rng.shuffle(order)
        for start in range(0, len(order), 8):
            idx = order[start:start + 8]
            batch = make_batch(tensors, idx, device)
            optimizer.zero_grad()
            logits = model(batch["chunks"].long(), batch["chunk_mask"].bool(), dense=batch["dense"])
            targets = torch.as_tensor(tensors["labels"][idx], dtype=torch.float32, device=device)
            weights = torch.as_tensor(tensors["confidence_weight"][idx], dtype=torch.float32, device=device)
            per_sample = nn.functional.binary_cross_entropy_with_logits(logits, targets, reduction="none")
            loss = (per_sample * weights).mean()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), GRAD_CLIP)
            optimizer.step()

    # Calibrate + threshold on a random 80/20 split of the same Gold-Dev binary set (no
    # Gold-Test involvement whatsoever) -- this is the same role the original Phase 1/2
    # validation fold played, just re-derived here since there is no separate held-out
    # calibration split provided for this tiny provisional-model exercise.
    cal_rng = np.random.default_rng(seed + 999)
    perm = cal_rng.permutation(n_items)
    cal_idx = perm[: max(1, n_items // 5)]
    with torch.no_grad():
        cal_batch = make_batch(tensors, cal_idx, device)
        cal_logits = model(cal_batch["chunks"].long(), cal_batch["chunk_mask"].bool(), dense=cal_batch["dense"])
    cal_labels = torch.as_tensor(tensors["labels"][cal_idx], dtype=torch.float32)
    temperature = fit_temperature(cal_logits.cpu(), cal_labels) if len(np.unique(tensors["labels"][cal_idx])) > 1 else 1.0

    train_logits = score_all(model, tensors, idx_all, device)
    train_scores = torch.sigmoid(torch.as_tensor(train_logits) / max(temperature, 1e-3)).numpy()
    threshold_5pct = threshold_at_nominal_fpr(train_scores, tensors["labels"], 0.05)

    return {"model_state_dict": copy.deepcopy(model.state_dict()), "temperature": float(temperature),
            "threshold_5pct": float(threshold_5pct), "seed": seed}


def main() -> int:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    manifest, labels, binary_ids, uncertain_ids = load_gold_dev_binary()
    tensors = build_tensors(binary_ids, manifest, labels)

    print(f"[select_provisional_final_model] training winning method "
          f"'{WINNING_METHOD}' on all {len(binary_ids)} binary Gold-Dev items, {len(SEEDS)} seeds")
    per_seed_ckpts = {}
    for seed in SEEDS:
        result = train_final(tensors, seed, device)
        ckpt_path = os.path.join(CKPT_DIR, f"provisional_final_model_seed{seed}.pt")
        torch.save(result, ckpt_path)
        per_seed_ckpts[seed] = ckpt_path
        print(f"  seed={seed}: temperature={result['temperature']:.3f} threshold_5pct={result['threshold_5pct']:.3f}")

    with open(os.path.join(RESULTS_DIR, "retraining", "retraining_results.json")) as f:
        retraining_results = json.load(f)

    manifest_out = {
        "LABEL_SOURCE": "LLM_PROVISIONAL", "STATUS": "PROVISIONAL_NOT_FOR_FINAL_CLAIMS",
        "provisional_final_model": {
            "base_architecture": "HybridModel (authguard_sequence_dense architecture, unchanged)",
            "base_checkpoint": BASE_CKPT,
            "selection_method": WINNING_METHOD,
            "selection_evidence": {
                m: retraining_results["methods"][m] for m in
                ["baseline_frozen", WINNING_METHOD, "plain_finetune", "sequence_dense_weight_adjustment"]
            },
            "selection_criteria_applied": [
                "highest mean val AUPRC across 9 Part-7 CV runs (family-grouped 3-fold x 3 seeds)",
                "lowest std across those runs (stability)",
                "no architecture/complexity change vs. frozen baseline",
                "does not alter UNCERTAIN-exclusion behavior",
            ],
            "training_data": f"{len(binary_ids)} Gold-Dev binary-labeled items (LLM_PROVISIONAL), "
                              f"{len(uncertain_ids)} UNCERTAIN items excluded from training entirely",
            "checkpoints": {str(s): p for s, p in per_seed_ckpts.items()},
            "frozen_at_utc": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        },
        "phase2_frozen_model_untouched_reference": os.path.join(REPO_ROOT, "revision_v3", "configs", "final_model.json"),
    }
    manifest_path = os.path.join(RESULTS_DIR, "provisional_final_model_manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest_out, f, indent=2, default=str)

    config_out = {
        "_comment": "PROVISIONAL FINAL MODEL config -- LLM_PROVISIONAL label source. Does "
                    "NOT replace revision_v3/configs/final_model.json (phase2_frozen_model), "
                    "which remains the frozen Phase 2 reference and is preserved unchanged.",
        "LABEL_SOURCE": "LLM_PROVISIONAL", "STATUS": "PROVISIONAL_NOT_FOR_FINAL_CLAIMS",
        "model_name": "provisional_final_model",
        "base_model_name": "authguard_sequence_dense",
        "architecture": {"class": "HybridModel", "module": "revision_v3.src.models.hybrid",
                          "config": {"vocab_size": 227, "chunk_size": 256, "max_chunks": 64,
                                     "embedding_dim": 32, "channel_dim": 64, "view_dim": 64,
                                     "fusion_dim": 128, "dense_dim": 261, "ngram_dim": 512,
                                     "dropout": 0.15, "use_multiscale": False, "use_dense": True,
                                     "use_ngram": False}},
        "selection_method": WINNING_METHOD,
        "training_data": "revision_v3/results/llm_provisional/gold_dev_labels.json (binary subset only)",
        "checkpoints": {str(s): p for s, p in per_seed_ckpts.items()},
        "phase2_frozen_model": os.path.join(REPO_ROOT, "revision_v3", "configs", "final_model.json"),
        "llm_provisional_selected_model": manifest_path,
    }
    config_path = os.path.join(CONFIG_DIR, "provisional_final_model.json")
    with open(config_path, "w") as f:
        json.dump(config_out, f, indent=2, default=str)

    print(f"\nWrote {manifest_path}")
    print(f"Wrote {config_path}")
    print(f"Wrote {len(per_seed_ckpts)} checkpoints -> {CKPT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
