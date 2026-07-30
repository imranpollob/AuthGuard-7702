"""Phase 2 corrected bootstrap: a single seed-aware paired family-clustered bootstrap.

Phase 1's bootstrap (`revision_v3/src/evaluation/bootstrap.py`) ran an independent bootstrap
per seed and then averaged the resulting CI bounds across seeds after the fact -- that
"combine after the fact" step is not a valid confidence interval (percentile bounds are not
linear in the underlying distribution, so averaging bounds does not equal the bound of the
average). This module replaces it: for every bootstrap replicate, ONE family multiset is
drawn and reused for all three seeds, the paired metric difference is computed per seed on
that shared resample, and the three seed-level differences are averaged into a single
replicate-level number. The 95% CI is the 2.5/97.5 percentile of the resulting 10,000
replicate-level averaged differences -- a single, internally consistent interval.
"""
from __future__ import annotations

import numpy as np


def seed_aware_paired_bootstrap_ci(
    family_ids: np.ndarray,
    y_true: np.ndarray,
    scores_a_by_seed: dict[int, np.ndarray],
    scores_b_by_seed: dict[int, np.ndarray],
    metric_fn,
    n_replicates: int = 10000,
    seed: int = 77032026,
    alpha: float = 0.05,
) -> dict:
    """All arrays must share the same row order (same sample_id ordering) across seeds.

    metric_fn(y_true_subset, scores_subset) -> float.
    """
    seeds = sorted(scores_a_by_seed.keys())
    assert seeds == sorted(scores_b_by_seed.keys())
    n_seeds = len(seeds)

    unique_families = np.unique(family_ids)
    family_to_indices = {f: np.where(family_ids == f)[0] for f in unique_families}
    n_families = len(unique_families)
    rng = np.random.default_rng(seed)

    # Point estimate: mean of the per-seed full-sample (non-resampled) paired deltas.
    point_seed_deltas = [
        metric_fn(y_true, scores_a_by_seed[s]) - metric_fn(y_true, scores_b_by_seed[s])
        for s in seeds
    ]
    point_delta = float(np.mean(point_seed_deltas))

    replicate_deltas = np.empty(n_replicates, dtype=np.float64)
    for r in range(n_replicates):
        sampled_families = rng.choice(unique_families, size=n_families, replace=True)
        idx = np.concatenate([family_to_indices[f] for f in sampled_families])
        y_sub = y_true[idx]
        seed_deltas = np.empty(n_seeds, dtype=np.float64)
        for i, s in enumerate(seeds):
            m_a = metric_fn(y_sub, scores_a_by_seed[s][idx])
            m_b = metric_fn(y_sub, scores_b_by_seed[s][idx])
            seed_deltas[i] = m_a - m_b
        replicate_deltas[r] = seed_deltas.mean()

    ci_low = float(np.percentile(replicate_deltas, 100 * alpha / 2))
    ci_high = float(np.percentile(replicate_deltas, 100 * (1 - alpha / 2)))

    return {
        "point_delta": point_delta,
        "per_seed_point_deltas": {int(s): float(d) for s, d in zip(seeds, point_seed_deltas)},
        "ci_low": ci_low,
        "ci_high": ci_high,
        "excludes_zero": bool(ci_low > 0 or ci_high < 0),
        "n_replicates": n_replicates,
        "n_seeds": n_seeds,
        "method": "seed_aware_paired_family_bootstrap: one family-multiset draw per "
                  "replicate, shared across all seeds; per-seed deltas averaged WITHIN "
                  "each replicate before taking percentiles (not averaged across "
                  "independent per-seed CIs after the fact).",
    }


def align_wide_by_sample_id(pred_df, model_name: str, score_col: str, label_col: str = "label",
                             family_col: str = "family_id", sample_col: str = "sample_id"):
    """Pivots a long-format predictions dataframe (one row per (model, seed, sample_id)) into
    a common row order (sorted by sample_id) with one score array per seed. Requires each
    seed to cover the exact same set of sample_ids (true for pooled-across-fold Phase 1 data,
    since every primary row is tested exactly once per seed)."""
    sub = pred_df[pred_df["model"] == model_name]
    seeds = sorted(sub["seed"].unique())
    pivot = sub.pivot(index=sample_col, columns="seed", values=score_col).sort_index()
    meta = sub[[sample_col, family_col, label_col]].drop_duplicates(subset=sample_col).set_index(sample_col).sort_index()
    assert list(pivot.index) == list(meta.index)
    scores_by_seed = {s: pivot[s].to_numpy() for s in seeds}
    return scores_by_seed, meta[family_col].to_numpy(), meta[label_col].to_numpy()
