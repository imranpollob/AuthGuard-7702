#!/usr/bin/env python3
"""Uniform scoring interface over arbitrary candidate bytecode for the v2 adaptive attack.

Every scorer exposes ``score_hexes(list[str]) -> np.ndarray`` returning calibrated
probabilities on the same scale as the validation-derived warning thresholds, so a single
threshold comparison decides evasion for any model family.

Feature extraction is deliberately per-model-minimal: AuthGuard-Seq is the sequence-only
fusion configuration, so its dense and n-gram branches are never evaluated and the expensive
`featurize` call is skipped via `encode_sequence_bytecode`.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
RV2 = os.path.abspath(os.path.join(HERE, "..", ".."))
ROOT = os.path.abspath(os.path.join(RV2, ".."))
sys.path.insert(0, RV2)
sys.path.insert(0, os.path.join(ROOT, "pipeline"))

from ag_features import featurize, build_sensitive_selector_set  # noqa: E402
from authguard7702.features import (PAD_ID, encode_sequence_bytecode,  # noqa: E402
                                    opcode_chunks)

SENS = build_sensitive_selector_set()
CHUNK_SIZE = 256
MAX_CHUNKS = 64


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -40, 40)))


def logit_from_proba(proba):
    proba = np.clip(np.asarray(proba, dtype=float), 1e-6, 1 - 1e-6)
    return np.log(proba / (1 - proba))


def tokens_of(bytecode_hex: str) -> np.ndarray:
    """Full opcode token stream, padding removed (mirrors run_sanity_v2._encode)."""
    chunks, _ = opcode_chunks(bytecode_hex, CHUNK_SIZE, None)
    tokens = chunks.reshape(-1)
    tokens = tokens[tokens != PAD_ID].astype(np.int64)
    if not len(tokens):
        tokens = np.asarray([1], dtype=np.int64)
    return tokens


class Scorer:
    """Calibrated-probability scorer. `temperature` and `policy` come from validation only."""

    name = "base"

    def __init__(self, temperature: float):
        self.temperature = float(temperature)

    def logits(self, hexes: list[str]) -> np.ndarray:
        raise NotImplementedError

    def score_hexes(self, hexes: list[str]) -> np.ndarray:
        if not hexes:
            return np.asarray([], dtype=float)
        return _sigmoid(self.logits(hexes) / self.temperature)


class AuthGuardSeqScorer(Scorer):
    """Sequence-only fusion model; dense/n-gram views are inactive and never featurized."""

    name = "authguard_seq"

    def __init__(self, model, device, temperature, batch_size=32):
        super().__init__(temperature)
        self.model = model.to(device).eval()
        self.device = device
        self.batch_size = batch_size
        self._zero_dense = np.zeros(261, dtype=np.float32)
        self._zero_ngram = np.zeros(512, dtype=np.float32)

    def _collate(self, rows):
        width = max(len(r.chunks) for r in rows)
        chunks = np.full((len(rows), width, CHUNK_SIZE), PAD_ID, dtype=np.int64)
        mask = np.zeros((len(rows), width), dtype=bool)
        for i, r in enumerate(rows):
            chunks[i, :len(r.chunks)] = r.chunks
            mask[i, :len(r.chunks)] = True
        return {
            "chunks": torch.from_numpy(chunks).long().to(self.device),
            "chunk_mask": torch.from_numpy(mask).bool().to(self.device),
            "dense": torch.from_numpy(
                np.stack([self._zero_dense] * len(rows))).float().to(self.device),
            "ngram": torch.from_numpy(
                np.stack([self._zero_ngram] * len(rows))).float().to(self.device),
        }

    def logits(self, hexes):
        out = []
        with torch.no_grad():
            for start in range(0, len(hexes), self.batch_size):
                batch = hexes[start:start + self.batch_size]
                rows = [encode_sequence_bytecode(h, CHUNK_SIZE, MAX_CHUNKS) for h in batch]
                logits = self.model(**self._collate(rows))["risk_logit"]
                out.extend(logits.detach().cpu().numpy().tolist())
        return np.asarray(out, dtype=float)


class FlatCNNScorer(Scorer):
    """Flat opcode CNN over a uniformly sampled fixed-length view."""

    name = "flat_cnn"

    def __init__(self, model, device, temperature, max_len=2048, batch_size=32):
        super().__init__(temperature)
        self.model = model.to(device).eval()
        self.device = device
        self.max_len = int(max_len)
        self.batch_size = batch_size

    def _matrix(self, hexes):
        matrix = np.zeros((len(hexes), self.max_len), dtype=np.int64)
        lengths = np.zeros(len(hexes), dtype=np.int64)
        for i, h in enumerate(hexes):
            tokens = tokens_of(h)
            if len(tokens) > self.max_len:
                chosen = np.linspace(0, len(tokens) - 1, self.max_len).round().astype(int)
                tokens = tokens[chosen]
            matrix[i, :len(tokens)] = tokens
            lengths[i] = len(tokens)
        return matrix, lengths

    def logits(self, hexes):
        out = []
        with torch.no_grad():
            for start in range(0, len(hexes), self.batch_size):
                batch = hexes[start:start + self.batch_size]
                matrix, lengths = self._matrix(batch)
                logits = self.model(torch.from_numpy(matrix).long().to(self.device),
                                    torch.from_numpy(lengths).long())
                out.extend(logits.detach().cpu().numpy().tolist())
        return np.asarray(out, dtype=float)


class ControlledCNNScorer(Scorer):
    """Parameter-matched ablation control (flat / chunk-mean / chunk-attention).

    Wraps the same `ControlledSequenceCNN` used by the mechanism ablation so that those
    variants can be attacked under the identical adaptive protocol, closing the gap between
    the ablation (fixed transformations only) and the adaptive evaluation.
    """

    def __init__(self, model, device, temperature, layout, budget, name,
                 batch_size=16):
        super().__init__(temperature)
        self.model = model.to(device).eval()
        self.device = device
        self.layout = layout
        self.budget = int(budget)
        self.name = name
        self.batch_size = batch_size

    def _represent(self, bytecode_hex):
        tokens = tokens_of(bytecode_hex)
        if self.layout == "flat":
            if len(tokens) > self.budget:
                chosen = np.linspace(0, len(tokens) - 1, self.budget).round().astype(int)
                tokens = tokens[chosen]
            return tokens.reshape(1, -1)
        count = int(np.ceil(len(tokens) / CHUNK_SIZE))
        chunks = np.full((count, CHUNK_SIZE), PAD_ID, dtype=np.int64)
        for index in range(count):
            part = tokens[index * CHUNK_SIZE:(index + 1) * CHUNK_SIZE]
            chunks[index, :len(part)] = part
        max_chunks = self.budget // CHUNK_SIZE
        if len(chunks) > max_chunks:
            chosen = np.linspace(0, len(chunks) - 1, max_chunks).round().astype(int)
            chunks = chunks[chosen]
        return chunks

    def logits(self, hexes):
        out = []
        with torch.no_grad():
            for start in range(0, len(hexes), self.batch_size):
                rows = [self._represent(h) for h in hexes[start:start + self.batch_size]]
                width = max(r.shape[1] for r in rows)
                depth = max(len(r) for r in rows)
                chunks = np.full((len(rows), depth, width), PAD_ID, dtype=np.int64)
                mask = np.zeros((len(rows), depth), dtype=bool)
                for i, r in enumerate(rows):
                    chunks[i, :len(r), :r.shape[1]] = r
                    mask[i, :len(r)] = True
                output = self.model(
                    chunks=torch.from_numpy(chunks).long().to(self.device),
                    chunk_mask=torch.from_numpy(mask).bool().to(self.device),
                    dense=None, ngram=None)
                out.extend(output["risk_logit"].detach().cpu().numpy().tolist())
        return np.asarray(out, dtype=float)


class EmulatorLogRegScorer(Scorer):
    """L2 logistic regression over the 15 hand-coded rule-emulator features (Gate 0A).

    This is the cheap interpretable control that matches AuthGuard-Seq on clean AUPRC.
    Several of its features (code_bytes, unique_opcode_count, n_hardcoded_addresses) move
    under flooding, while its dominant CFG-reachability boolean should not, so its
    behaviour under attack is not predictable from the clean comparison alone.
    """

    name = "emulator_logreg"

    def __init__(self, model, temperature):
        super().__init__(temperature)
        self.model = model

    def logits(self, hexes):
        import emulator_features
        matrix = emulator_features.featurize(list(hexes))
        return logit_from_proba(self.model.predict_proba(matrix)[:, 1])


class HistNgramXGBScorer(Scorer):
    """Opcode histogram (225) + hashed 4-gram (512) gradient boosting."""

    name = "hist_ngram_xgb"

    def __init__(self, model, temperature):
        super().__init__(temperature)
        self.model = model

    def logits(self, hexes):
        dense, ngram, _ = featurize(list(hexes), sens=SENS)
        matrix = np.hstack([dense[:, :225], ngram]).astype(np.float32)
        return logit_from_proba(self.model.predict_proba(matrix)[:, 1])
