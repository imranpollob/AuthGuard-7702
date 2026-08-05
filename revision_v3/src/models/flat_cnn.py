"""Controlled flat-sequence CNN — one architecture, three input budgets.

Independent Revision v3 implementation. The architecture (embedding -> two 1-D convolutions
-> masked max pool -> linear head) is held fixed; only the token budget (`max_len`) that the
sequence is downsampled to changes across `flat_cnn_2048` / `flat_cnn_8192` / `flat_cnn_16384`,
so any performance difference between budgets isolates sequence-coverage effect from
architecture effect.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import torch
from torch import nn


@dataclass(frozen=True)
class FlatCNNConfig:
    vocab_size: int
    max_len: int = 2048
    embedding_dim: int = 64
    channels: int = 128
    dropout: float = 0.15


class FlatCNN(nn.Module):
    def __init__(self, config: FlatCNNConfig):
        super().__init__()
        self.config = config
        self.embedding = nn.Embedding(config.vocab_size, config.embedding_dim, padding_idx=0)
        self.encoder = nn.Sequential(
            nn.Conv1d(config.embedding_dim, config.channels, kernel_size=7, padding=3),
            nn.GELU(),
            nn.Conv1d(config.channels, config.channels, kernel_size=5, padding=2),
            nn.GELU(),
        )
        self.dropout = nn.Dropout(config.dropout)
        self.head = nn.Linear(config.channels, 1)

    def forward(self, tokens: torch.Tensor) -> torch.Tensor:
        # tokens: (batch, max_len) int64, 0 = pad
        mask = tokens.ne(0).unsqueeze(1)  # (batch, 1, max_len)
        embedded = self.embedding(tokens).transpose(1, 2)  # (batch, embed, max_len)
        encoded = self.encoder(embedded)
        encoded = encoded.masked_fill(~mask, -1.0e4)
        pooled = encoded.amax(dim=2)  # masked max pool over the sequence
        pooled = self.dropout(pooled)
        return self.head(pooled).squeeze(-1)


def downsample_to_budget(ids: np.ndarray, max_len: int) -> np.ndarray:
    """Evenly-spaced downsampling to a fixed token budget (never a prefix truncation),
    matching the chunk-selection philosophy used by the hierarchical model."""
    if len(ids) <= max_len:
        out = np.zeros(max_len, dtype=np.int64)
        out[:len(ids)] = ids
        return out
    selected = np.linspace(0, len(ids) - 1, max_len).round().astype(int)
    return ids[selected]
