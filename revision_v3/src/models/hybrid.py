"""Exploratory model-strengthening candidates — independent Revision v3 implementation.

These are explicitly NOT architectural ablations (see revision_v3/experiments/model_candidates/):
they exist to give the ML model a legitimate chance to beat the plain sequence-only reference
by combining views, not to isolate one architectural factor at a time.

- authguard_multiscale: cross-chunk aggregation is mean + max + attention concatenated
  (instead of picking one), then projected down before fusion.
- authguard_sequence_dense: sequence view + structural/histogram (dense, 261-d) view.
- authguard_sequence_ngram: sequence view + hashed opcode 4-gram (512-d) view.
- authguard_all_views: sequence + dense + ngram, gated fusion (same fusion mechanism used by
  the other two-view hybrids, generalized to three views).
"""
from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import nn

from .chunk_model import ChunkEncoder, ChunkModelConfig, CrossChunkAggregator


def view_mlp(input_dim: int, output_dim: int, dropout: float) -> nn.Sequential:
    return nn.Sequential(
        nn.LayerNorm(input_dim),
        nn.Linear(input_dim, 128),
        nn.GELU(),
        nn.Dropout(dropout),
        nn.Linear(128, output_dim),
        nn.GELU(),
    )


class MultiscaleAggregator(nn.Module):
    """Concatenates mean, max, and attention chunk summaries, then projects to channel_dim."""

    def __init__(self, channel_dim: int):
        super().__init__()
        self.mean_agg = CrossChunkAggregator(channel_dim, "mean")
        self.max_agg = CrossChunkAggregator(channel_dim, "max")
        self.attn_agg = CrossChunkAggregator(channel_dim, "attention")
        self.project = nn.Linear(channel_dim * 3, channel_dim)

    def forward(self, chunk_vectors: torch.Tensor, chunk_mask: torch.Tensor) -> torch.Tensor:
        combined = torch.cat([
            self.mean_agg(chunk_vectors, chunk_mask),
            self.max_agg(chunk_vectors, chunk_mask),
            self.attn_agg(chunk_vectors, chunk_mask),
        ], dim=1)
        return self.project(combined)


@dataclass(frozen=True)
class HybridConfig:
    vocab_size: int
    chunk_size: int = 256
    max_chunks: int | None = 64
    embedding_dim: int = 32
    channel_dim: int = 64
    view_dim: int = 64
    fusion_dim: int = 128
    dense_dim: int = 261
    ngram_dim: int = 512
    dropout: float = 0.15
    use_multiscale: bool = False
    use_dense: bool = False
    use_ngram: bool = False


class HybridModel(nn.Module):
    """Generalized N-view model: sequence (always active) + optional dense + optional ngram,
    combined by a learned per-sample gate over the active views (same gating idea used
    throughout the project for multi-view fusion, implemented independently here)."""

    def __init__(self, config: HybridConfig):
        super().__init__()
        self.config = config
        chunk_cfg = ChunkModelConfig(
            vocab_size=config.vocab_size, chunk_size=config.chunk_size,
            max_chunks=config.max_chunks, embedding_dim=config.embedding_dim,
            channel_dim=config.channel_dim, dropout=config.dropout,
            aggregation="attention",
        )
        self.sequence_encoder = ChunkEncoder(chunk_cfg)
        if config.use_multiscale:
            self.aggregator = MultiscaleAggregator(config.channel_dim)
        else:
            self.aggregator = CrossChunkAggregator(config.channel_dim, "attention")
        self.sequence_project = (
            nn.Identity() if config.channel_dim == config.view_dim
            else nn.Linear(config.channel_dim, config.view_dim)
        )

        self.active_views = [True, config.use_ngram, config.use_dense]  # seq, ngram, dense
        n_views = sum(self.active_views)

        self.ngram_view = view_mlp(config.ngram_dim, config.view_dim, config.dropout) if config.use_ngram else None
        self.dense_view = view_mlp(config.dense_dim, config.view_dim, config.dropout) if config.use_dense else None

        self.gate = nn.Linear(config.view_dim * n_views, n_views)
        self.fusion = nn.Sequential(
            nn.Linear(config.view_dim * (n_views + 1), config.fusion_dim),
            nn.GELU(),
            nn.Dropout(config.dropout),
            nn.LayerNorm(config.fusion_dim),
        )
        self.head = nn.Linear(config.fusion_dim, 1)

    def forward(self, chunks: torch.Tensor, chunk_mask: torch.Tensor,
                dense: torch.Tensor | None = None, ngram: torch.Tensor | None = None) -> torch.Tensor:
        chunk_vectors = self.sequence_encoder(chunks)
        sequence = self.sequence_project(self.aggregator(chunk_vectors, chunk_mask))

        views = [sequence]
        if self.config.use_ngram:
            views.append(self.ngram_view(ngram))
        if self.config.use_dense:
            views.append(self.dense_view(dense))

        concatenated = torch.cat(views, dim=1)
        gate_weights = torch.softmax(self.gate(concatenated), dim=1)
        stacked = torch.stack(views, dim=1)  # (batch, n_views, view_dim)
        weighted = (stacked * gate_weights.unsqueeze(-1)).sum(dim=1)  # (batch, view_dim)
        fused = self.fusion(torch.cat([concatenated, weighted], dim=1))
        return self.head(fused).squeeze(-1)
