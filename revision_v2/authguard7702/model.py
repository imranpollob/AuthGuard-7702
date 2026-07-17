"""Lightweight multi-view, multi-task AuthGuard-Fusion network."""
from __future__ import annotations

from dataclasses import asdict, dataclass

import torch
from torch import nn

from .features import AUXILIARY_FACTORS, VOCAB_SIZE


@dataclass(frozen=True)
class FusionConfig:
    vocab_size: int = VOCAB_SIZE
    dense_dim: int = 261
    ngram_dim: int = 512
    embedding_dim: int = 32
    view_dim: int = 64
    fusion_dim: int = 128
    auxiliary_dim: int = len(AUXILIARY_FACTORS)
    dropout: float = 0.15
    active_views: tuple[bool, bool, bool] = (True, True, True)

    def to_dict(self) -> dict:
        return asdict(self)


class SequenceView(nn.Module):
    def __init__(self, config: FusionConfig):
        super().__init__()
        self.embedding = nn.Embedding(config.vocab_size, config.embedding_dim, padding_idx=0)
        self.encoder = nn.Sequential(
            nn.Conv1d(config.embedding_dim, config.view_dim, kernel_size=5, padding=2),
            nn.GELU(),
            nn.Conv1d(config.view_dim, config.view_dim, kernel_size=3,
                      padding=2, dilation=2),
            nn.GELU(),
        )
        self.chunk_attention = nn.Linear(config.view_dim, 1)

    def forward(self, chunks: torch.Tensor, chunk_mask: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        batch, n_chunks, width = chunks.shape
        embedded = self.embedding(chunks.reshape(batch * n_chunks, width)).transpose(1, 2)
        encoded = self.encoder(embedded)
        token_mask = chunks.reshape(batch * n_chunks, width).ne(0).unsqueeze(1)
        # A finite sentinel avoids overflow in the subsequent linear attention layer. Fully
        # padded chunks are explicitly zeroed after pooling; they must never carry -inf-like
        # vectors into a matrix multiplication, even though their attention is masked later.
        encoded = encoded.masked_fill(~token_mask, -1.0e4)
        chunk_vectors = encoded.amax(dim=2).reshape(batch, n_chunks, -1)
        empty = ~chunk_mask
        chunk_vectors = chunk_vectors.masked_fill(empty.unsqueeze(-1), 0.0)
        attention_logits = self.chunk_attention(chunk_vectors).squeeze(-1)
        attention_logits = attention_logits.masked_fill(empty, -1.0e4)
        attention = torch.softmax(attention_logits, dim=1)
        sequence = (chunk_vectors * attention.unsqueeze(-1)).sum(dim=1)
        return sequence, attention


def _view_mlp(input_dim: int, output_dim: int, dropout: float) -> nn.Sequential:
    return nn.Sequential(
        nn.LayerNorm(input_dim),
        nn.Linear(input_dim, 128),
        nn.GELU(),
        nn.Dropout(dropout),
        nn.Linear(128, output_dim),
        nn.GELU(),
    )


class AuthGuardFusion(nn.Module):
    """Three-view model with a risk head and observable-factor auxiliary heads."""

    def __init__(self, config: FusionConfig | None = None):
        super().__init__()
        self.config = config or FusionConfig()
        c = self.config
        self.sequence_view = SequenceView(c)
        self.ngram_view = _view_mlp(c.ngram_dim, c.view_dim, c.dropout)
        self.dense_view = _view_mlp(c.dense_dim, c.view_dim, c.dropout)
        self.gate = nn.Linear(c.view_dim * 3, 3)
        self.fusion = nn.Sequential(
            nn.Linear(c.view_dim * 4, c.fusion_dim),
            nn.GELU(),
            nn.Dropout(c.dropout),
            nn.LayerNorm(c.fusion_dim),
        )
        self.risk_head = nn.Linear(c.fusion_dim, 1)
        self.auxiliary_head = nn.Linear(c.fusion_dim, c.auxiliary_dim)
        if not any(c.active_views):
            raise ValueError("at least one AuthGuard-Fusion view must be active")

    def forward(self, chunks: torch.Tensor, chunk_mask: torch.Tensor,
                dense: torch.Tensor, ngram: torch.Tensor) -> dict[str, torch.Tensor]:
        batch = dense.shape[0]
        zero = dense.new_zeros((batch, self.config.view_dim))
        if self.config.active_views[0]:
            sequence, chunk_attention = self.sequence_view(chunks, chunk_mask)
        else:
            sequence = zero
            chunk_attention = dense.new_zeros((batch, chunks.shape[1]))
        ngram_view = self.ngram_view(ngram) if self.config.active_views[1] else zero
        dense_view = self.dense_view(dense) if self.config.active_views[2] else zero
        raw_views = [sequence, ngram_view, dense_view]
        active = torch.tensor(self.config.active_views, device=dense.device, dtype=dense.dtype)
        masked_views = [view * active[index] for index, view in enumerate(raw_views)]
        views = torch.stack(masked_views, dim=1)
        concatenated = torch.cat(masked_views, dim=1)
        gate_logits = self.gate(concatenated).masked_fill(~active.bool().unsqueeze(0),
                                                          torch.finfo(dense.dtype).min)
        view_weights = torch.softmax(gate_logits, dim=1)
        weighted = (views * view_weights.unsqueeze(-1)).sum(dim=1)
        fused = self.fusion(torch.cat([concatenated, weighted], dim=1))
        return {
            "risk_logit": self.risk_head(fused).squeeze(-1),
            "auxiliary_logits": self.auxiliary_head(fused),
            "embedding": fused,
            "view_weights": view_weights,
            "chunk_attention": chunk_attention,
        }
