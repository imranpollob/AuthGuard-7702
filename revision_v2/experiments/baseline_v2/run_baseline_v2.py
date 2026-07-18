#!/usr/bin/env python3
"""Fair multi-model baseline comparison on the corrected AuthGuardBench-7702 v2 primary task.

Models (identical family-disjoint protocol, seeds 7702/7703/7704, all 5 outer folds):
  hist_ngram_xgb   opcode histogram (225) + hashed 4-gram (512) XGBoost   [traditional]
  dense_only       MLP over 261-dim structural/histogram/selector features [existing]
  ngram_only       MLP over 512-dim hashed 4-gram features                 [existing]
  flat_cnn         non-hierarchical 1D opcode-sequence CNN                  [new]
  bigru            bidirectional GRU over opcode tokens                     [new]
  transformer      compact Transformer encoder over opcode tokens          [new]
  authguard_seq    hierarchical chunk-attention sequence model (proposed)  [unchanged]

Protocol per outer fold f: validation = (f+1) mod 5, training = the other three folds.
Calibration: temperature scaling fit on validation only. Warning thresholds: from
validation-negative scores at 1%/5%/10% FPR. No test-set tuning. Metrics on the held-out
test fold. Fold means -> per-seed means -> 3-seed mean/SD.

Frozen originals are read-only; every output is written under
revision_v2/experiments/baseline_v2/ (results mirrored to revision_v2/results/baseline_v2).
"""
from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
import sys
import time
from dataclasses import replace

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import average_precision_score, roc_auc_score
from torch import nn
from torch.nn.utils.rnn import pack_padded_sequence, pad_packed_sequence
from torch.utils.data import DataLoader, Dataset

HERE = os.path.dirname(os.path.abspath(__file__))
RV2 = os.path.abspath(os.path.join(HERE, "..", ".."))
ROOT = os.path.abspath(os.path.join(RV2, ".."))
OUT = HERE
MIRROR = os.path.join(RV2, "results", "baseline_v2")
BENCH = os.path.join(RV2, "data", "authguardbench_7702_v2.csv.gz")

sys.path.insert(0, RV2)
sys.path.insert(0, os.path.join(RV2, "experiments", "common"))


def _load(module_name, path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fusion = _load("fusion_run", os.path.join(
    RV2, "experiments", "authguard_fusion", "run_authguard_fusion.py"))
sanity = _load("run_sanity_v2", os.path.join(
    RV2, "audit", "scripts", "run_sanity_v2.py"))

from authguard7702.features import PAD_ID, VOCAB_SIZE  # noqa: E402
from authguard7702.model import FusionConfig  # noqa: E402
from authguard7702.policy import WarningPolicy  # noqa: E402
from frozen import verify as verify_frozen  # noqa: E402
from xgboost import XGBClassifier  # noqa: E402

SEEDS = [7702, 7703, 7704]
EPOCHS = 30
PATIENCE = 5
FUSION_BATCH = 16
FLAT_BATCH = 32
MAX_LEN = {"flat_cnn": 2048, "bigru": 2048, "transformer": 1024}
METRIC_COLUMNS = ["AUPRC", "AUROC", "Brier", "Recall_01", "FPR_01",
                  "Recall_05", "FPR_05", "Recall_10", "FPR_10"]


# --------------------------------------------------------------------------- models
class FlatCNN(nn.Module):
    """Non-hierarchical opcode-sequence CNN: embed -> 2 conv blocks -> masked max-pool."""

    def __init__(self, vocab=VOCAB_SIZE, emb=64, channels=128, dropout=0.1):
        super().__init__()
        self.embedding = nn.Embedding(vocab, emb, padding_idx=PAD_ID)
        self.conv1 = nn.Conv1d(emb, channels, kernel_size=7, padding=3)
        self.conv2 = nn.Conv1d(channels, channels, kernel_size=5, padding=2)
        self.act = nn.GELU()
        self.dropout = nn.Dropout(dropout)
        self.head = nn.Linear(channels, 1)

    def forward(self, tokens, lengths):
        mask = tokens != PAD_ID
        x = self.embedding(tokens).transpose(1, 2)
        x = self.act(self.conv1(x))
        x = self.act(self.conv2(x)).transpose(1, 2)
        x = x.masked_fill(~mask.unsqueeze(-1), -1.0e4)
        pooled = x.amax(dim=1)
        return self.head(self.dropout(pooled)).squeeze(-1)


class BiGRU(nn.Module):
    """Bidirectional GRU over opcode tokens.

    Readout concatenates the final hidden state of each direction (the standard
    sequence-classification readout) with a masked mean of the outputs; packed
    sequences give the GRU exact per-row lengths so padding never contributes.
    """

    def __init__(self, vocab=VOCAB_SIZE, emb=64, hidden=96, dropout=0.1):
        super().__init__()
        self.embedding = nn.Embedding(vocab, emb, padding_idx=PAD_ID)
        self.gru = nn.GRU(emb, hidden, batch_first=True, bidirectional=True)
        self.dropout = nn.Dropout(dropout)
        self.head = nn.Linear(hidden * 4, 1)

    def forward(self, tokens, lengths):
        x = self.embedding(tokens)
        clamped = lengths.cpu().clamp(min=1)
        packed = pack_padded_sequence(x, clamped, batch_first=True, enforce_sorted=False)
        out, hidden = self.gru(packed)
        out, _ = pad_packed_sequence(out, batch_first=True, total_length=tokens.shape[1])
        last = torch.cat([hidden[-2], hidden[-1]], dim=1)  # forward + backward final state
        mask = (tokens != PAD_ID).unsqueeze(-1).float()
        pooled = (out * mask).sum(1) / mask.sum(1).clamp(min=1.0)
        return self.head(self.dropout(torch.cat([last, pooled], dim=1))).squeeze(-1)


class TransformerEncoderModel(nn.Module):
    """Compact Transformer encoder over opcode tokens with masked mean pooling."""

    def __init__(self, vocab=VOCAB_SIZE, d_model=128, nhead=4, layers=2, ff=256,
                 max_len=1024, dropout=0.1):
        super().__init__()
        self.embedding = nn.Embedding(vocab, d_model, padding_idx=PAD_ID)
        self.position = nn.Embedding(max_len, d_model)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model, nhead, dim_feedforward=ff, dropout=dropout, batch_first=True,
            activation="gelu")
        self.encoder = nn.TransformerEncoder(encoder_layer, layers)
        self.dropout = nn.Dropout(dropout)
        self.head = nn.Linear(d_model, 1)
        self.max_len = max_len

    def forward(self, tokens, lengths):
        length = tokens.shape[1]
        positions = torch.arange(length, device=tokens.device).clamp(max=self.max_len - 1)
        x = self.embedding(tokens) + self.position(positions).unsqueeze(0)
        pad_mask = tokens == PAD_ID
        hidden = self.encoder(x, src_key_padding_mask=pad_mask)
        keep = (~pad_mask).unsqueeze(-1).float()
        pooled = (hidden * keep).sum(1) / keep.sum(1).clamp(min=1.0)
        return self.head(self.dropout(pooled)).squeeze(-1)


FLAT_CTORS = {
    "flat_cnn": lambda: FlatCNN(),
    "bigru": lambda: BiGRU(),
    "transformer": lambda: TransformerEncoderModel(max_len=MAX_LEN["transformer"]),
}
FUSION_VIEWS = {
    "dense_only": (False, False, True),
    "ngram_only": (False, True, False),
    "authguard_seq": (True, False, False),
}


# --------------------------------------------------------------------------- data
class FlatDataset(Dataset):
    def __init__(self, indices, matrix, lengths, labels):
        self.indices = np.asarray(indices, dtype=int)
        self.matrix = matrix
        self.lengths = lengths
        self.labels = labels

    def __len__(self):
        return len(self.indices)

    def __getitem__(self, offset):
        index = int(self.indices[offset])
        return (index, self.matrix[index], self.lengths[index], float(self.labels[index]))


def flat_collate(batch):
    indices, tokens, lengths, labels = zip(*batch)
    return (np.asarray(indices, dtype=int),
            torch.from_numpy(np.stack(tokens)).long(),
            torch.tensor(lengths, dtype=torch.long),
            torch.tensor(labels, dtype=torch.float32))


def build_flat_matrix(token_store, count, max_len):
    """Uniform-stride whole-sequence sampling to a fixed length (documented strategy).

    Contracts <= max_len are seen at full resolution; longer contracts are evenly
    downsampled across their entire opcode stream, mirroring AuthGuard-Seq's chunk
    sampling so the flat models see the whole contract, not only a prefix.
    """
    matrix = np.zeros((count, max_len), dtype=np.int64)
    lengths = np.zeros(count, dtype=np.int64)
    for index in range(count):
        tokens = token_store.row(index)
        if not len(tokens):
            tokens = np.asarray([1], dtype=np.int64)
        if len(tokens) > max_len:
            chosen = np.linspace(0, len(tokens) - 1, max_len).round().astype(int)
            tokens = tokens[chosen]
        matrix[index, :len(tokens)] = tokens
        lengths[index] = len(tokens)
    return matrix, lengths


def flat_loader(indices, matrix, lengths, labels, batch_size, shuffle):
    dataset = FlatDataset(indices, matrix, lengths, labels)
    return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle,
                      collate_fn=flat_collate, num_workers=0,
                      pin_memory=torch.cuda.is_available())


# ----------------------------------------------------------------------- training
def train_flat(ctor, train_loader, val_loader, device, seed, pos_weight):
    fusion.set_seed(seed)
    model = ctor().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([pos_weight], device=device))
    best_ap, best_state, stale = -np.inf, None, 0
    for epoch in range(1, EPOCHS + 1):
        model.train()
        for _, tokens, lengths, labels in train_loader:
            tokens, labels = tokens.to(device), labels.to(device)
            logits = model(tokens, lengths)
            loss = loss_fn(logits, labels)
            if not torch.isfinite(loss):
                raise FloatingPointError(f"non-finite loss at epoch {epoch}")
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            optimizer.step()
        _, y_val, val_logits = predict_flat(model, val_loader, device)
        ap = float(average_precision_score(y_val, val_logits))
        if ap > best_ap + 1e-5:
            best_ap, best_state, stale = ap, {k: v.detach().cpu().clone()
                                              for k, v in model.state_dict().items()}, 0
        else:
            stale += 1
            if stale >= PATIENCE:
                break
    model.load_state_dict(best_state)
    return model, best_ap


def predict_flat(model, loader, device):
    model.eval()
    indices, labels, logits = [], [], []
    with torch.no_grad():
        for batch_indices, tokens, lengths, batch_labels in loader:
            out = model(tokens.to(device), lengths)
            if not torch.isfinite(out).all():
                raise FloatingPointError("non-finite flat-model logits")
            indices.extend(batch_indices.tolist())
            labels.extend(batch_labels.tolist())
            logits.extend(out.cpu().numpy().tolist())
    return np.asarray(indices), np.asarray(labels), np.asarray(logits)


# -------------------------------------------------------------------- calibration
def calibrate_and_eval(val_logits, y_val, test_logits, y_test):
    temperature = fusion.fit_temperature(val_logits, y_val)
    val_probs = fusion.probabilities(val_logits, temperature)
    test_probs = fusion.probabilities(test_logits, temperature)
    policy = WarningPolicy.from_validation_negatives(val_probs[y_val == 0])
    metrics = fusion.evaluate(y_test, test_probs, policy)
    metrics["AUROC"] = (float(roc_auc_score(y_test, test_probs))
                        if len(np.unique(y_test)) == 2 else None)
    raw_probs = 1.0 / (1.0 + np.exp(-np.clip(test_logits, -40, 40)))
    return metrics, temperature, policy, test_probs, raw_probs


def logit_from_proba(proba):
    proba = np.clip(proba, 1e-6, 1 - 1e-6)
    return np.log(proba / (1 - proba))


# --------------------------------------------------------------- model complexity
def torch_complexity(model):
    params = int(sum(p.numel() for p in model.parameters() if p.requires_grad))
    buffer = io.BytesIO()
    torch.save(model.state_dict(), buffer)
    return params, int(buffer.getbuffer().nbytes)


def measure_torch_latency(model, sample_batches, device):
    model = model.to(device).eval()
    times = []
    with torch.no_grad():
        for tokens, lengths in sample_batches[:5]:  # warmup
            model(tokens.to(device), lengths)
        for tokens, lengths in sample_batches:
            start = time.perf_counter()
            model(tokens.to(device), lengths)
            times.append((time.perf_counter() - start) * 1000.0)
    return times


def latency_summary(times):
    times = np.asarray(times, dtype=float)
    return {"latency_ms_mean": float(times.mean()),
            "latency_ms_median": float(np.median(times)),
            "latency_ms_p95": float(np.percentile(times, 95))}


# ------------------------------------------------------------------------- driver
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", nargs="+", type=int, default=SEEDS)
    parser.add_argument("--folds", nargs="+", type=int, default=list(range(5)))
    parser.add_argument("--models", nargs="+", default=list(
        ["hist_ngram_xgb", "dense_only", "ngram_only", "flat_cnn", "bigru",
         "transformer", "authguard_seq"]))
    parser.add_argument("--epochs", type=int, default=EPOCHS)
    args = parser.parse_args()
    globals()["EPOCHS"] = args.epochs

    os.makedirs(OUT, exist_ok=True)
    os.makedirs(MIRROR, exist_ok=True)
    if verify_frozen() != 0:
        raise RuntimeError("frozen-artifact verification failed")

    bench = pd.read_csv(BENCH)
    frame = bench[bench["population"] == "PRIMARY_EVALUATION"].reset_index(drop=True)
    assert not frame["bytecode_repaired"].any()
    assert len(frame) == 2190 and int(frame["label"].sum()) == 727
    print(f"[baseline] primary rows={len(frame)} pos={int(frame['label'].sum())} "
          f"models={args.models}", flush=True)

    features = sanity.build_features(frame, os.path.join(OUT, "features_v2.npz"))
    token_store = sanity.LocalTokenStore(features["tokens"], features["offsets"],
                                         features["auxiliary"])
    Xd = features["dense"]
    Xn = features["ngram"]
    y = frame["label"].to_numpy(dtype=int)
    folds = frame["fold_id"].to_numpy(dtype=int)
    families = frame["family_id"].astype(str).to_numpy()
    sids = frame["sample_id"].astype(str).to_numpy()
    hist_ngram = np.hstack([Xd[:, :225], Xn]).astype(np.float32)
    source_indices = np.arange(len(frame))
    flat_matrices = {name: build_flat_matrix(token_store, len(frame), MAX_LEN[name])
                     for name in FLAT_CTORS}

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[baseline] device={device}", flush=True)

    metric_rows, prediction_rows, complexity_rows = [], [], []
    checkpoint = os.path.join(OUT, "checkpoint.json")
    done = set()
    if os.path.exists(checkpoint):
        state = json.load(open(checkpoint))
        done = set(tuple(k) for k in state["done"])
        metric_rows = state["metrics"]
        complexity_rows = state["complexity"]
        prediction_rows = pd.read_csv(
            os.path.join(OUT, "baseline_predictions.csv.gz")).to_dict("records") \
            if os.path.exists(os.path.join(OUT, "baseline_predictions.csv.gz")) else []

    def persist():
        pd.DataFrame(metric_rows).to_csv(
            os.path.join(OUT, "baseline_fold_seed_results.csv"), index=False)
        pd.DataFrame(prediction_rows).to_csv(
            os.path.join(OUT, "baseline_predictions.csv.gz"), index=False,
            compression="gzip")
        json.dump({"done": [list(k) for k in done], "metrics": metric_rows,
                   "complexity": complexity_rows}, open(checkpoint, "w"))

    def record(model_name, seed, fold, metrics, temperature, best_val, policy,
               test_indices, calib, raw):
        row = {"model": model_name, "seed": seed, "fold": fold,
               "temperature": temperature, "best_val_AUPRC": best_val,
               "threshold_01": policy.threshold_01, "threshold_05": policy.threshold_05,
               "threshold_10": policy.threshold_10}
        row.update({key: metrics.get(key) for key in METRIC_COLUMNS})
        metric_rows.append(row)
        for local, index in enumerate(test_indices):
            index = int(index)
            prediction_rows.append({
                "sample_id": sids[index], "family_id": families[index], "fold": fold,
                "seed": seed, "model": model_name, "true_label": int(y[index]),
                "raw_score": float(raw[local]), "calibrated_score": float(calib[local]),
                "threshold_01": policy.threshold_01, "threshold_05": policy.threshold_05,
                "threshold_10": policy.threshold_10})

    for seed in args.seeds:
        for fold in args.folds:
            val_fold = (fold + 1) % 5
            train_idx = np.flatnonzero((folds != fold) & (folds != val_fold))
            val_idx = np.flatnonzero(folds == val_fold)
            test_idx = np.flatnonzero(folds == fold)
            mean = Xd[train_idx].mean(0)
            scale = Xd[train_idx].std(0)
            scale[scale < 1e-6] = 1.0
            pos_weight = float((y[train_idx] == 0).sum() / max((y[train_idx] == 1).sum(), 1))
            measure = (seed == args.seeds[0] and fold == 0)

            for model_name in args.models:
                if (model_name, seed, fold) in done:
                    continue
                start = time.time()
                if model_name == "hist_ngram_xgb":
                    model = XGBClassifier(random_state=seed, **fusion.XGB_HP)
                    model.fit(hist_ngram[train_idx], y[train_idx])
                    val_logits = logit_from_proba(model.predict_proba(hist_ngram[val_idx])[:, 1])
                    test_logits = logit_from_proba(model.predict_proba(hist_ngram[test_idx])[:, 1])
                    metrics, temperature, policy, calib, raw = calibrate_and_eval(
                        val_logits, y[val_idx], test_logits, y[test_idx])
                    record(model_name, seed, fold, metrics, temperature, None, policy,
                           test_idx, calib, raw)
                    if measure:
                        buffer = io.BytesIO()
                        model.get_booster().save_model(os.path.join(OUT, "_xgb.json"))
                        size = os.path.getsize(os.path.join(OUT, "_xgb.json"))
                        os.remove(os.path.join(OUT, "_xgb.json"))
                        sample = hist_ngram[test_idx][:200]
                        for feats in sample[:5]:
                            model.predict_proba(feats.reshape(1, -1))
                        times = []
                        for feats in sample:
                            t0 = time.perf_counter()
                            model.predict_proba(feats.reshape(1, -1))
                            times.append((time.perf_counter() - t0) * 1000.0)
                        complexity_rows.append({
                            "model": model_name, "trainable_params": None,
                            "serialized_bytes": int(size), "device": "cpu",
                            **latency_summary(times)})

                elif model_name in FUSION_VIEWS:
                    config = replace(FusionConfig(), active_views=FUSION_VIEWS[model_name])
                    train_loader = fusion.make_loaders(
                        train_idx, source_indices, token_store, Xd, Xn, y, mean, scale,
                        256, 64, FUSION_BATCH, shuffle=True)
                    val_loader = fusion.make_loaders(
                        val_idx, source_indices, token_store, Xd, Xn, y, mean, scale,
                        256, 64, FUSION_BATCH)
                    test_loader = fusion.make_loaders(
                        test_idx, source_indices, token_store, Xd, Xn, y, mean, scale,
                        256, 64, FUSION_BATCH)
                    net, _, best_val = fusion.train_model(
                        config, train_loader, val_loader, device, seed + fold,
                        args.epochs, PATIENCE, 1e-3, 0.0, 0.0)
                    _, y_val, val_logits, _, _ = fusion.predict_logits(net, val_loader, device)
                    test_indices, y_test, test_logits, _, _ = fusion.predict_logits(
                        net, test_loader, device)
                    metrics, temperature, policy, calib, raw = calibrate_and_eval(
                        val_logits, y_val, test_logits, y_test)
                    record(model_name, seed, fold, metrics, temperature, best_val, policy,
                           test_indices, calib, raw)
                    if measure:
                        params, size = torch_complexity(net)
                        complexity_rows.append({
                            "model": model_name, "trainable_params": params,
                            "serialized_bytes": size, "device": "cpu",
                            **fusion_latency(net, test_idx, source_indices, token_store,
                                             Xd, Xn, y, mean, scale)})

                else:  # flat neural
                    matrix, lengths = flat_matrices[model_name]
                    train_loader = flat_loader(train_idx, matrix, lengths, y,
                                               FLAT_BATCH, True)
                    val_loader = flat_loader(val_idx, matrix, lengths, y, FLAT_BATCH, False)
                    test_loader = flat_loader(test_idx, matrix, lengths, y, FLAT_BATCH, False)
                    net, best_val = train_flat(FLAT_CTORS[model_name], train_loader,
                                               val_loader, device, seed + fold, pos_weight)
                    _, y_val, val_logits = predict_flat(net, val_loader, device)
                    test_indices, y_test, test_logits = predict_flat(net, test_loader, device)
                    metrics, temperature, policy, calib, raw = calibrate_and_eval(
                        val_logits, y_val, test_logits, y_test)
                    record(model_name, seed, fold, metrics, temperature, best_val, policy,
                           test_indices, calib, raw)
                    if measure:
                        params, size = torch_complexity(net)
                        cpu_net = net.to("cpu")
                        batches = []
                        for index in test_idx[:200]:
                            toks = torch.from_numpy(matrix[index:index + 1]).long()
                            batches.append((toks, torch.tensor([lengths[index]])))
                        times = measure_torch_latency(cpu_net, batches, torch.device("cpu"))
                        complexity_rows.append({
                            "model": model_name, "trainable_params": params,
                            "serialized_bytes": size, "device": "cpu",
                            **latency_summary(times)})
                        net.to(device)

                done.add((model_name, seed, fold))
                print(f"[baseline] seed={seed} fold={fold} {model_name} "
                      f"AUPRC={metrics['AUPRC']:.4f} AUROC={metrics['AUROC']:.4f} "
                      f"R@5={metrics['Recall_05']:.3f} ({time.time() - start:.1f}s)",
                      flush=True)
                persist()

    aggregate(metric_rows, complexity_rows)
    for name in ("baseline_fold_seed_results.csv", "baseline_predictions.csv.gz",
                 "baseline_summary.csv", "baseline_model_complexity.csv"):
        source = os.path.join(OUT, name)
        if os.path.exists(source):
            pd.read_csv(source).to_csv(os.path.join(MIRROR, name), index=False)
    if verify_frozen() != 0:
        raise RuntimeError("frozen-artifact verification failed after run")
    print("[baseline] complete", flush=True)
    return 0


def fusion_latency(net, test_idx, source_indices, token_store, Xd, Xn, y, mean, scale):
    device = torch.device("cpu")
    net = net.to(device).eval()
    loader = fusion.make_loaders(test_idx[:200], source_indices, token_store, Xd, Xn, y,
                                 mean, scale, 256, 64, 1)
    times = []
    with torch.no_grad():
        for count, batch in enumerate(loader):
            view = fusion.to_device(batch["clean"], device)
            if count < 5:
                net(**view)
                continue
            start = time.perf_counter()
            net(**view)
            times.append((time.perf_counter() - start) * 1000.0)
    return latency_summary(times)


def aggregate(metric_rows, complexity_rows):
    frame = pd.DataFrame(metric_rows)
    per_seed = (frame.groupby(["model", "seed"])[METRIC_COLUMNS].mean().reset_index())
    summary = []
    for model_name, group in per_seed.groupby("model"):
        row = {"model": model_name, "n_seeds": int(group["seed"].nunique())}
        for column in METRIC_COLUMNS:
            row[f"{column}_mean"] = float(group[column].mean())
            row[f"{column}_sd"] = float(group[column].std(ddof=0))
        summary.append(row)
    summary_frame = pd.DataFrame(summary).sort_values("AUPRC_mean", ascending=False)
    summary_frame.to_csv(os.path.join(OUT, "baseline_summary.csv"), index=False)
    if complexity_rows:
        pd.DataFrame(complexity_rows).to_csv(
            os.path.join(OUT, "baseline_model_complexity.csv"), index=False)
    print(summary_frame[["model", "AUPRC_mean", "AUPRC_sd", "Recall_05_mean",
                         "AUROC_mean"]].round(4).to_string(index=False))


if __name__ == "__main__":
    sys.exit(main())
