"""Matched-budget robustness: every scored (model, condition) pair must respect its declared
token budget in the ARRAY sent to the model (even when the true flooded token count exceeds
it, downsampling/chunk-selection must have already reduced it to the budget)."""
import os

import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RESULTS_DIR = os.path.join(REPO_ROOT, "revision_v3", "results")


def test_transformed_length_distribution_exists_and_flags_exceedance():
    path = os.path.join(RESULTS_DIR, "transformed_length_distribution.csv")
    if not os.path.exists(path):
        import pytest
        pytest.skip("matched_robustness has not been run yet in this environment")
    df = pd.read_csv(path)
    assert set(df["model"].unique()) == {
        "flat_cnn_2048", "chunk_attention_2048", "flat_cnn_8192",
        "chunk_attention_8192", "flat_cnn_16384", "chunk_attention_16384",
    }
    # exceeds_budget must be consistent with flood200_token_count vs budget
    recomputed = df["flood200_token_count"] > df["budget"]
    assert (recomputed == df["exceeds_budget"]).all()
    # smaller budgets should show a higher exceedance rate than larger ones (monotonic)
    rates = df.groupby("budget")["exceeds_budget"].mean().sort_index()
    assert list(rates) == sorted(rates, reverse=True)


def test_flat_downsample_actually_caps_array_size():
    import sys
    sys.path.insert(0, os.path.join(REPO_ROOT, "revision_v3", "src"))
    import numpy as np
    from models.flat_cnn import downsample_to_budget
    huge = np.arange(1, 40000)
    for budget in (2048, 8192, 16384):
        out = downsample_to_budget(huge, budget)
        assert out.shape[0] == budget


def test_chunk_array_actually_caps_at_max_chunks():
    import sys
    sys.path.insert(0, os.path.join(REPO_ROOT, "revision_v3", "src"))
    import numpy as np
    from features.encode import chunk_token_ids
    huge = np.arange(1, 40000)
    for chunk_size, max_chunks in [(256, 8), (256, 32), (256, 64)]:
        out = chunk_token_ids(huge, chunk_size=chunk_size, max_chunks=max_chunks)
        assert out.shape == (max_chunks, chunk_size)
