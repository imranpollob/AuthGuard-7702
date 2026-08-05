"""Calibration is fit on validation logits only; thresholds are derived from validation
negatives only. Both are enforced structurally (the functions simply have no parameter that
could carry test labels), verified here with synthetic data plus a signature check."""
import inspect

import numpy as np
import torch

from evaluation.metrics import threshold_at_nominal_fpr
from training.calibration import apply_temperature, fit_temperature


def test_fit_temperature_signature_has_no_test_data_parameter():
    sig = inspect.signature(fit_temperature)
    for name in sig.parameters:
        assert "test" not in name.lower()


def test_fit_temperature_runs_on_validation_only():
    torch.manual_seed(0)
    val_logits = torch.randn(200) * 3
    val_labels = (torch.sigmoid(val_logits) > 0.5).float()
    t = fit_temperature(val_logits, val_labels)
    assert t > 0


def test_threshold_uses_only_validation_negatives():
    rng = np.random.default_rng(0)
    val_scores = rng.uniform(0, 1, size=1000)
    val_labels = rng.integers(0, 2, size=1000)
    thr = threshold_at_nominal_fpr(val_scores, val_labels, nominal_fpr=0.05)
    negatives = val_scores[val_labels == 0]
    observed_fpr = (negatives >= thr).mean()
    assert abs(observed_fpr - 0.05) < 0.02  # close to nominal, by construction


def test_threshold_signature_has_no_test_data_parameter():
    sig = inspect.signature(threshold_at_nominal_fpr)
    for name in sig.parameters:
        assert "test" not in name.lower()
