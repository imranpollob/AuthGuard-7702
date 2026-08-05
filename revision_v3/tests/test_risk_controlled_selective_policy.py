from __future__ import annotations

import numpy as np

from revision_v3.experiments.selective_policy.run_risk_controlled_dcrg_policy import (
    clopper_pearson_upper,
    policy_decisions,
    select_low_risk_threshold,
)


def test_clopper_pearson_upper_is_conservative_and_monotone():
    assert 0 < clopper_pearson_upper(0, 100) < 0.05
    assert clopper_pearson_upper(1, 100) > clopper_pearson_upper(0, 100)
    assert clopper_pearson_upper(0, 20) > clopper_pearson_upper(0, 100)


def test_low_threshold_requires_complete_prefix_with_risk_bound():
    scores = np.linspace(0.01, 1.0, 100)
    labels = np.array([0] * 80 + [1] * 20)
    complete = np.ones(100, dtype=bool)
    result = select_low_risk_threshold(
        scores, labels, complete, risk_target=0.05
    )
    assert result["n_validation_low"] == 80
    assert result["n_validation_unsafe"] == 0
    assert result["risk_upper_bound"] < 0.05


def test_policy_has_separate_warn_low_and_defer_regions():
    decisions = policy_decisions(
        np.array([0.01, 0.20, 0.90, 0.01]),
        np.array(["COMPLETE", "COMPLETE", "PARTIAL", "PARTIAL"]),
        warning_threshold=0.8,
        low_threshold=0.05,
    )
    assert decisions.tolist() == [
        "LOW_OBSERVED_RISK", "DEFER", "WARN", "DEFER"
    ]
