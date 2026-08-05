"""Controlled model specs shared by the ablation driver and the matched-robustness driver."""
from __future__ import annotations

from models.chunk_model import ChunkModel, ChunkModelConfig
from models.flat_cnn import FlatCNN, FlatCNNConfig
from models.forward_fns import chunk_forward, flat_forward
from features.encode import VOCAB_SIZE

BUDGET_TO_MAX_CHUNKS = {2048: 8, 8192: 32, 16384: 64}


def flat_spec(budget: int):
    def build():
        return FlatCNN(FlatCNNConfig(vocab_size=VOCAB_SIZE, max_len=budget))
    return {"name": f"flat_cnn_{budget}", "kind": "flat", "budget": budget,
            "build": build, "forward": flat_forward}


def chunk_spec(budget: int, aggregation: str):
    max_chunks = BUDGET_TO_MAX_CHUNKS[budget]
    def build():
        return ChunkModel(ChunkModelConfig(
            vocab_size=VOCAB_SIZE, chunk_size=256, max_chunks=max_chunks,
            aggregation=aggregation,
        ))
    return {"name": f"chunk_{aggregation}_{budget}", "kind": "chunk", "budget": budget,
            "max_chunks": max_chunks, "aggregation": aggregation,
            "build": build, "forward": chunk_forward}


CONTROLLED_SPECS = [
    flat_spec(2048),
    flat_spec(8192),
    flat_spec(16384),
    chunk_spec(2048, "mean"),
    chunk_spec(2048, "attention"),
    chunk_spec(8192, "mean"),
    chunk_spec(8192, "attention"),
    chunk_spec(16384, "mean"),
    chunk_spec(16384, "max"),
    # chunk_attention_16384 is architecturally identical to authguard_reference_v3 and its
    # results are the reference-validation run — not retrained here (see CONTROLLED_ABLATION_REPORT.md).
]

REQUIRED_COMPARISONS = [
    ("chunk_attention_2048", "flat_cnn_2048"),
    ("chunk_attention_8192", "flat_cnn_8192"),
    ("chunk_attention_16384", "flat_cnn_16384"),
    ("chunk_attention_16384", "chunk_mean_16384"),
    ("chunk_attention_16384", "chunk_max_16384"),
    ("chunk_attention_2048", "chunk_attention_8192"),
    ("chunk_attention_8192", "chunk_attention_16384"),
]
