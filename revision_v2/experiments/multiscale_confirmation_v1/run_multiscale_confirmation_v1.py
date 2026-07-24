#!/usr/bin/env python3
"""Confirm AuthGuard-MSP on outer folds 1--4, with fold 0 reserved for development."""
from __future__ import annotations

import argparse
import gc
import json
import os
import sys
import time

import numpy as np
import pandas as pd
import torch
from torch import nn

HERE = os.path.dirname(os.path.abspath(__file__))
RV2 = os.path.abspath(os.path.join(HERE, "..", ".."))
LCA_DIR = os.path.join(RV2, "experiments", "long_context_ablation_v3")
sys.path.insert(0, LCA_DIR)

import run_long_context_ablation_v3 as lca  # noqa: E402

OUT = os.path.join(RV2, "results", "multiscale_confirmation_v1")
V3_OUT = os.path.join(RV2, "results", "long_context_ablation_v3")
MODEL_NAME = "authguard_msp_16384"
FOLDS = (1, 2, 3, 4)
SEEDS = (7702, 7703, 7704)
SPEC = lca.ModelSpec(MODEL_NAME, "chunk", "multiscale", 16_384)


class AuthGuardMSP(nn.Module):
    """Shared local encoding with attention, mean, and max chunk summaries."""

    def __init__(self, dropout=0.15):
        super().__init__()
        self.embedding = nn.Embedding(lca.VOCAB_SIZE, 32, padding_idx=lca.PAD_ID)
        self.encoder = nn.Sequential(
            nn.Conv1d(32, 64, kernel_size=5, padding=2),
            nn.GELU(),
            nn.Conv1d(64, 64, kernel_size=3, padding=2, dilation=2),
            nn.GELU(),
        )
        self.chunk_attention = nn.Linear(64, 1)
        self.fusion = nn.Sequential(
            nn.LayerNorm(192),
            nn.Linear(192, 64),
            nn.GELU(),
            nn.Dropout(dropout),
        )
        self.risk_head = nn.Linear(64, 1)

    def forward(self, chunks, chunk_mask, dense, ngram):
        del dense, ngram
        batch, count, width = chunks.shape
        flat = chunks.reshape(batch * count, width)
        encoded = self.encoder(self.embedding(flat).transpose(1, 2))
        token_mask = flat.ne(lca.PAD_ID).unsqueeze(1)
        encoded = encoded.masked_fill(~token_mask, -1.0e4)
        vectors = encoded.amax(dim=2).reshape(batch, count, -1)
        vectors = vectors.masked_fill(~chunk_mask.unsqueeze(-1), 0.0)

        logits = self.chunk_attention(vectors).squeeze(-1)
        logits = logits.masked_fill(~chunk_mask, -1.0e4)
        attention = torch.softmax(logits, dim=1)
        attention_summary = (vectors * attention.unsqueeze(-1)).sum(dim=1)

        weights = chunk_mask.to(vectors.dtype)
        mean_summary = (vectors * weights.unsqueeze(-1)).sum(dim=1)
        mean_summary = mean_summary / weights.sum(dim=1, keepdim=True).clamp(min=1.0)

        max_summary = vectors.masked_fill(
            ~chunk_mask.unsqueeze(-1), -1.0e4).amax(dim=1)
        fused = self.fusion(torch.cat(
            [attention_summary, mean_summary, max_summary], dim=1))
        risk = self.risk_head(fused).squeeze(-1)
        return {
            "risk_logit": risk,
            "auxiliary_logits": risk.new_zeros((batch, 6)),
            "embedding": fused,
            "view_weights": risk.new_ones((batch, 1)),
            "chunk_attention": attention,
        }


def persist(output, completed, metrics, predictions, history, complexity):
    lca.atomic_csv(pd.DataFrame(metrics), os.path.join(output, "metrics.csv"))
    lca.atomic_csv(
        pd.DataFrame(predictions),
        os.path.join(output, "predictions.csv.gz"),
        compression="gzip",
    )
    lca.atomic_csv(pd.DataFrame(history), os.path.join(output, "history.csv"))
    lca.atomic_csv(pd.DataFrame(complexity), os.path.join(output, "complexity.csv"))
    lca.atomic_json(
        {"completed": sorted(completed)},
        os.path.join(output, "checkpoint.json"),
    )


def load_resume(output):
    checkpoint = os.path.join(output, "checkpoint.json")
    if not os.path.exists(checkpoint):
        return set(), [], [], [], []
    completed = set(json.load(open(checkpoint, encoding="utf-8"))["completed"])

    def rows(name):
        path = os.path.join(output, name)
        if not os.path.exists(path):
            return []
        frame = pd.read_csv(path)
        return frame[frame["unit_key"].isin(completed)].to_dict("records")

    return completed, rows("metrics.csv"), rows("predictions.csv.gz"), \
        rows("history.csv"), rows("complexity.csv")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", nargs="+", type=int, default=list(SEEDS))
    parser.add_argument("--folds", nargs="+", type=int, default=list(FOLDS))
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--patience", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--threads", type=int, default=6)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--output-dir", default=OUT)
    args = parser.parse_args()
    if any(fold not in FOLDS for fold in args.folds):
        raise ValueError("fold 0 is development-only; confirmation folds are 1--4")

    output = os.path.abspath(args.output_dir)
    os.makedirs(output, exist_ok=True)
    os.makedirs(os.path.join(output, "models"), exist_ok=True)
    torch.set_num_threads(args.threads)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if lca.verify_frozen() != 0:
        raise RuntimeError("frozen-artifact verification failed")

    bench = pd.read_csv(lca.BENCH_PATH)
    primary = bench[bench["population"] == "PRIMARY_EVALUATION"].copy().reset_index(drop=True)
    primary["y"] = primary["label"].astype(int)
    features = np.load(lca.FEATURE_PATH, allow_pickle=False)
    token_store = lca.RaggedTokenStore(features["tokens"], features["offsets"])
    original_counts = np.diff(features["offsets"]).astype(np.int64)
    y = primary["y"].to_numpy(dtype=int)
    fold_ids = primary["fold_id"].to_numpy(dtype=int)

    if args.resume:
        completed, metrics, predictions, history, complexity = load_resume(output)
    else:
        completed, metrics, predictions, history, complexity = set(), [], [], [], []

    for fold in args.folds:
        cache = os.path.join(V3_OUT, "data", f"f200_fold{fold}.npz")
        if not os.path.exists(cache):
            raise FileNotFoundError(
                f"v3 F200 cache is not ready for fold {fold}: {cache}")
        test_idx = np.flatnonzero(fold_ids == fold)
        val_idx = np.flatnonzero(fold_ids == (fold + 1) % 5)
        train_idx = np.flatnonzero(
            (fold_ids != fold) & (fold_ids != (fold + 1) % 5))
        expected_sids = primary.iloc[test_idx]["sample_id"].astype(str).tolist()
        f200_store, f200_counts, _ = lca.load_ragged(cache, expected_sids)
        f200_local = np.arange(len(test_idx))
        f200_y = y[test_idx]

        for seed in args.seeds:
            unit_key = f"{MODEL_NAME}:{seed}:{fold}"
            if unit_key in completed:
                continue
            train_loader = lca.make_loader(
                train_idx, token_store, y, SPEC, args.batch_size, shuffle=True,
                seed=seed + fold)
            val_loader = lca.make_loader(
                val_idx, token_store, y, SPEC, args.batch_size)
            test_loader = lca.make_loader(
                test_idx, token_store, y, SPEC, args.batch_size)
            flood_loader = lca.make_loader(
                f200_local, f200_store, f200_y, SPEC, args.batch_size)
            model = AuthGuardMSP()
            params, size = lca.model_size(model)
            if not complexity:
                complexity.append({
                    "unit_key": unit_key,
                    "model": MODEL_NAME,
                    "token_budget": SPEC.token_budget,
                    "trainable_params": params,
                    "serialized_bytes_untrained": size,
                })
            started = time.time()
            model, unit_history, best_val = lca.train_model(
                model, train_loader, val_loader, y[train_idx], device, seed + fold,
                args.epochs, args.patience, 1e-3)
            _, y_val, val_logits = lca.predict(model, val_loader, device)
            clean_indices, y_test, clean_logits = lca.predict(model, test_loader, device)
            clean_metrics, temperature, policy, clean_scores, clean_raw = \
                lca.evaluate_logits(val_logits, y_val, clean_logits, y_test)
            _, y_flood, flood_logits = lca.predict(model, flood_loader, device)
            flood_metrics, flood_scores, flood_raw = lca.evaluate_fixed_policy(
                flood_logits, y_flood, temperature, policy)

            torch.save({
                "state_dict": model.state_dict(),
                "seed": seed,
                "fold": fold,
                "temperature": temperature,
                "warning_policy": policy.to_dict(),
                "best_val_AUPRC": best_val,
                "protocol": "revision_v2/protocols/multiscale_confirmation_v1.md",
            }, os.path.join(
                output, "models", f"{MODEL_NAME}_seed{seed}_fold{fold}.pt"))

            for condition, result in (("M0", clean_metrics), ("F200", flood_metrics)):
                row = {
                    "unit_key": unit_key,
                    "model": MODEL_NAME,
                    "seed": seed,
                    "fold": fold,
                    "condition": condition,
                    "token_budget": SPEC.token_budget,
                    "best_val_AUPRC": best_val,
                    "temperature": temperature,
                    "threshold_01": policy.threshold_01,
                    "threshold_05": policy.threshold_05,
                    "threshold_10": policy.threshold_10,
                }
                row.update({name: result.get(name) for name in lca.METRIC_COLUMNS})
                metrics.append(row)

            clean_pos = {int(index): pos for pos, index in enumerate(clean_indices)}
            for index in test_idx:
                pos = clean_pos[int(index)]
                total = int(original_counts[index])
                predictions.append({
                    "unit_key": unit_key,
                    "model": MODEL_NAME,
                    "seed": seed,
                    "fold": fold,
                    "condition": "M0",
                    "sid": primary.iloc[index]["sample_id"],
                    "family_id": primary.iloc[index]["family_id"],
                    "y": int(y[index]),
                    "raw_score": float(clean_raw[pos]),
                    "calibrated_score": float(clean_scores[pos]),
                    "original_opcode_count": total,
                    "condition_opcode_count": total,
                    "retained_token_count": lca.retained_token_count(
                        token_store.row(int(index)), SPEC),
                    "token_budget": SPEC.token_budget,
                })
            for local, index in enumerate(test_idx):
                predictions.append({
                    "unit_key": unit_key,
                    "model": MODEL_NAME,
                    "seed": seed,
                    "fold": fold,
                    "condition": "F200",
                    "sid": primary.iloc[index]["sample_id"],
                    "family_id": primary.iloc[index]["family_id"],
                    "y": int(y[index]),
                    "raw_score": float(flood_raw[local]),
                    "calibrated_score": float(flood_scores[local]),
                    "original_opcode_count": int(original_counts[index]),
                    "condition_opcode_count": int(f200_counts[local]),
                    "retained_token_count": lca.retained_token_count(
                        f200_store.row(local), SPEC),
                    "token_budget": SPEC.token_budget,
                })
            for item in unit_history:
                history.append({
                    "unit_key": unit_key,
                    "model": MODEL_NAME,
                    "seed": seed,
                    "fold": fold,
                    **item,
                })
            completed.add(unit_key)
            persist(output, completed, metrics, predictions, history, complexity)
            print(
                f"[msp] complete {unit_key} M0_AP={clean_metrics['AUPRC']:.4f} "
                f"F200_AP={flood_metrics['AUPRC']:.4f} "
                f"seconds={time.time() - started:.1f}",
                flush=True,
            )
            del model, train_loader, val_loader, test_loader, flood_loader
            gc.collect()

    frame = pd.DataFrame(metrics)
    per_seed = (
        frame.groupby(["model", "condition", "seed"], as_index=False)
        [list(lca.METRIC_COLUMNS)]
        .mean()
    )
    lca.atomic_csv(per_seed, os.path.join(output, "seed_summary.csv"))
    summary = []
    for (model, condition), group in per_seed.groupby(["model", "condition"]):
        row = {"model": model, "condition": condition}
        for metric in lca.METRIC_COLUMNS:
            row[f"{metric}_mean"] = float(group[metric].mean())
            row[f"{metric}_sd"] = float(group[metric].std(ddof=0))
        summary.append(row)
    lca.atomic_csv(pd.DataFrame(summary), os.path.join(output, "summary.csv"))
    if lca.verify_frozen() != 0:
        raise RuntimeError("frozen-artifact verification failed after confirmation")
    print(f"[msp] confirmation complete units={len(completed)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
