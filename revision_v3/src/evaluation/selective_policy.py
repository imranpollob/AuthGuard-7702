"""Pre-specified context fusion and coverage-aware selective decisions.

The policy uses three outputs instead of equating a negative classifier prediction with proof
of safety.  A high fused risk score produces WARN.  A below-threshold item is called
LOW_OBSERVED_RISK only when static semantic coverage is COMPLETE; otherwise it is DEFERred.
"""
from __future__ import annotations

import numpy as np

WARN = "WARN"
LOW_OBSERVED_RISK = "LOW_OBSERVED_RISK"
DEFER = "DEFER"


def risk_union(sequence_scores, context_scores) -> np.ndarray:
    """Monotone noisy-OR fusion fixed before test evaluation.

    Either view can raise risk; a low score in one view cannot suppress a high score in the
    other.  This fixed rule avoids fitting a flexible meta-classifier on a small validation set.
    """
    sequence = np.asarray(sequence_scores, dtype=np.float64)
    context = np.asarray(context_scores, dtype=np.float64)
    if sequence.shape != context.shape:
        raise ValueError(f"score shape mismatch: {sequence.shape} != {context.shape}")
    if np.any((sequence < 0) | (sequence > 1) | (context < 0) | (context > 1)):
        raise ValueError("risk_union expects calibrated/probability-like scores in [0, 1]")
    return 1.0 - (1.0 - sequence) * (1.0 - context)


def selective_decisions(fused_scores, threshold: float, coverage) -> np.ndarray:
    scores = np.asarray(fused_scores, dtype=np.float64)
    coverage_values = np.asarray(coverage, dtype=object)
    if scores.shape != coverage_values.shape:
        raise ValueError(f"scores/coverage shape mismatch: {scores.shape} != {coverage_values.shape}")
    decisions = np.full(scores.shape, DEFER, dtype=object)
    decisions[scores >= threshold] = WARN
    decisions[(scores < threshold) & (coverage_values == "COMPLETE")] = LOW_OBSERVED_RISK
    return decisions


def selective_policy_metrics(labels, decisions) -> dict:
    y = np.asarray(labels, dtype=np.int64)
    d = np.asarray(decisions, dtype=object)
    if y.shape != d.shape:
        raise ValueError(f"labels/decisions shape mismatch: {y.shape} != {d.shape}")
    positive = y == 1
    negative = y == 0
    warn = d == WARN
    low = d == LOW_OBSERVED_RISK
    defer = d == DEFER

    def ratio(numerator: int, denominator: int) -> float | None:
        return float(numerator / denominator) if denominator else None

    return {
        "n": int(len(y)),
        "n_warn": int(warn.sum()),
        "n_low_observed_risk": int(low.sum()),
        "n_defer": int(defer.sum()),
        "defer_rate": ratio(int(defer.sum()), len(y)),
        "actionable_coverage": ratio(int((~defer).sum()), len(y)),
        "warn_recall_on_positives": ratio(int((warn & positive).sum()), int(positive.sum())),
        "warn_fpr_on_negatives": ratio(int((warn & negative).sum()), int(negative.sum())),
        "positive_rate_within_low_observed_risk": ratio(
            int((low & positive).sum()), int(low.sum())
        ),
        "positive_miss_fraction_assigned_low_observed_risk": ratio(
            int((low & positive).sum()), int(positive.sum())
        ),
    }
