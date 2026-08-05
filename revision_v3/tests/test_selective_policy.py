from __future__ import annotations

import numpy as np
import pytest

from evaluation.selective_policy import (
    DEFER,
    LOW_OBSERVED_RISK,
    WARN,
    risk_union,
    selective_decisions,
    selective_policy_metrics,
)


def test_risk_union_is_monotone_and_never_suppresses_either_view():
    sequence = np.array([0.1, 0.8, 0.2])
    context = np.array([0.7, 0.1, 0.2])
    fused = risk_union(sequence, context)
    np.testing.assert_allclose(fused, [0.73, 0.82, 0.36])
    assert np.all(fused >= sequence)
    assert np.all(fused >= context)


def test_incomplete_negative_is_deferred_not_called_low_risk():
    decisions = selective_decisions(
        [0.9, 0.1, 0.1], 0.5, ["PARTIAL", "PARTIAL", "COMPLETE"]
    )
    assert decisions.tolist() == [WARN, DEFER, LOW_OBSERVED_RISK]


def test_selective_metrics_expose_low_risk_errors_and_coverage():
    report = selective_policy_metrics(
        [1, 1, 0, 0], [WARN, LOW_OBSERVED_RISK, DEFER, LOW_OBSERVED_RISK]
    )
    assert report["warn_recall_on_positives"] == 0.5
    assert report["warn_fpr_on_negatives"] == 0.0
    assert report["defer_rate"] == 0.25
    assert report["positive_rate_within_low_observed_risk"] == 0.5
    assert report["positive_miss_fraction_assigned_low_observed_risk"] == 0.5


def test_risk_union_rejects_invalid_probabilities():
    with pytest.raises(ValueError, match=r"in \[0, 1\]"):
        risk_union([1.1], [0.2])
