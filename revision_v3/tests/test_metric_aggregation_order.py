"""Aggregation order must be: per-fold metric -> mean over folds within a seed -> mean and
sample std over the 3 seed-level means. Never a pooled-across-everything computation."""
import numpy as np
import pandas as pd


def aggregate(fold_seed_df: pd.DataFrame, metric_col: str) -> tuple[float, float]:
    per_seed = fold_seed_df.groupby("seed")[metric_col].mean()
    return float(per_seed.mean()), float(per_seed.std(ddof=1))


def test_aggregation_matches_fold_then_seed_not_pooled():
    # Construct fold-seed metrics where naive pooling would give a different answer than the
    # fold-then-seed-mean protocol, to prove the two are NOT the same computation.
    rows = []
    for seed in (7702, 7703, 7704):
        for fold in range(5):
            rows.append({"seed": seed, "fold": fold, "auprc": 0.9 if fold < 4 else 0.5})
    df = pd.DataFrame(rows)

    mean_val, std_val = aggregate(df, "auprc")
    # per-seed mean = (0.9*4 + 0.5)/5 = 0.82, identical across all 3 seeds here
    assert abs(mean_val - 0.82) < 1e-9
    assert std_val == 0.0  # all seed-level means identical in this construction

    naive_pool = df["auprc"].mean()  # pooled over 15 rows -- same value here by symmetry,
    assert abs(naive_pool - mean_val) < 1e-9  # but only because folds are seed-independent;
    # the real dataset has seed-varying per-fold results, where pooling and fold-then-seed
    # averaging diverge whenever fold sizes are unequal (they are: 446/446/427/447/424).


def test_aggregation_diverges_from_pooling_with_unequal_fold_sizes():
    # unequal per-fold row counts + a metric correlated with fold size => pooled mean
    # (weighted by row count) differs from the unweighted fold-mean-then-seed-mean protocol.
    fold_sizes = [446, 446, 427, 447, 424]
    fold_scores = [0.90, 0.90, 0.90, 0.90, 0.50]  # last (smallest-ish) fold is much worse
    rows = []
    for seed in (7702, 7703, 7704):
        for fold, (size, score) in enumerate(zip(fold_sizes, fold_scores)):
            rows.append({"seed": seed, "fold": fold, "auprc": score, "n": size})
    df = pd.DataFrame(rows)

    protocol_mean, _ = aggregate(df, "auprc")
    pooled_weighted_mean = (df["auprc"] * df["n"]).sum() / df["n"].sum()
    assert abs(protocol_mean - np.mean(fold_scores)) < 1e-9
    assert abs(protocol_mean - pooled_weighted_mean) > 1e-6  # genuinely different numbers
