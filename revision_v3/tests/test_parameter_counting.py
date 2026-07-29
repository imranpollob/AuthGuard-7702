"""Parameter counting: active parameters (nonzero-gradient) must never exceed total
instantiated parameters, and a model with no dead branches (all v3 models, by construction)
should have active == trainable."""
import torch

from models.chunk_model import ChunkModel, ChunkModelConfig
from models.hybrid import HybridConfig, HybridModel
from reporting.model_complexity import active_params, total_and_trainable_params


def test_chunk_model_active_equals_trainable():
    model = ChunkModel(ChunkModelConfig(vocab_size=227, chunk_size=256, max_chunks=8, aggregation="attention"))
    total, trainable = total_and_trainable_params(model)
    assert total == trainable

    def forward():
        chunks = torch.randint(0, 227, (4, 8, 256))
        mask = torch.ones(4, 8, dtype=torch.bool)
        logits, _ = model(chunks, mask)
        return logits

    active = active_params(model, forward)
    assert active == total  # no dead branches in this architecture


def test_hybrid_model_all_views_active_equals_trainable():
    model = HybridModel(HybridConfig(vocab_size=227, chunk_size=256, max_chunks=8, use_dense=True, use_ngram=True))
    total, trainable = total_and_trainable_params(model)
    assert total == trainable

    def forward():
        chunks = torch.randint(0, 227, (4, 8, 256))
        mask = torch.ones(4, 8, dtype=torch.bool)
        dense = torch.randn(4, 261)
        ngram = torch.randn(4, 512)
        return model(chunks, mask, dense=dense, ngram=ngram)

    active = active_params(model, forward)
    assert active == total  # v3 HybridModel only instantiates the views it uses
