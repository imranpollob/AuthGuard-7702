"""Hierarchical chunk model with configurable cross-chunk aggregation.

Independent Revision v3 implementation of the AuthGuard-style architecture: per-chunk
embedding + dilated convolutions + masked max pooling within a chunk, then one of three
interchangeable cross-chunk aggregation strategies (mean / max / learned attention) so the
"does attention help" question can be answered by swapping one module while holding
everything else (chunk size, token budget, training protocol) fixed.

`authguard_reference_v3` (the reference-validation target) is this model with
chunk_size=256, max_chunks=64, aggregation="attention" — architecturally the sequence-only
branch of the frozen Revision v2 AuthGuardFusion, re-implemented from scratch here (no
inactive n-gram/dense branches are ever instantiated, unlike the v2 shared-fusion module —
see PARAMETER_ACCOUNTING_REPORT.md).
"""
from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import nn


@dataclass(frozen=True)
class ChunkModelConfig:
    vocab_size: int
    chunk_size: int = 256
    max_chunks: int | None = 64
    embedding_dim: int = 32
    channel_dim: int = 64
    dropout: float = 0.15
    aggregation: str = "attention"  # "mean" | "max" | "attention"


class ChunkEncoder(nn.Module):
    """Per-chunk embedding -> conv(k5) -> conv(k3, dilation=2) -> masked max pool."""

    def __init__(self, config: ChunkModelConfig):
        super().__init__()
        self.embedding = nn.Embedding(config.vocab_size, config.embedding_dim, padding_idx=0)
        self.encoder = nn.Sequential(
            nn.Conv1d(config.embedding_dim, config.channel_dim, kernel_size=5, padding=2),
            nn.GELU(),
            nn.Conv1d(config.channel_dim, config.channel_dim, kernel_size=3, padding=2, dilation=2),
            nn.GELU(),
        )

    def forward(self, chunks: torch.Tensor) -> torch.Tensor:
        # chunks: (batch, n_chunks, chunk_size)
        batch, n_chunks, width = chunks.shape
        flat = chunks.reshape(batch * n_chunks, width)
        token_mask = flat.ne(0).unsqueeze(1)
        embedded = self.embedding(flat).transpose(1, 2)
        encoded = self.encoder(embedded)
        encoded = encoded.masked_fill(~token_mask, -1.0e4)
        chunk_vectors = encoded.amax(dim=2).reshape(batch, n_chunks, -1)
        return chunk_vectors


class CrossChunkAggregator(nn.Module):
    def __init__(self, channel_dim: int, mode: str):
        super().__init__()
        assert mode in ("mean", "max", "attention")
        self.mode = mode
        if mode == "attention":
            self.attention_logit = nn.Linear(channel_dim, 1)

    def forward(self, chunk_vectors: torch.Tensor, chunk_mask: torch.Tensor) -> torch.Tensor:
        empty = ~chunk_mask
        chunk_vectors = chunk_vectors.masked_fill(empty.unsqueeze(-1), 0.0)
        if self.mode == "mean":
            counts = chunk_mask.sum(dim=1, keepdim=True).clamp(min=1).to(chunk_vectors.dtype)
            return chunk_vectors.sum(dim=1) / counts
        if self.mode == "max":
            filled = chunk_vectors.masked_fill(empty.unsqueeze(-1), -1.0e4)
            return filled.amax(dim=1)
        logits = self.attention_logit(chunk_vectors).squeeze(-1)
        logits = logits.masked_fill(empty, -1.0e4)
        weights = torch.softmax(logits, dim=1)
        return (chunk_vectors * weights.unsqueeze(-1)).sum(dim=1)


class ChunkModel(nn.Module):
    def __init__(self, config: ChunkModelConfig):
        super().__init__()
        self.config = config
        self.encoder = ChunkEncoder(config)
        self.aggregator = CrossChunkAggregator(config.channel_dim, config.aggregation)
        self.fusion = nn.Sequential(
            nn.LayerNorm(config.channel_dim),
            nn.Linear(config.channel_dim, 128),
            nn.GELU(),
            nn.Dropout(config.dropout),
        )
        self.head = nn.Linear(128, 1)

    def forward(self, chunks: torch.Tensor, chunk_mask: torch.Tensor) -> torch.Tensor:
        chunk_vectors = self.encoder(chunks)
        pooled = self.aggregator(chunk_vectors, chunk_mask)
        fused = self.fusion(pooled)
        return self.head(fused).squeeze(-1), fused

    def sequence_dim(self) -> int:
        return 128
