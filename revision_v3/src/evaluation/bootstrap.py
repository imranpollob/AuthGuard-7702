"""Family-clustered paired percentile bootstrap for Revision v3.

Statistical unit is the frozen bytecode family (matching the canonical Revision v2
protocol): families are resampled with replacement, all rows of a sampled family are kept
together so multiplicities are shared across the two models being compared (preserving
pairing). Independent implementation of the same estimator described in
revision_v2/experiments/statistical_analysis_v2/.
"""
from __future__ import annotations

import numpy as np


def paired_family_bootstrap_ci(
    family_ids: np.ndarray,
    y_true: np.ndarray,
    scores_a: np.ndarray,
    scores_b: np.ndarray,
    metric_fn,
    n_replicates: int = 10000,
    seed: int = 77032026,
    alpha: float = 0.05,
) -> dict:
    """Returns {"delta": mean(metric_a - metric_b) on full sample, "ci_low", "ci_high",
    "n_replicates"}. metric_fn(y_true, scores) -> float (e.g. AUPRC or recall@5%FPR)."""
    unique_families = np.unique(family_ids)
    family_to_indices = {f: np.where(family_ids == f)[0] for f in unique_families}
    rng = np.random.default_rng(seed)

    point_a = metric_fn(y_true, scores_a)
    point_b = metric_fn(y_true, scores_b)
    point_delta = point_a - point_b

    deltas = np.empty(n_replicates, dtype=np.float64)
    n_families = len(unique_families)
    for r in range(n_replicates):
        sampled_families = rng.choice(unique_families, size=n_families, replace=True)
        idx = np.concatenate([family_to_indices[f] for f in sampled_families])
        try:
            m_a = metric_fn(y_true[idx], scores_a[idx])
            m_b = metric_fn(y_true[idx], scores_b[idx])
        except ValueError:
            m_a, m_b = np.nan, np.nan
        deltas[r] = m_a - m_b

    valid = deltas[~np.isnan(deltas)]
    ci_low = float(np.percentile(valid, 100 * alpha / 2))
    ci_high = float(np.percentile(valid, 100 * (1 - alpha / 2)))

    return {
        "metric_a": point_a,
        "metric_b": point_b,
        "delta": point_delta,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "n_replicates": int(len(valid)),
        "excludes_zero": bool(ci_low > 0 or ci_high < 0),
    }
