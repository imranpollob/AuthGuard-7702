"""Thin forward-pass adapters so the shared harness can drive any model family uniformly."""
from __future__ import annotations

import torch


def chunk_forward(model, batch: dict) -> torch.Tensor:
    logits, _ = model(batch["chunks"].long(), batch["chunk_mask"].bool())
    return logits


def flat_forward(model, batch: dict) -> torch.Tensor:
    return model(batch["tokens"].long())


def hybrid_forward(model, batch: dict) -> torch.Tensor:
    return model(
        batch["chunks"].long(), batch["chunk_mask"].bool(),
        dense=batch.get("dense"), ngram=batch.get("ngram"),
    )
