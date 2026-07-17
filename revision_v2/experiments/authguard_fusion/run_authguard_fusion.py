#!/usr/bin/env python3
"""Family-disjoint AuthGuard-Fusion architecture and strongest-baseline experiment.

Long-running entry point. The frozen corpus is read-only and all checkpoints/results are written
under revision_v2/results/authguard_fusion.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import gc
import json
import math
import os
import random
import sys
import time

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import average_precision_score, brier_score_loss
from torch import nn
from torch.utils.data import DataLoader, Dataset

HERE = os.path.dirname(os.path.abspath(__file__))
RV2 = os.path.abspath(os.path.join(HERE, "..", ".."))
ROOT = os.path.abspath(os.path.join(RV2, ".."))
sys.path.insert(0, RV2)
sys.path.insert(0, os.path.join(RV2, "experiments", "common"))
sys.path.insert(0, os.path.join(RV2, "experiments", "donor_pools"))

from authguard7702.features import (AUXILIARY_FACTORS, EncodedBytecode, PAD_ID,
                                    auxiliary_targets, encode_bytecode)  # noqa: E402
from authguard7702.model import AuthGuardFusion, FusionConfig  # noqa: E402
from authguard7702.policy import WarningPolicy  # noqa: E402
from frozen import verify as verify_frozen  # noqa: E402
try:
    from xgboost import XGBClassifier
except ImportError:  # validate-only works without XGBoost
    XGBClassifier = None

OUT = os.path.join(RV2, "results", "authguard_fusion")
BENCH = os.path.join(RV2, "results", "authguard_bench")
DATA = os.path.join(ROOT, "paper_build", "data_hygiene", "task_aligned_dataset_v1.csv")
DENSE = os.path.join(ROOT, "paper_build", "data_hygiene", "task_aligned_features_dense.npz")
NGRAM = os.path.join(ROOT, "paper_build", "data_hygiene", "task_aligned_features_ngram.npz")
TOKENS = os.path.join(BENCH, "opcode_tokens.npz")

MODEL_SPECS = {
    "sequence_only": dict(active_views=(True, False, False), auxiliary_weight=0.0,
                          transformed=False, consistency_weight=0.0),
    "ngram_only": dict(active_views=(False, True, False), auxiliary_weight=0.0,
                       transformed=False, consistency_weight=0.0),
    "dense_only": dict(active_views=(False, False, True), auxiliary_weight=0.0,
                       transformed=False, consistency_weight=0.0),
    "fusion_no_aux": dict(active_views=(True, True, True), auxiliary_weight=0.0,
                          transformed=False, consistency_weight=0.0),
    "fusion_multitask": dict(active_views=(True, True, True), auxiliary_weight=0.25,
                             transformed=False, consistency_weight=0.0),
    "fusion_source_balanced": dict(active_views=(True, True, True), auxiliary_weight=0.25,
                                   transformed=True, consistency_weight=0.0),
    "fusion_consistent": dict(active_views=(True, True, True), auxiliary_weight=0.25,
                              transformed=True, consistency_weight=0.50),
}

XGB_HP = dict(n_estimators=300, max_depth=6, learning_rate=0.1, subsample=0.9,
              colsample_bytree=0.8, eval_metric="logloss", n_jobs=12, tree_method="hist")


def set_seed(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(False)


class TokenStore:
    def __init__(self, path: str):
        data = np.load(path)
        self.tokens = data["tokens"]
        self.offsets = data["offsets"]
        self.auxiliary = data["auxiliary"]

    def row(self, source_index: int) -> np.ndarray:
        return self.tokens[self.offsets[source_index]:self.offsets[source_index + 1]].astype(np.int64)


def chunk_tokens(tokens: np.ndarray, chunk_size: int, max_chunks: int) -> np.ndarray:
    count = int(math.ceil(len(tokens) / chunk_size))
    chunks = np.full((count, chunk_size), PAD_ID, dtype=np.int64)
    for index in range(count):
        part = tokens[index * chunk_size:(index + 1) * chunk_size]
        chunks[index, :len(part)] = part
    if len(chunks) > max_chunks:
        chosen = np.linspace(0, len(chunks) - 1, max_chunks).round().astype(int)
        chunks = chunks[chosen]
    return chunks


class FusionDataset(Dataset):
    def __init__(self, indices, source_indices, tokens: TokenStore, dense, ngram, labels,
                 dense_mean, dense_scale, chunk_size, max_chunks, transformed=None):
        self.indices = np.asarray(indices, dtype=int)
        self.source_indices = np.asarray(source_indices, dtype=int)
        self.tokens = tokens
        self.dense = dense
        self.ngram = ngram
        self.labels = labels
        self.dense_mean = dense_mean
        self.dense_scale = dense_scale
        self.chunk_size = chunk_size
        self.max_chunks = max_chunks
        self.transformed = transformed or {}

    def __len__(self):
        return len(self.indices)

    def clean(self, index: int) -> dict:
        source_index = self.source_indices[index]
        return {
            "chunks": chunk_tokens(self.tokens.row(source_index), self.chunk_size, self.max_chunks),
            "dense": ((self.dense[index] - self.dense_mean) / self.dense_scale).astype(np.float32),
            "ngram": self.ngram[index].astype(np.float32),
            "auxiliary": self.tokens.auxiliary[source_index].astype(np.float32),
        }

    def variant(self, index: int) -> dict | None:
        encoded = self.transformed.get(index)
        if encoded is None:
            return None
        return {
            "chunks": encoded.chunks,
            "dense": ((encoded.dense - self.dense_mean) / self.dense_scale).astype(np.float32),
            "ngram": encoded.ngram.astype(np.float32),
            "auxiliary": encoded.auxiliary.astype(np.float32),
        }

    def __getitem__(self, offset):
        index = int(self.indices[offset])
        return index, self.clean(index), self.variant(index), float(self.labels[index])


def _pad_views(items: list[dict]) -> dict[str, torch.Tensor]:
    max_chunks = max(len(item["chunks"]) for item in items)
    width = items[0]["chunks"].shape[1]
    chunks = np.full((len(items), max_chunks, width), PAD_ID, dtype=np.int64)
    mask = np.zeros((len(items), max_chunks), dtype=np.bool_)
    for index, item in enumerate(items):
        chunks[index, :len(item["chunks"])] = item["chunks"]
        mask[index, :len(item["chunks"])] = True
    return {
        "chunks": torch.from_numpy(chunks),
        "chunk_mask": torch.from_numpy(mask),
        "dense": torch.from_numpy(np.stack([item["dense"] for item in items])),
        "ngram": torch.from_numpy(np.stack([item["ngram"] for item in items])),
        "auxiliary": torch.from_numpy(np.stack([item["auxiliary"] for item in items])),
    }


def collate(batch):
    indices, clean, variant, labels = zip(*batch)
    output = {
        "indices": np.asarray(indices, dtype=int),
        "clean": _pad_views(list(clean)),
        "labels": torch.tensor(labels, dtype=torch.float32),
    }
    output["variant"] = _pad_views(list(variant)) if all(v is not None for v in variant) else None
    return output


def to_device(view: dict, device: torch.device) -> dict:
    return {key: value.to(device, non_blocking=True) for key, value in view.items()
            if key != "auxiliary"}


def predict_logits(model, loader, device):
    model.eval()
    indices, labels, logits, aux, view_weights = [], [], [], [], []
    with torch.no_grad():
        for batch in loader:
            view = to_device(batch["clean"], device)
            output = model(**view)
            if not torch.isfinite(output["risk_logit"]).all():
                raise FloatingPointError("non-finite AuthGuard-Fusion risk logits during scoring")
            indices.extend(batch["indices"].tolist())
            labels.extend(batch["labels"].numpy().tolist())
            logits.extend(output["risk_logit"].cpu().numpy().tolist())
            aux.extend(torch.sigmoid(output["auxiliary_logits"]).cpu().numpy().tolist())
            view_weights.extend(output["view_weights"].cpu().numpy().tolist())
    return (np.asarray(indices), np.asarray(labels), np.asarray(logits),
            np.asarray(aux), np.asarray(view_weights))


def fit_temperature(logits: np.ndarray, labels: np.ndarray) -> float:
    x = torch.tensor(logits, dtype=torch.float32)
    y = torch.tensor(labels, dtype=torch.float32)
    log_temperature = torch.zeros(1, requires_grad=True)
    optimizer = torch.optim.LBFGS([log_temperature], lr=0.1, max_iter=50)
    loss_fn = nn.BCEWithLogitsLoss()

    def closure():
        optimizer.zero_grad()
        temperature = log_temperature.exp().clamp(0.05, 20.0)
        loss = loss_fn(x / temperature, y)
        loss.backward()
        return loss

    optimizer.step(closure)
    return float(log_temperature.detach().exp().clamp(0.05, 20.0))


def probabilities(logits, temperature):
    scaled = np.asarray(logits, dtype=float) / float(temperature)
    return 1.0 / (1.0 + np.exp(-np.clip(scaled, -40, 40)))


def evaluate(y, scores, policy: WarningPolicy) -> dict:
    y = np.asarray(y, dtype=int); scores = np.asarray(scores, dtype=float)
    output = {
        "AUPRC": float(average_precision_score(y, scores)) if len(np.unique(y)) == 2 else None,
        "Brier": float(brier_score_loss(y, scores)),
    }
    for suffix, threshold in (("01", policy.threshold_01),
                              ("05", policy.threshold_05),
                              ("10", policy.threshold_10)):
        pred = scores >= threshold
        positive, negative = y == 1, y == 0
        output[f"Recall_{suffix}"] = float(pred[positive].mean()) if positive.any() else None
        output[f"FPR_{suffix}"] = float(pred[negative].mean()) if negative.any() else None
    return output


def auxiliary_metrics(targets, scores) -> dict:
    output = {}
    for index, name in enumerate(AUXILIARY_FACTORS):
        y = targets[:, index].astype(int)
        output[name] = {
            "prevalence": float(y.mean()),
            "AUPRC": float(average_precision_score(y, scores[:, index]))
            if len(np.unique(y)) == 2 else None,
        }
    valid = [item["AUPRC"] for item in output.values() if item["AUPRC"] is not None]
    output["macro_AUPRC"] = float(np.mean(valid)) if valid else None
    return output


def train_model(config, train_loader, val_loader, device, seed, epochs, patience, lr,
                auxiliary_weight, consistency_weight):
    set_seed(seed)
    model = AuthGuardFusion(config).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    labels = np.concatenate([batch["labels"].numpy() for batch in train_loader])
    pos_weight = torch.tensor([(labels == 0).sum() / max((labels == 1).sum(), 1)],
                              device=device, dtype=torch.float32)
    risk_loss = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    aux_loss = nn.BCEWithLogitsLoss()
    best_state, best_ap, stale, history = None, -np.inf, 0, []
    for epoch in range(1, epochs + 1):
        model.train(); running = []
        for batch in train_loader:
            y = batch["labels"].to(device)
            clean_view = to_device(batch["clean"], device)
            clean = model(**clean_view)
            loss_main = risk_loss(clean["risk_logit"], y)
            loss_aux = aux_loss(clean["auxiliary_logits"],
                                batch["clean"]["auxiliary"].to(device))
            loss = loss_main + auxiliary_weight * loss_aux
            if batch["variant"] is not None:
                variant = model(**to_device(batch["variant"], device))
                loss_variant = risk_loss(variant["risk_logit"], y)
                consistency = nn.functional.mse_loss(
                    torch.sigmoid(clean["risk_logit"]), torch.sigmoid(variant["risk_logit"]))
                # Average clean and transformed supervised losses: one unit per source.
                loss = 0.5 * (loss_main + loss_variant) + auxiliary_weight * loss_aux
                loss = loss + consistency_weight * consistency
            if not torch.isfinite(loss):
                raise FloatingPointError(
                    f"non-finite training loss at epoch {epoch}; check view normalization")
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            optimizer.step()
            running.append(float(loss.detach().cpu()))
        _, y_val, logits_val, _, _ = predict_logits(model, val_loader, device)
        ap = float(average_precision_score(y_val, logits_val))
        history.append({"epoch": epoch, "train_loss": float(np.mean(running)),
                        "val_AUPRC": ap})
        if ap > best_ap + 1e-5:
            best_ap, stale = ap, 0
            best_state = {key: value.detach().cpu().clone()
                          for key, value in model.state_dict().items()}
        else:
            stale += 1
            if stale >= patience:
                break
    model.load_state_dict(best_state)
    return model, history, best_ap


def make_loaders(indices, source_indices, tokens, dense, ngram, labels, mean, scale,
                 chunk_size, max_chunks, batch_size, transformed=None, shuffle=False):
    dataset = FusionDataset(indices, source_indices, tokens, dense, ngram, labels, mean, scale,
                            chunk_size, max_chunks, transformed)
    return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle, collate_fn=collate,
                      num_workers=0, pin_memory=torch.cuda.is_available())


def transformed_bank(df, indices, fold, partition, conditions, pools, chunk_size, max_chunks,
                     domain):
    bank = {}
    for position, index in enumerate(indices):
        row = df.iloc[int(index)].to_dict()
        condition = conditions[position % len(conditions)]
        variant = make_variant_isolated(pools, row, fold, partition, condition, domain)
        bank[int(index)] = encode_bytecode(variant, chunk_size, max_chunks)
    return bank


def score_encoded_bank(model, encoded_rows, labels, mean, scale, batch_size, device):
    dense = np.stack([row.dense for row in encoded_rows])
    ngram = np.stack([row.ngram for row in encoded_rows])
    auxiliary = np.stack([row.auxiliary for row in encoded_rows])
    # A local store adapter is unnecessary; collate directly in deterministic batches.
    logits, aux_scores = [], []
    model.eval()
    with torch.no_grad():
        for start in range(0, len(encoded_rows), batch_size):
            rows = encoded_rows[start:start + batch_size]
            views = _pad_views([{
                "chunks": row.chunks,
                "dense": ((row.dense - mean) / scale).astype(np.float32),
                "ngram": row.ngram.astype(np.float32),
                "auxiliary": row.auxiliary.astype(np.float32),
            } for row in rows])
            output = model(**to_device(views, device))
            logits.extend(output["risk_logit"].cpu().numpy().tolist())
            aux_scores.extend(torch.sigmoid(output["auxiliary_logits"]).cpu().numpy().tolist())
    return np.asarray(logits), np.asarray(aux_scores), auxiliary


def fit_strongest_baseline(X_train, y_train, X_val, X_test, seed):
    if XGBClassifier is None:
        raise RuntimeError("xgboost is required for the strongest hist+ngram baseline")
    model = XGBClassifier(random_state=seed, **XGB_HP)
    model.fit(X_train, y_train)
    return model, model.predict_proba(X_val)[:, 1], model.predict_proba(X_test)[:, 1]


def main():
    global OUT
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--models", nargs="+", choices=sorted(MODEL_SPECS),
                        default=list(MODEL_SPECS))
    parser.add_argument("--seeds", nargs="+", type=int, default=[7702])
    parser.add_argument("--folds", nargs="+", type=int, default=list(range(5)))
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--patience", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--chunk-size", type=int, default=256)
    parser.add_argument("--max-chunks", type=int, default=64)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--skip-baseline", action="store_true")
    parser.add_argument("--skip-robustness", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--output-dir", default=OUT)
    parser.add_argument("--smoke-limit", type=int, default=0,
                        help="stratified rows per partition for implementation smoke tests only")
    args = parser.parse_args()
    OUT = os.path.abspath(args.output_dir)

    if verify_frozen() != 0:
        raise RuntimeError("frozen-artifact verification failed")
    if not os.path.exists(TOKENS):
        raise FileNotFoundError("build AuthGuardBench-7702 before training")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[fusion] device={device} models={args.models} seeds={args.seeds}", flush=True)

    full = pd.read_csv(DATA)
    full["bc"] = full["bytecode"].astype(str)
    full["sid"] = full["chain"].astype(str) + ":" + full["address"].astype(str)
    full["y"] = (full["class"] == "malicious").astype(int)
    Xd_all = np.load(DENSE)["X"].astype(np.float32)
    Xn_all = np.load(NGRAM)["X"].astype(np.float32)
    token_store = TokenStore(TOKENS)
    primary_mask = full["class"].isin(["malicious", "benign_cleared"]).to_numpy()
    source_indices = np.flatnonzero(primary_mask)
    frame = full.loc[primary_mask].reset_index(drop=True)
    Xd, Xn = Xd_all[primary_mask], Xn_all[primary_mask]
    y = frame["y"].to_numpy(dtype=int)
    folds = frame["outer_fold_primary"].to_numpy(dtype=int)
    families = frame["family_id"].astype(str).to_numpy()
    hist_ngram = np.hstack([Xd[:, :225], Xn]).astype(np.float32)

    if args.validate_only:
        indices = np.arange(min(12, len(frame)))
        mean = Xd[indices].mean(0); scale = Xd[indices].std(0); scale[scale < 1e-6] = 1.0
        loader = make_loaders(indices, source_indices, token_store, Xd, Xn, y, mean, scale,
                              args.chunk_size, args.max_chunks, 4)
        batch = next(iter(loader))
        model = AuthGuardFusion()
        output = model(**to_device(batch["clean"], torch.device("cpu")))
        assert output["risk_logit"].shape[0] == len(batch["labels"])
        print(json.dumps({"validation": "PASS", "batch": len(batch["labels"]),
                          "risk_shape": list(output["risk_logit"].shape),
                          "aux_shape": list(output["auxiliary_logits"].shape)}, indent=2))
        return

    os.makedirs(OUT, exist_ok=True)
    checkpoint_path = os.path.join(OUT, "checkpoint.json")
    completed, metrics_rows, prediction_rows, history_rows = set(), [], [], []
    if args.resume and os.path.exists(checkpoint_path):
        state = json.load(open(checkpoint_path))
        completed = set(state["completed"])
        for name, destination in (("metrics.csv", metrics_rows),
                                  ("predictions.csv.gz", prediction_rows),
                                  ("history.csv", history_rows)):
            path = os.path.join(OUT, name)
            if os.path.exists(path):
                destination.extend(pd.read_csv(path).to_dict(orient="records"))

    needs_pool = (not args.skip_robustness or
                  any(MODEL_SPECS[name]["transformed"] for name in args.models))
    pools = None
    if needs_pool:
        # Donor-pool imports load the frozen mutation module, whose historical imports include
        # XGBoost. Keep them out of validation and clean-model-only paths.
        global DonorPools, make_variant_isolated
        from pools import DonorPools
        from authguard7702.transformations import make_variant_isolated_safe
        make_variant_isolated = make_variant_isolated_safe
        pools = DonorPools(full, "benign_general", "outer_fold_primary", "AUTHGUARD_FUSION")
    for seed in args.seeds:
        for fold in args.folds:
            if fold not in range(5):
                raise ValueError(f"invalid outer fold: {fold}")
            val_fold = (fold + 1) % 5
            train_idx = np.flatnonzero((folds != fold) & (folds != val_fold))
            val_idx = np.flatnonzero(folds == val_fold)
            test_idx = np.flatnonzero(folds == fold)
            if args.smoke_limit:
                def limited(values):
                    per_class = max(2, args.smoke_limit // 2)
                    selected = np.concatenate([
                        values[y[values] == 0][:per_class],
                        values[y[values] == 1][:per_class],
                    ])
                    return np.sort(selected)
                train_idx, val_idx, test_idx = map(limited, (train_idx, val_idx, test_idx))
            mean = Xd[train_idx].mean(0)
            scale = Xd[train_idx].std(0); scale[scale < 1e-6] = 1.0

            needs_transform = any(MODEL_SPECS[name]["transformed"] for name in args.models)
            train_variants = None
            if needs_transform:
                pools.assert_disjoint(fold)
                train_variants = transformed_bank(
                    frame, train_idx, fold, "train", ["M1", "M2", "F50"], pools,
                    args.chunk_size, args.max_chunks, f"fusion:{seed}:{fold}:train")

            train_base = make_loaders(train_idx, source_indices, token_store, Xd, Xn, y,
                                      mean, scale, args.chunk_size, args.max_chunks,
                                      args.batch_size, shuffle=True)
            val_loader = make_loaders(val_idx, source_indices, token_store, Xd, Xn, y,
                                      mean, scale, args.chunk_size, args.max_chunks,
                                      args.batch_size)
            test_loader = make_loaders(test_idx, source_indices, token_store, Xd, Xn, y,
                                       mean, scale, args.chunk_size, args.max_chunks,
                                       args.batch_size)

            robustness_banks = {}
            if not args.skip_robustness:
                for condition in ("F200", "M3F200"):
                    rows = []
                    for index in test_idx:
                        variant = make_variant_isolated(
                            pools, frame.iloc[int(index)].to_dict(), fold, "test", condition,
                            f"fusion:{seed}:{fold}:test:{condition}")
                        rows.append(encode_bytecode(variant, args.chunk_size, args.max_chunks))
                    robustness_banks[condition] = rows

            benign_source_indices = np.flatnonzero(
                (full["class"].to_numpy() == "benign_general") &
                (full["outer_fold_secondary"].fillna(-1).to_numpy(dtype=int) == fold))
            if args.smoke_limit:
                benign_source_indices = benign_source_indices[:args.smoke_limit]
            benign_rows = [encode_bytecode(full.iloc[int(index)]["bytecode"],
                                           args.chunk_size, args.max_chunks)
                           for index in benign_source_indices]

            if not args.skip_baseline:
                baseline_conditions = ["cleanM0", *robustness_banks.keys(), "benign_general"]
                pending = [condition for condition in baseline_conditions
                           if f"{seed}:{fold}:hist_ngram_xgb:{condition}" not in completed]
                if pending:
                    baseline, val_scores, test_scores = fit_strongest_baseline(
                        hist_ngram[train_idx], y[train_idx], hist_ngram[val_idx],
                        hist_ngram[test_idx], seed)
                    policy = WarningPolicy.from_validation_negatives(val_scores[y[val_idx] == 0])
                    baseline_scores = {"cleanM0": test_scores}
                    for condition, encoded_rows in robustness_banks.items():
                        representation = np.hstack([
                            np.stack([row.dense[:225] for row in encoded_rows]),
                            np.stack([row.ngram for row in encoded_rows]),
                        ]).astype(np.float32)
                        baseline_scores[condition] = baseline.predict_proba(representation)[:, 1]
                    benign_representation = np.hstack([
                        np.stack([row.dense[:225] for row in benign_rows]),
                        np.stack([row.ngram for row in benign_rows]),
                    ]).astype(np.float32)
                    baseline_scores["benign_general"] = baseline.predict_proba(
                        benign_representation)[:, 1]
                    for condition in pending:
                        scores = baseline_scores[condition]
                        condition_y = (np.zeros(len(benign_rows), dtype=int)
                                       if condition == "benign_general" else y[test_idx])
                        result = evaluate(condition_y, scores, policy)
                        metrics_rows.append({"seed": seed, "fold": fold,
                                             "model": "hist_ngram_xgb",
                                             "condition": condition,
                                             **result, **policy.to_dict()})
                        condition_indices = (benign_source_indices if condition == "benign_general"
                                             else test_idx)
                        for local, index in enumerate(condition_indices):
                            source = full.iloc[int(index)] if condition == "benign_general" \
                                else frame.iloc[int(index)]
                            prediction_rows.append({
                                "seed": seed, "fold": fold, "model": "hist_ngram_xgb",
                                "condition": condition, "sid": source["sid"],
                                "family_id": source["family_id"],
                                "y": int(condition_y[local]),
                                "score": float(scores[local]),
                            })
                        completed.add(f"{seed}:{fold}:hist_ngram_xgb:{condition}")

            for model_name in args.models:
                key = f"{seed}:{fold}:{model_name}"
                if key in completed:
                    continue
                spec = MODEL_SPECS[model_name]
                transformed = train_variants if spec["transformed"] else None
                train_loader = make_loaders(
                    train_idx, source_indices, token_store, Xd, Xn, y, mean, scale,
                    args.chunk_size, args.max_chunks, args.batch_size,
                    transformed=transformed, shuffle=True) if transformed else train_base
                config = replace(FusionConfig(), active_views=spec["active_views"])
                print(f"[fusion] seed={seed} fold={fold} model={model_name}", flush=True)
                model, history, best_ap = train_model(
                    config, train_loader, val_loader, device, seed + fold, args.epochs,
                    args.patience, args.learning_rate, spec["auxiliary_weight"],
                    spec["consistency_weight"])
                for item in history:
                    history_rows.append({"seed": seed, "fold": fold,
                                         "model": model_name, **item})
                _, y_val, val_logits, _, _ = predict_logits(model, val_loader, device)
                test_indices, y_test, test_logits, test_aux, view_weights = predict_logits(
                    model, test_loader, device)
                temperature = fit_temperature(val_logits, y_val)
                val_scores = probabilities(val_logits, temperature)
                test_scores = probabilities(test_logits, temperature)
                policy = WarningPolicy.from_validation_negatives(val_scores[y_val == 0])
                result = evaluate(y_test, test_scores, policy)
                aux_targets = token_store.auxiliary[source_indices[test_indices]]
                aux_result = auxiliary_metrics(aux_targets, test_aux)
                metrics_rows.append({
                    "seed": seed, "fold": fold, "model": model_name,
                    "condition": "cleanM0", "temperature": temperature,
                    "best_val_AUPRC": best_ap, "aux_macro_AUPRC": aux_result["macro_AUPRC"],
                    **result, **policy.to_dict(),
                })
                for local, index in enumerate(test_indices):
                    prediction_rows.append({
                        "seed": seed, "fold": fold, "model": model_name,
                        "condition": "cleanM0", "sid": frame.iloc[index]["sid"],
                        "family_id": families[index], "y": int(y[index]),
                        "score": float(test_scores[local]),
                        "view_sequence": float(view_weights[local, 0]),
                        "view_ngram": float(view_weights[local, 1]),
                        "view_dense": float(view_weights[local, 2]),
                    })
                for condition, encoded_rows in robustness_banks.items():
                    robust_logits, _, _ = score_encoded_bank(
                        model, encoded_rows, y[test_idx], mean, scale, args.batch_size, device)
                    robust_scores = probabilities(robust_logits, temperature)
                    robust_result = evaluate(y[test_idx], robust_scores, policy)
                    metrics_rows.append({"seed": seed, "fold": fold, "model": model_name,
                                         "condition": condition, "temperature": temperature,
                                         "best_val_AUPRC": best_ap, **robust_result,
                                         **policy.to_dict()})
                    for local, index in enumerate(test_idx):
                        prediction_rows.append({
                            "seed": seed, "fold": fold, "model": model_name,
                            "condition": condition, "sid": frame.iloc[index]["sid"],
                            "family_id": families[index], "y": int(y[index]),
                            "score": float(robust_scores[local]),
                        })
                benign_logits, _, _ = score_encoded_bank(
                    model, benign_rows, np.zeros(len(benign_rows)), mean, scale,
                    args.batch_size, device)
                benign_scores = probabilities(benign_logits, temperature)
                benign_result = evaluate(np.zeros(len(benign_rows), dtype=int),
                                         benign_scores, policy)
                metrics_rows.append({"seed": seed, "fold": fold, "model": model_name,
                                     "condition": "benign_general", "temperature": temperature,
                                     "best_val_AUPRC": best_ap, **benign_result,
                                     **policy.to_dict()})
                for local, source_index in enumerate(benign_source_indices):
                    source = full.iloc[int(source_index)]
                    prediction_rows.append({
                        "seed": seed, "fold": fold, "model": model_name,
                        "condition": "benign_general", "sid": source["sid"],
                        "family_id": source["family_id"], "y": 0,
                        "score": float(benign_scores[local]),
                    })
                artifact = {
                    "model": model.state_dict(),
                    "config": config.to_dict(),
                    "dense_mean": torch.from_numpy(mean),
                    "dense_scale": torch.from_numpy(scale),
                    "temperature": torch.tensor(temperature),
                    "policy": policy.to_dict(),
                    "factor_order": list(AUXILIARY_FACTORS),
                    "auxiliary_trained": bool(spec["auxiliary_weight"] > 0),
                    "preprocessing": {"chunk_size": args.chunk_size,
                                      "max_chunks": args.max_chunks},
                }
                torch.save(artifact, os.path.join(OUT, f"model_{model_name}_s{seed}_f{fold}.pt"))
                completed.add(key)
                pd.DataFrame(metrics_rows).to_csv(os.path.join(OUT, "metrics.csv"), index=False)
                pd.DataFrame(prediction_rows).to_csv(
                    os.path.join(OUT, "predictions.csv.gz"), index=False, compression="gzip")
                pd.DataFrame(history_rows).to_csv(os.path.join(OUT, "history.csv"), index=False)
                with open(checkpoint_path, "w") as handle:
                    json.dump({"completed": sorted(completed), "device": str(device)}, handle,
                              indent=2)
                del model
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()

    metrics = pd.DataFrame(metrics_rows)
    summary = (metrics.groupby(["model", "condition"])
               [["AUPRC", "Recall_01", "Recall_05", "Recall_10",
                 "FPR_01", "FPR_05", "FPR_10", "Brier"]]
               .agg(["mean", "std"]).reset_index())
    summary.to_csv(os.path.join(OUT, "summary.csv"), index=False)
    with open(os.path.join(OUT, "run_metadata.json"), "w") as handle:
        json.dump({"models": args.models, "seeds": args.seeds, "device": str(device),
                   "epochs": args.epochs, "patience": args.patience,
                   "batch_size": args.batch_size, "chunk_size": args.chunk_size,
                   "max_chunks": args.max_chunks, "frozen_verified": True}, handle, indent=2)
    if verify_frozen() != 0:
        raise RuntimeError("frozen-artifact verification failed after experiment")
    print(summary.to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
