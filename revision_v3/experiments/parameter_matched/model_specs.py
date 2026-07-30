"""Parameter-matched Flat CNN spec: embedding_dim=32, channels=60 gives 38,885 active
parameters (+0.84% vs authguard_reference_v3's 38,562) -- well within the required ±10%
band (34,706-42,418), found by grid search over (embedding_dim, channels) in
revision_v3/experiments/parameter_matched/ (see PARAMETER_MATCHED_COMPARISON_REPORT.md).
Architecture is otherwise identical to the original flat_cnn (kernel 7 then kernel 5,
masked max pool, linear head) so the ONLY controlled difference vs. the original
Phase 1 flat_cnn_* models is parameter count.
"""
from __future__ import annotations

from models.flat_cnn import FlatCNN, FlatCNNConfig
from models.forward_fns import flat_forward
from features.encode import VOCAB_SIZE

MATCHED_EMBED_DIM = 32
MATCHED_CHANNELS = 60


def flat_matched_spec(budget: int):
    def build():
        return FlatCNN(FlatCNNConfig(
            vocab_size=VOCAB_SIZE, max_len=budget,
            embedding_dim=MATCHED_EMBED_DIM, channels=MATCHED_CHANNELS,
        ))
    return {"name": f"flat_cnn_matched_{budget}", "kind": "flat", "budget": budget, "build": build, "forward": flat_forward}


PARAMETER_MATCHED_SPECS = [
    flat_matched_spec(2048),
    flat_matched_spec(8192),
    flat_matched_spec(16384),
]

COMPARISON_PAIRS = [
    ("chunk_attention_2048", "flat_cnn_matched_2048"),
    ("chunk_attention_8192", "flat_cnn_matched_8192"),
    ("chunk_attention_16384", "flat_cnn_matched_16384"),
]
