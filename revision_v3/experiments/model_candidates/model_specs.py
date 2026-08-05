"""Exploratory model-strengthening candidate specs (not architectural ablations)."""
from __future__ import annotations

from models.hybrid import HybridConfig, HybridModel
from models.forward_fns import hybrid_forward
from features.encode import VOCAB_SIZE

_COMMON = dict(vocab_size=VOCAB_SIZE, chunk_size=256, max_chunks=64,
               embedding_dim=32, channel_dim=64, view_dim=64, fusion_dim=128, dropout=0.15)


def _spec(name: str, **kwargs):
    def build():
        return HybridModel(HybridConfig(**_COMMON, **kwargs))
    return {"name": name, "build": build, "forward": hybrid_forward, "kwargs": kwargs}


CANDIDATE_SPECS = [
    _spec("authguard_multiscale", use_multiscale=True),
    _spec("authguard_sequence_dense", use_dense=True),
    _spec("authguard_sequence_ngram", use_ngram=True),
    _spec("authguard_all_views", use_dense=True, use_ngram=True),
]
