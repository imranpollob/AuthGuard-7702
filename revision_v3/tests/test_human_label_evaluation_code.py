"""Unit tests for the Part 10 evaluation code, using SYNTHETIC data only -- these tests prove
the metric functions are correct; they are not, and must never be mistaken for, a real
human-label evaluation result. No file under revision_v3/reports/ should ever cite numbers
from this test file.
"""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "experiments", "human_label_evaluation"))
from evaluate_against_human_labels import (  # noqa: E402
    binary_rule_metrics, continuous_score_metrics, expected_calibration_error, load_human_reference,
)


def test_binary_rule_metrics_perfect_predictor():
    y_true = np.array([1, 1, 0, 0])
    y_pred = np.array([1, 1, 0, 0])
    m = binary_rule_metrics(y_true, y_pred)
    assert m["precision"] == 1.0
    assert m["recall"] == 1.0
    assert m["specificity"] == 1.0
    assert m["fpr"] == 0.0
    assert m["f1"] == 1.0
    assert m["balanced_accuracy"] == 1.0


def test_binary_rule_metrics_all_wrong():
    y_true = np.array([1, 1, 0, 0])
    y_pred = np.array([0, 0, 1, 1])
    m = binary_rule_metrics(y_true, y_pred)
    assert m["recall"] == 0.0
    assert m["specificity"] == 0.0
    assert m["balanced_accuracy"] == 0.0


def test_expected_calibration_error_perfect_calibration():
    rng = np.random.default_rng(0)
    scores = rng.uniform(0, 1, 2000)
    y_true = (rng.uniform(0, 1, 2000) < scores).astype(int)  # scores ARE the true probabilities
    ece = expected_calibration_error(y_true, scores, n_bins=10)
    assert ece < 0.05  # should be well-calibrated by construction


def test_continuous_score_metrics_runs():
    rng = np.random.default_rng(0)
    y_true = rng.integers(0, 2, 200)
    scores = rng.uniform(0, 1, 200)
    m = continuous_score_metrics(y_true, scores, threshold=0.5)
    assert "auprc" in m and "auroc" in m and "brier" in m


def test_load_human_reference_raises_on_empty_release():
    import json
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump([], f)
        path = f.name
    try:
        with pytest.raises(ValueError):
            load_human_reference(path)
    finally:
        os.unlink(path)
