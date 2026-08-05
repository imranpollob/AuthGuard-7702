"""Part 11: deterministic replay test for the final selected model
(authguard_sequence_dense). Repeats one full fold/seed training run twice under the
strengthened determinism settings (torch.use_deterministic_algorithms(True), strict mode,
CUBLAS_WORKSPACE_CONFIG set in training/harness.py) and requires exact or near-exact
numerical equivalence of the resulting test predictions.

This test trains a real model twice (~45-90s total on this session's GPU) -- it is
intentionally not mocked, since the entire point is to catch real non-determinism that a
mocked test would hide.
"""
import os
import sys

import numpy as np
import pytest
import torch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from data.loader import load_primary_dataset
from features.encode import VOCAB_SIZE
from models.forward_fns import hybrid_forward
from models.hybrid import HybridConfig, HybridModel
from training.dataset import build_token_cache, chunks_array_for_spec
from training.harness import DETERMINISTIC_ALGORITHMS_STRICT, fold_indices, score_indices, train_one_model


def test_strict_deterministic_algorithms_enabled():
    assert DETERMINISTIC_ALGORITHMS_STRICT, (
        "torch.use_deterministic_algorithms(True) fell back to warn_only mode -- "
        "CUBLAS_WORKSPACE_CONFIG may not be taking effect; see harness.py's import-order comment."
    )
    assert torch.are_deterministic_algorithms_enabled()


@pytest.mark.skipif(not torch.cuda.is_available(), reason="replay determinism is specifically about GPU non-determinism")
def test_same_seed_same_fold_reproduces_exactly():
    device = torch.device("cuda")
    df = load_primary_dataset()
    cache = build_token_cache(df)
    tensors = chunks_array_for_spec(df, cache, chunk_size=256, max_chunks=64)
    train_idx, val_idx, test_idx, _ = fold_indices(tensors["fold_id"], test_fold=0)

    def run_once():
        torch.manual_seed(0)
        model = HybridModel(HybridConfig(vocab_size=VOCAB_SIZE, chunk_size=256, max_chunks=64, use_dense=True))
        model = train_one_model(model, hybrid_forward, tensors, train_idx, val_idx, device, seed=7702)
        return score_indices(model, hybrid_forward, tensors, test_idx, device)

    scores_a = run_once()
    scores_b = run_once()
    max_abs_diff = float(np.max(np.abs(scores_a - scores_b)))
    assert max_abs_diff < 1e-5, f"replay diverged: max abs diff {max_abs_diff}"
