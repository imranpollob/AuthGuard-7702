#!/usr/bin/env python3
"""Controlled long-context contribution study for AuthGuard-7702.

The first five configurations share an embedding, convolutional encoder, dropout, and
risk head. They vary only token layout, token budget, and chunk aggregation. The sixth
configuration retrains the paper's AuthGuard-Seq architecture under the same corrected
16,384-token cap. Clean and donor-isolated F200 inputs always obey the declared budget.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, replace
import gc
import io
import json
import os
import random
import sys
import time

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import average_precision_score, roc_auc_score
from torch import nn
from torch.utils.data import DataLoader, Dataset, Sampler

HERE = os.path.dirname(os.path.abspath(__file__))
RV2 = os.path.abspath(os.path.join(HERE, "..", ".."))
ROOT = os.path.abspath(os.path.join(RV2, ".."))
RESULT_ROOT = os.path.join(RV2, "results", "long_context_ablation_v3")
BENCH_PATH = os.path.join(RV2, "data", "authguardbench_7702_v2.csv.gz")
FEATURE_PATH = os.path.join(RV2, "experiments", "baseline_v2", "features_v2.npz")
PROTOCOL_PATH = os.path.join(RV2, "protocols", "long_context_ablation_v3.md")

sys.path.insert(0, RV2)
sys.path.insert(0, os.path.join(RV2, "experiments", "common"))
sys.path.insert(0, os.path.join(RV2, "experiments", "donor_pools"))
sys.path.insert(0, os.path.join(RV2, "experiments", "authguard_fusion"))

from authguard7702.features import (EncodedBytecode, PAD_ID, VOCAB_SIZE,  # noqa: E402
                                    opcode_chunks)
from authguard7702.model import AuthGuardFusion, FusionConfig  # noqa: E402
from authguard7702.policy import WarningPolicy  # noqa: E402
from authguard7702.transformations import make_variant_isolated_safe  # noqa: E402
from frozen import verify as verify_frozen  # noqa: E402
from pools import DonorPools  # noqa: E402
import run_authguard_fusion as fusion  # noqa: E402

SEEDS = (7702, 7703, 7704)
FOLDS = tuple(range(5))
CHUNK_SIZE = 256
METRIC_COLUMNS = (
    "AUPRC", "AUROC", "Brier", "Recall_01", "FPR_01",
    "Recall_05", "FPR_05", "Recall_10", "FPR_10",
)


@dataclass(frozen=True)
class ModelSpec:
    name: str
    layout: str
    aggregation: str
    token_budget: int
    reference: bool = False

    @property
    def max_chunks(self) -> int:
        return self.token_budget // CHUNK_SIZE


SPECS = {
    spec.name: spec for spec in (
        ModelSpec("flat_control_2048", "flat", "flat", 2_048),
        ModelSpec("flat_control_16384", "flat", "flat", 16_384),
        ModelSpec("chunk_attention_control_2048", "chunk", "attention", 2_048),
        ModelSpec("chunk_mean_control_16384", "chunk", "mean", 16_384),
        ModelSpec("chunk_attention_control_16384", "chunk", "attention", 16_384),
        ModelSpec("authguard_reference_16384", "chunk", "attention", 16_384, True),
    )
}

CONTRASTS = {
    "coverage": ("chunk_attention_control_16384", "chunk_attention_control_2048"),
    "attention": ("chunk_attention_control_16384", "chunk_mean_control_16384"),
    "hierarchy": ("chunk_attention_control_16384", "flat_control_16384"),
}


class RaggedTokenStore:
    def __init__(self, tokens: np.ndarray, offsets: np.ndarray):
        self.tokens = tokens
        self.offsets = offsets

    def __len__(self) -> int:
        return len(self.offsets) - 1

    def row(self, index: int) -> np.ndarray:
        return self.tokens[self.offsets[index]:self.offsets[index + 1]].astype(
            np.int64, copy=False)


def select_representation(tokens: np.ndarray, spec: ModelSpec) -> np.ndarray:
    """Apply the declared budget across the full opcode stream."""
    tokens = np.asarray(tokens, dtype=np.int64)
    if not len(tokens):
        tokens = np.asarray([1], dtype=np.int64)
    if spec.layout == "flat":
        if len(tokens) > spec.token_budget:
            chosen = np.linspace(0, len(tokens) - 1, spec.token_budget).round().astype(int)
            tokens = tokens[chosen]
        return tokens.reshape(1, -1)
    count = int(np.ceil(len(tokens) / CHUNK_SIZE))
    chunks = np.full((count, CHUNK_SIZE), PAD_ID, dtype=np.int64)
    for index in range(count):
        part = tokens[index * CHUNK_SIZE:(index + 1) * CHUNK_SIZE]
        chunks[index, :len(part)] = part
    if len(chunks) > spec.max_chunks:
        chosen = np.linspace(0, len(chunks) - 1, spec.max_chunks).round().astype(int)
        chunks = chunks[chosen]
    return chunks


def retained_token_count(tokens: np.ndarray, spec: ModelSpec) -> int:
    return int((select_representation(tokens, spec) != PAD_ID).sum())


class SequenceDataset(Dataset):
    def __init__(self, indices, store: RaggedTokenStore, labels, spec: ModelSpec):
        self.indices = np.asarray(indices, dtype=int)
        self.store = store
        self.labels = np.asarray(labels, dtype=int)
        self.spec = spec

    def __len__(self):
        return len(self.indices)

    def __getitem__(self, offset):
        index = int(self.indices[offset])
        return index, select_representation(self.store.row(index), self.spec), \
            float(self.labels[index])


class LengthBucketBatchSampler(Sampler):
    """Shuffle length-local batches to reduce CPU padding without changing examples."""

    def __init__(self, dataset: SequenceDataset, batch_size: int, seed: int):
        self.dataset = dataset
        self.batch_size = int(batch_size)
        self.seed = int(seed)
        self.epoch = 0
        lengths = np.diff(dataset.store.offsets)[dataset.indices]
        if dataset.spec.layout == "flat":
            keys = np.minimum(lengths, dataset.spec.token_budget)
        else:
            keys = np.minimum(
                np.ceil(lengths / CHUNK_SIZE).astype(int),
                dataset.spec.max_chunks,
            )
        self.sorted_offsets = np.argsort(keys, kind="stable")

    def __len__(self):
        return int(np.ceil(len(self.sorted_offsets) / self.batch_size))

    def __iter__(self):
        rng = np.random.default_rng(self.seed + self.epoch)
        self.epoch += 1
        batches = []
        bucket_size = self.batch_size * 8
        for start in range(0, len(self.sorted_offsets), bucket_size):
            bucket = self.sorted_offsets[start:start + bucket_size].copy()
            rng.shuffle(bucket)
            batches.extend(
                bucket[offset:offset + self.batch_size].tolist()
                for offset in range(0, len(bucket), self.batch_size)
            )
        rng.shuffle(batches)
        yield from batches


def sequence_collate(batch):
    indices, representations, labels = zip(*batch)
    max_chunks = max(row.shape[0] for row in representations)
    max_width = max(row.shape[1] for row in representations)
    chunks = np.full((len(batch), max_chunks, max_width), PAD_ID, dtype=np.int64)
    chunk_mask = np.zeros((len(batch), max_chunks), dtype=np.bool_)
    for offset, row in enumerate(representations):
        chunks[offset, :row.shape[0], :row.shape[1]] = row
        chunk_mask[offset, :row.shape[0]] = True
    size = len(batch)
    return {
        "indices": np.asarray(indices, dtype=int),
        "labels": torch.tensor(labels, dtype=torch.float32),
        "view": {
            "chunks": torch.from_numpy(chunks),
            "chunk_mask": torch.from_numpy(chunk_mask),
            "dense": torch.zeros((size, 261), dtype=torch.float32),
            "ngram": torch.zeros((size, 512), dtype=torch.float32),
        },
    }


def make_loader(indices, store, labels, spec, batch_size, shuffle=False, seed=7702):
    dataset = SequenceDataset(indices, store, labels, spec)
    if shuffle:
        return DataLoader(
            dataset,
            batch_sampler=LengthBucketBatchSampler(dataset, batch_size, seed),
            collate_fn=sequence_collate,
            num_workers=0,
            pin_memory=False,
        )
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=False,
        collate_fn=sequence_collate,
        num_workers=0,
        pin_memory=False,
    )


class ControlledSequenceCNN(nn.Module):
    """Parameter-matched flat/chunk sequence control.

    All variants use the local encoder from AuthGuard-Seq. Only representation layout and
    aggregation differ; attention adds one 64-to-1 linear layer (65 parameters).
    """

    def __init__(self, aggregation: str, dropout: float = 0.15):
        super().__init__()
        if aggregation not in {"flat", "mean", "attention"}:
            raise ValueError(aggregation)
        self.aggregation = aggregation
        self.embedding = nn.Embedding(VOCAB_SIZE, 32, padding_idx=PAD_ID)
        self.encoder = nn.Sequential(
            nn.Conv1d(32, 64, kernel_size=5, padding=2),
            nn.GELU(),
            nn.Conv1d(64, 64, kernel_size=3, padding=2, dilation=2),
            nn.GELU(),
        )
        self.chunk_attention = nn.Linear(64, 1) if aggregation == "attention" else None
        self.dropout = nn.Dropout(dropout)
        self.risk_head = nn.Linear(64, 1)

    def forward(self, chunks, chunk_mask, dense, ngram):
        del dense, ngram
        batch, n_chunks, width = chunks.shape
        flat = chunks.reshape(batch * n_chunks, width)
        embedded = self.embedding(flat).transpose(1, 2)
        encoded = self.encoder(embedded)
        token_mask = flat.ne(PAD_ID).unsqueeze(1)
        encoded = encoded.masked_fill(~token_mask, -1.0e4)
        vectors = encoded.amax(dim=2).reshape(batch, n_chunks, -1)
        vectors = vectors.masked_fill(~chunk_mask.unsqueeze(-1), 0.0)
        if self.aggregation == "flat":
            if n_chunks != 1:
                raise RuntimeError("flat control received more than one chunk")
            attention = chunk_mask.to(vectors.dtype)
            sequence = vectors[:, 0]
        elif self.aggregation == "mean":
            attention = chunk_mask.to(vectors.dtype)
            attention = attention / attention.sum(dim=1, keepdim=True).clamp(min=1.0)
            sequence = (vectors * attention.unsqueeze(-1)).sum(dim=1)
        else:
            logits = self.chunk_attention(vectors).squeeze(-1)
            logits = logits.masked_fill(~chunk_mask, -1.0e4)
            attention = torch.softmax(logits, dim=1)
            sequence = (vectors * attention.unsqueeze(-1)).sum(dim=1)
        risk = self.risk_head(self.dropout(sequence)).squeeze(-1)
        return {
            "risk_logit": risk,
            "auxiliary_logits": risk.new_zeros((batch, 6)),
            "embedding": sequence,
            "view_weights": risk.new_ones((batch, 1)),
            "chunk_attention": attention,
        }


def set_seed(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(False)


def make_model(spec: ModelSpec) -> nn.Module:
    if spec.reference:
        config = replace(FusionConfig(), active_views=(True, False, False))
        return AuthGuardFusion(config)
    return ControlledSequenceCNN(spec.aggregation)


def to_device(view: dict, device: torch.device) -> dict:
    return {name: tensor.to(device) for name, tensor in view.items()}


def predict(model, loader, device):
    model.eval()
    indices, labels, logits = [], [], []
    with torch.no_grad():
        for batch in loader:
            output = model(**to_device(batch["view"], device))["risk_logit"]
            if not torch.isfinite(output).all():
                raise FloatingPointError("non-finite logits during scoring")
            indices.extend(batch["indices"].tolist())
            labels.extend(batch["labels"].numpy().tolist())
            logits.extend(output.cpu().numpy().tolist())
    return np.asarray(indices), np.asarray(labels), np.asarray(logits)


def train_model(model, train_loader, val_loader, y_train, device, seed, epochs,
                patience, learning_rate):
    set_seed(seed)
    model = model.to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=1e-4)
    y_train = np.asarray(y_train, dtype=int)
    pos_weight = float((y_train == 0).sum() / max((y_train == 1).sum(), 1))
    loss_fn = nn.BCEWithLogitsLoss(
        pos_weight=torch.tensor([pos_weight], device=device, dtype=torch.float32))
    best_ap, best_state, stale, history = -np.inf, None, 0, []
    for epoch in range(1, epochs + 1):
        model.train()
        losses = []
        for batch in train_loader:
            labels = batch["labels"].to(device)
            logits = model(**to_device(batch["view"], device))["risk_logit"]
            loss = loss_fn(logits, labels)
            if not torch.isfinite(loss):
                raise FloatingPointError(f"non-finite loss at epoch {epoch}")
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            optimizer.step()
            losses.append(float(loss.detach().cpu()))
        _, y_val, val_logits = predict(model, val_loader, device)
        val_ap = float(average_precision_score(y_val, val_logits))
        history.append({
            "epoch": epoch,
            "train_loss": float(np.mean(losses)),
            "val_AUPRC": val_ap,
        })
        if val_ap > best_ap + 1e-5:
            best_ap, stale = val_ap, 0
            best_state = {
                name: value.detach().cpu().clone()
                for name, value in model.state_dict().items()
            }
        else:
            stale += 1
            if stale >= patience:
                break
    if best_state is None:
        raise RuntimeError("training did not produce a finite validation checkpoint")
    model.load_state_dict(best_state)
    return model, history, best_ap


def evaluate_logits(val_logits, y_val, test_logits, y_test):
    temperature = fusion.fit_temperature(val_logits, y_val)
    val_scores = fusion.probabilities(val_logits, temperature)
    test_scores = fusion.probabilities(test_logits, temperature)
    policy = WarningPolicy.from_validation_negatives(val_scores[np.asarray(y_val) == 0])
    metrics = fusion.evaluate(y_test, test_scores, policy)
    metrics["AUROC"] = (
        float(roc_auc_score(y_test, test_scores))
        if len(np.unique(y_test)) == 2 else None
    )
    raw_scores = 1.0 / (1.0 + np.exp(-np.clip(test_logits, -40, 40)))
    return metrics, temperature, policy, test_scores, raw_scores


def evaluate_fixed_policy(logits, labels, temperature, policy):
    scores = fusion.probabilities(logits, temperature)
    metrics = fusion.evaluate(labels, scores, policy)
    metrics["AUROC"] = (
        float(roc_auc_score(labels, scores))
        if len(np.unique(labels)) == 2 else None
    )
    raw_scores = 1.0 / (1.0 + np.exp(-np.clip(logits, -40, 40)))
    return metrics, scores, raw_scores


def atomic_csv(frame: pd.DataFrame, path: str, compression=None):
    temporary = path + ".tmp"
    frame.to_csv(temporary, index=False, compression=compression)
    os.replace(temporary, path)


def atomic_json(payload: dict, path: str):
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
    os.replace(temporary, path)


def save_ragged(rows: list[np.ndarray], path: str, metadata: dict, counts: np.ndarray):
    offsets = np.zeros(len(rows) + 1, dtype=np.int64)
    offsets[1:] = np.cumsum([len(row) for row in rows])
    tokens = np.concatenate(rows).astype(np.uint16, copy=False)
    temporary = path + ".tmp.npz"
    np.savez_compressed(
        temporary,
        tokens=tokens,
        offsets=offsets,
        counts=np.asarray(counts, dtype=np.int64),
        meta=np.str_(json.dumps(metadata, sort_keys=True)),
    )
    os.replace(temporary, path)


def load_ragged(path: str, expected_sids: list[str]):
    data = np.load(path, allow_pickle=False)
    metadata = json.loads(str(data["meta"]))
    if metadata["sids"] != expected_sids:
        raise RuntimeError(f"F200 cache recipient mismatch: {path}")
    return (
        RaggedTokenStore(data["tokens"], data["offsets"]),
        data["counts"].astype(np.int64),
        metadata,
    )


def prepare_donor_frame(bench: pd.DataFrame) -> pd.DataFrame:
    frame = bench.copy()
    frame["class"] = frame["dataset_subset"].astype(str)
    frame["bytecode"] = frame["runtime_bytecode"].astype(str)
    frame["bc"] = frame["runtime_bytecode"].astype(str)
    frame["sid"] = frame["sample_id"].astype(str)
    frame["y"] = frame["label"].fillna(0).astype(int)
    frame["outer_fold_primary"] = frame["fold_id"]
    return frame


def get_f200_store(output_dir, donor_frame, primary, test_idx, fold, pools):
    data_dir = os.path.join(output_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    cache_path = os.path.join(data_dir, f"f200_fold{fold}.npz")
    ledger_path = os.path.join(data_dir, f"f200_donor_ledger_fold{fold}.csv.gz")
    expected_sids = primary.iloc[test_idx]["sample_id"].astype(str).tolist()
    if os.path.exists(cache_path):
        return load_ragged(cache_path, expected_sids)

    pools.assert_disjoint(fold)
    rows, counts = [], []
    ledger_start = len(pools.ledger_rows)
    domain = f"long_context_ablation_v3:fold{fold}:test:F200"
    for position, index in enumerate(test_idx):
        row = primary.iloc[int(index)].to_dict()
        variant = make_variant_isolated_safe(
            pools, row, fold, "test", "F200", domain)
        chunks, _ = opcode_chunks(variant, CHUNK_SIZE, max_chunks=None)
        tokens = chunks.reshape(-1)
        tokens = tokens[tokens != PAD_ID].astype(np.uint16, copy=False)
        if not len(tokens):
            tokens = np.asarray([1], dtype=np.uint16)
        rows.append(tokens)
        counts.append(len(tokens))
        if (position + 1) % 100 == 0:
            print(
                f"[long-context] generated F200 fold={fold} "
                f"{position + 1}/{len(test_idx)}",
                flush=True,
            )
    metadata = {
        "condition": "F200",
        "fold": int(fold),
        "rng_domain": domain,
        "sids": expected_sids,
        "uncapped_during_generation": True,
        "cap_applied_per_model_before_scoring": True,
    }
    save_ragged(rows, cache_path, metadata, np.asarray(counts))
    ledger = pd.DataFrame(pools.ledger_rows[ledger_start:])
    atomic_csv(ledger, ledger_path, compression="gzip")
    return load_ragged(cache_path, expected_sids)


def model_batch_size(spec: ModelSpec, short_batch: int, long_batch: int) -> int:
    return short_batch if spec.token_budget <= 2_048 else long_batch


def limited_partition(indices, labels, per_class):
    indices = np.asarray(indices, dtype=int)
    selected = np.concatenate([
        indices[np.asarray(labels)[indices] == value][:per_class]
        for value in (0, 1)
    ])
    return np.sort(selected)


def model_size(model):
    params = int(sum(parameter.numel() for parameter in model.parameters()
                     if parameter.requires_grad))
    buffer = io.BytesIO()
    torch.save(model.state_dict(), buffer)
    return params, int(buffer.getbuffer().nbytes)


def persist(output_dir, completed, metrics_rows, prediction_rows, history_rows,
            complexity_rows):
    atomic_csv(pd.DataFrame(metrics_rows), os.path.join(output_dir, "metrics.csv"))
    atomic_csv(
        pd.DataFrame(prediction_rows),
        os.path.join(output_dir, "predictions.csv.gz"),
        compression="gzip",
    )
    atomic_csv(pd.DataFrame(history_rows), os.path.join(output_dir, "history.csv"))
    atomic_csv(pd.DataFrame(complexity_rows), os.path.join(output_dir, "complexity.csv"))
    atomic_json(
        {"completed": sorted(completed)},
        os.path.join(output_dir, "checkpoint.json"),
    )


def load_resume(output_dir):
    checkpoint = os.path.join(output_dir, "checkpoint.json")
    if not os.path.exists(checkpoint):
        return set(), [], [], [], []
    with open(checkpoint, encoding="utf-8") as handle:
        completed = set(json.load(handle)["completed"])

    def records(name):
        path = os.path.join(output_dir, name)
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            return []
        frame = pd.read_csv(path)
        if "unit_key" in frame.columns:
            frame = frame[frame["unit_key"].isin(completed)]
        return frame.to_dict("records")

    return (
        completed,
        records("metrics.csv"),
        records("predictions.csv.gz"),
        records("history.csv"),
        records("complexity.csv"),
    )


def write_summaries(output_dir, metrics_rows):
    metrics = pd.DataFrame(metrics_rows)
    if metrics.empty:
        return
    per_seed = (
        metrics.groupby(["model", "condition", "seed"], as_index=False)[list(METRIC_COLUMNS)]
        .mean()
    )
    atomic_csv(per_seed, os.path.join(output_dir, "seed_summary.csv"))
    rows = []
    for (model, condition), group in per_seed.groupby(["model", "condition"]):
        row = {
            "model": model,
            "condition": condition,
            "n_seeds": int(group["seed"].nunique()),
        }
        for metric in METRIC_COLUMNS:
            row[f"{metric}_mean"] = float(group[metric].mean())
            row[f"{metric}_sd"] = float(group[metric].std(ddof=0))
        rows.append(row)
    summary = pd.DataFrame(rows).sort_values(["condition", "AUPRC_mean"],
                                             ascending=[True, False])
    atomic_csv(summary, os.path.join(output_dir, "summary.csv"))


def write_length_and_capacity_diagnostics(output_dir, prediction_rows):
    predictions = pd.DataFrame(prediction_rows)
    if predictions.empty:
        return
    predictions["length_stratum"] = np.where(
        predictions["original_opcode_count"] <= 2_048,
        "source_le_2048",
        "source_gt_2048",
    )
    fold_rows = []
    for keys, group in predictions.groupby(
            ["model", "seed", "fold", "condition", "length_stratum"]):
        if group["y"].nunique() != 2:
            continue
        fold_rows.append({
            "model": keys[0],
            "seed": int(keys[1]),
            "fold": int(keys[2]),
            "condition": keys[3],
            "length_stratum": keys[4],
            "n": int(len(group)),
            "positives": int(group["y"].sum()),
            "AUPRC": float(average_precision_score(
                group["y"], group["calibrated_score"])),
            "AUROC": float(roc_auc_score(
                group["y"], group["calibrated_score"])),
        })
    fold_frame = pd.DataFrame(fold_rows)
    atomic_csv(
        fold_frame,
        os.path.join(output_dir, "length_stratified_fold_metrics.csv"),
    )
    if not fold_frame.empty:
        per_seed = (
            fold_frame.groupby(
                ["model", "seed", "condition", "length_stratum"], as_index=False)
            [["AUPRC", "AUROC"]]
            .mean()
        )
        rows = []
        for keys, group in per_seed.groupby(
                ["model", "condition", "length_stratum"]):
            rows.append({
                "model": keys[0],
                "condition": keys[1],
                "length_stratum": keys[2],
                "AUPRC_mean": float(group["AUPRC"].mean()),
                "AUPRC_sd": float(group["AUPRC"].std(ddof=0)),
                "AUROC_mean": float(group["AUROC"].mean()),
                "AUROC_sd": float(group["AUROC"].std(ddof=0)),
                "n_seeds": int(group["seed"].nunique()),
            })
        atomic_csv(
            pd.DataFrame(rows),
            os.path.join(output_dir, "length_stratified_summary.csv"),
        )

    unique_inputs = predictions.drop_duplicates(["model", "condition", "sid"])
    capacity_rows = []
    for (model, condition), group in unique_inputs.groupby(["model", "condition"]):
        budget = int(group["token_budget"].iloc[0])
        exceeds = group["condition_opcode_count"] > budget
        capacity_rows.append({
            "model": model,
            "condition": condition,
            "token_budget": budget,
            "n": int(len(group)),
            "inputs_exceeding_budget": int(exceeds.sum()),
            "fraction_exceeding_budget": float(exceeds.mean()),
            "max_condition_opcode_count": int(group["condition_opcode_count"].max()),
            "max_retained_token_count": int(group["retained_token_count"].max()),
            "median_original_to_condition_ratio": float(
                group["original_to_condition_ratio"].median()),
        })
    atomic_csv(
        pd.DataFrame(capacity_rows),
        os.path.join(output_dir, "capacity_audit.csv"),
    )


def family_bootstrap(output_dir, prediction_rows, replicates=2_000):
    predictions = pd.DataFrame(prediction_rows)
    required = {
        model
        for left_right in CONTRASTS.values()
        for model in left_right
    }
    if not required.issubset(set(predictions["model"].unique())):
        return None
    rng = np.random.default_rng(7702)
    output = []
    for condition in ("M0", "F200"):
        condition_frame = predictions[predictions["condition"] == condition]
        base = (
            condition_frame[["sid", "family_id", "y"]]
            .drop_duplicates("sid")
            .sort_values("sid")
            .reset_index(drop=True)
        )
        families = sorted(base["family_id"].astype(str).unique())
        family_rows = {
            family: np.flatnonzero(base["family_id"].astype(str).to_numpy() == family)
            for family in families
        }
        score_by_seed_model = {}
        for seed in sorted(condition_frame["seed"].unique()):
            seed_frame = condition_frame[condition_frame["seed"] == seed]
            for model in required:
                model_scores = seed_frame[seed_frame["model"] == model][
                    ["sid", "calibrated_score"]
                ]
                aligned = base[["sid"]].merge(model_scores, on="sid", how="left")
                if aligned["calibrated_score"].isna().any():
                    raise RuntimeError(
                        f"missing bootstrap prediction: {condition} seed={seed} model={model}")
                score_by_seed_model[(int(seed), model)] = \
                    aligned["calibrated_score"].to_numpy()
        y = base["y"].to_numpy(dtype=int)
        for contrast, (left, right) in CONTRASTS.items():
            observed_by_seed = []
            for seed in sorted(condition_frame["seed"].unique()):
                observed_by_seed.append(
                    average_precision_score(y, score_by_seed_model[(int(seed), left)])
                    - average_precision_score(y, score_by_seed_model[(int(seed), right)])
                )
            boot = np.zeros(replicates, dtype=float)
            for rep in range(replicates):
                sampled = rng.choice(families, size=len(families), replace=True)
                indices = np.concatenate([family_rows[family] for family in sampled])
                seed_deltas = []
                for seed in sorted(condition_frame["seed"].unique()):
                    left_ap = average_precision_score(
                        y[indices], score_by_seed_model[(int(seed), left)][indices])
                    right_ap = average_precision_score(
                        y[indices], score_by_seed_model[(int(seed), right)][indices])
                    seed_deltas.append(left_ap - right_ap)
                boot[rep] = float(np.mean(seed_deltas))
            output.append({
                "contrast": contrast,
                "condition": condition,
                "left_model": left,
                "right_model": right,
                "AUPRC_delta": float(np.mean(observed_by_seed)),
                "ci95_low": float(np.percentile(boot, 2.5)),
                "ci95_high": float(np.percentile(boot, 97.5)),
                "probability_positive": float((boot > 0).mean()),
                "replicates": int(replicates),
                "cluster": "family_id",
            })
    result = pd.DataFrame(output)
    atomic_csv(result, os.path.join(output_dir, "family_bootstrap_contrasts.csv"))
    return result


def write_decision_report(output_dir, bootstrap):
    if bootstrap is None or bootstrap.empty:
        return
    lines = [
        "# Long-context contribution decision report",
        "",
        "Decisions follow the predeclared family-clustered AUPRC contrasts.",
        "",
        "| Gate | Condition | Delta AUPRC | 95% CI | Decision |",
        "|---|---|---:|---:|---|",
    ]
    for row in bootstrap.to_dict("records"):
        if row["ci95_low"] > 0:
            decision = "SUPPORTED"
        elif row["ci95_high"] < 0:
            decision = "NOT SUPPORTED"
        else:
            decision = "INCONCLUSIVE"
        lines.append(
            f"| {row['contrast']} | {row['condition']} | {row['AUPRC_delta']:+.4f} | "
            f"[{row['ci95_low']:+.4f}, {row['ci95_high']:+.4f}] | {decision} |"
        )
    lines.extend([
        "",
        "The AuthGuard reference is a transfer check and is deliberately excluded from the",
        "causal gate decisions.",
        "",
    ])
    path = os.path.join(output_dir, "CONTRIBUTION_DECISION.md")
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", choices=sorted(SPECS), default=list(SPECS))
    parser.add_argument("--seeds", nargs="+", type=int, default=list(SEEDS))
    parser.add_argument("--folds", nargs="+", type=int, default=list(FOLDS))
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--patience", type=int, default=5)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--short-batch", type=int, default=32)
    parser.add_argument("--long-batch", type=int, default=8)
    parser.add_argument("--threads", type=int, default=6)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--smoke-per-class", type=int, default=4)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--output-dir", default=RESULT_ROOT)
    parser.add_argument("--bootstrap-replicates", type=int, default=2_000)
    args = parser.parse_args()

    if any(fold not in FOLDS for fold in args.folds):
        raise ValueError(f"invalid fold selection: {args.folds}")
    torch.set_num_threads(args.threads)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    output_dir = os.path.abspath(args.output_dir)
    if args.smoke:
        output_dir = os.path.join(output_dir, "smoke")
        args.seeds = [args.seeds[0]]
        args.folds = [args.folds[0]]
        args.epochs = min(args.epochs, 2)
        args.patience = min(args.patience, 1)
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, "models"), exist_ok=True)

    if verify_frozen() != 0:
        raise RuntimeError("frozen-artifact verification failed before run")
    if not os.path.exists(PROTOCOL_PATH):
        raise FileNotFoundError(PROTOCOL_PATH)
    print(
        f"[long-context] device={device} output={output_dir} models={args.models} "
        f"seeds={args.seeds} folds={args.folds}",
        flush=True,
    )

    bench = pd.read_csv(BENCH_PATH)
    primary = (
        bench[bench["population"] == "PRIMARY_EVALUATION"]
        .copy()
        .reset_index(drop=True)
    )
    primary["bytecode"] = primary["runtime_bytecode"].astype(str)
    primary["sid"] = primary["sample_id"].astype(str)
    primary["y"] = primary["label"].astype(int)
    assert len(primary) == 2190 and int(primary["y"].sum()) == 727
    assert not primary["bytecode_repaired"].any()

    feature_data = np.load(FEATURE_PATH, allow_pickle=False)
    token_store = RaggedTokenStore(feature_data["tokens"], feature_data["offsets"])
    if len(token_store) != len(primary):
        raise RuntimeError("baseline token cache does not align with primary benchmark")
    y = primary["y"].to_numpy(dtype=int)
    folds = primary["fold_id"].to_numpy(dtype=int)
    original_counts = np.diff(feature_data["offsets"]).astype(np.int64)

    donor_frame = prepare_donor_frame(bench)
    pools = DonorPools(
        donor_frame,
        "benign_general",
        "outer_fold_primary",
        "LONG_CONTEXT_ABLATION_V3",
    )

    if args.resume:
        completed, metrics_rows, prediction_rows, history_rows, complexity_rows = \
            load_resume(output_dir)
    else:
        completed, metrics_rows, prediction_rows, history_rows, complexity_rows = \
            set(), [], [], [], []

    expected_units = {
        f"{model}:{seed}:{fold}"
        for model in args.models
        for seed in args.seeds
        for fold in args.folds
    }

    for fold in args.folds:
        val_fold = (fold + 1) % 5
        train_idx = np.flatnonzero((folds != fold) & (folds != val_fold))
        val_idx = np.flatnonzero(folds == val_fold)
        test_idx = np.flatnonzero(folds == fold)
        if args.smoke:
            train_idx = limited_partition(train_idx, y, args.smoke_per_class)
            val_idx = limited_partition(val_idx, y, args.smoke_per_class)
            test_idx = limited_partition(test_idx, y, args.smoke_per_class)
        f200_store, f200_counts, _ = get_f200_store(
            output_dir, donor_frame, primary, test_idx, fold, pools)
        f200_labels = y[test_idx]
        f200_local_idx = np.arange(len(test_idx))

        for seed in args.seeds:
            for model_name in args.models:
                unit_key = f"{model_name}:{seed}:{fold}"
                if unit_key in completed:
                    print(f"[long-context] skip completed {unit_key}", flush=True)
                    continue
                spec = SPECS[model_name]
                batch_size = model_batch_size(
                    spec, args.short_batch, args.long_batch)
                train_loader = make_loader(
                    train_idx, token_store, y, spec, batch_size, shuffle=True,
                    seed=seed + fold)
                val_loader = make_loader(
                    val_idx, token_store, y, spec, batch_size)
                test_loader = make_loader(
                    test_idx, token_store, y, spec, batch_size)
                f200_loader = make_loader(
                    f200_local_idx, f200_store, f200_labels, spec, batch_size)
                model = make_model(spec)
                params, serialized_bytes = model_size(model)
                if not any(row.get("model") == model_name for row in complexity_rows):
                    complexity_rows.append({
                        "unit_key": unit_key,
                        "model": model_name,
                        "layout": spec.layout,
                        "aggregation": spec.aggregation,
                        "token_budget": spec.token_budget,
                        "trainable_params": params,
                        "serialized_bytes_untrained": serialized_bytes,
                        "reference": spec.reference,
                    })

                started = time.time()
                model, history, best_val = train_model(
                    model,
                    train_loader,
                    val_loader,
                    y[train_idx],
                    device,
                    seed + fold,
                    args.epochs,
                    args.patience,
                    args.learning_rate,
                )
                _, y_val, val_logits = predict(model, val_loader, device)
                clean_indices, y_test, clean_logits = predict(
                    model, test_loader, device)
                clean_metrics, temperature, policy, clean_scores, clean_raw = \
                    evaluate_logits(val_logits, y_val, clean_logits, y_test)
                _, y_f200, f200_logits = predict(model, f200_loader, device)
                f200_metrics, f200_scores, f200_raw = evaluate_fixed_policy(
                    f200_logits, y_f200, temperature, policy)

                checkpoint_path = os.path.join(
                    output_dir, "models", f"{model_name}_seed{seed}_fold{fold}.pt")
                torch.save({
                    "state_dict": model.state_dict(),
                    "spec": asdict(spec),
                    "seed": seed,
                    "fold": fold,
                    "temperature": temperature,
                    "warning_policy": policy.to_dict(),
                    "best_val_AUPRC": best_val,
                    "protocol": os.path.relpath(PROTOCOL_PATH, ROOT),
                }, checkpoint_path)

                for condition, metrics in (("M0", clean_metrics), ("F200", f200_metrics)):
                    metric_row = {
                        "unit_key": unit_key,
                        "model": model_name,
                        "seed": seed,
                        "fold": fold,
                        "condition": condition,
                        "layout": spec.layout,
                        "aggregation": spec.aggregation,
                        "token_budget": spec.token_budget,
                        "reference": spec.reference,
                        "best_val_AUPRC": best_val,
                        "temperature": temperature,
                        "threshold_01": policy.threshold_01,
                        "threshold_05": policy.threshold_05,
                        "threshold_10": policy.threshold_10,
                    }
                    metric_row.update({name: metrics.get(name) for name in METRIC_COLUMNS})
                    metrics_rows.append(metric_row)

                clean_position = {int(index): pos
                                  for pos, index in enumerate(clean_indices)}
                for index in test_idx:
                    pos = clean_position[int(index)]
                    total = int(original_counts[index])
                    prediction_rows.append({
                        "unit_key": unit_key,
                        "model": model_name,
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
                        "retained_token_count": retained_token_count(
                            token_store.row(int(index)), spec),
                        "token_budget": spec.token_budget,
                        "original_to_condition_ratio": 1.0,
                    })
                for local, index in enumerate(test_idx):
                    total = int(f200_counts[local])
                    original = int(original_counts[index])
                    prediction_rows.append({
                        "unit_key": unit_key,
                        "model": model_name,
                        "seed": seed,
                        "fold": fold,
                        "condition": "F200",
                        "sid": primary.iloc[index]["sample_id"],
                        "family_id": primary.iloc[index]["family_id"],
                        "y": int(y[index]),
                        "raw_score": float(f200_raw[local]),
                        "calibrated_score": float(f200_scores[local]),
                        "original_opcode_count": original,
                        "condition_opcode_count": total,
                        "retained_token_count": retained_token_count(
                            f200_store.row(local), spec),
                        "token_budget": spec.token_budget,
                        "original_to_condition_ratio": float(original / max(total, 1)),
                    })
                for epoch_row in history:
                    history_rows.append({
                        "unit_key": unit_key,
                        "model": model_name,
                        "seed": seed,
                        "fold": fold,
                        **epoch_row,
                    })
                completed.add(unit_key)
                persist(
                    output_dir,
                    completed,
                    metrics_rows,
                    prediction_rows,
                    history_rows,
                    complexity_rows,
                )
                elapsed = time.time() - started
                print(
                    f"[long-context] complete {unit_key} "
                    f"M0_AP={clean_metrics['AUPRC']:.4f} "
                    f"F200_AP={f200_metrics['AUPRC']:.4f} "
                    f"seconds={elapsed:.1f}",
                    flush=True,
                )
                del model, train_loader, val_loader, test_loader, f200_loader
                gc.collect()

    write_summaries(output_dir, metrics_rows)
    write_length_and_capacity_diagnostics(output_dir, prediction_rows)
    if expected_units.issubset(completed) and not args.smoke:
        bootstrap = family_bootstrap(
            output_dir, prediction_rows, args.bootstrap_replicates)
        write_decision_report(output_dir, bootstrap)
        from render_paper_packet import render
        render(output_dir)
    if verify_frozen() != 0:
        raise RuntimeError("frozen-artifact verification failed after run")
    print(
        f"[long-context] run complete units={len(expected_units & completed)}/"
        f"{len(expected_units)}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
