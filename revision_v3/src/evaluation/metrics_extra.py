"""Additive metrics helpers for the provisional-labels pipeline: confusion matrix,
specificity, balanced accuracy, expected calibration error, and a single "everything the
provisional reports need" aggregator on top of the existing evaluation.metrics module.
Does not modify metrics.py.
"""
from __future__ import annotations

import numpy as np

from evaluation.metrics import auprc, auroc, brier, full_metrics, metrics_at_threshold


def confusion_matrix(y_true: np.ndarray, scores: np.ndarray,
                     threshold: float | np.ndarray) -> dict:
    """Confusion matrix for a scalar or per-item validation-derived threshold."""
    preds = (scores >= threshold).astype(int)
    tp = int(((preds == 1) & (y_true == 1)).sum())
    fp = int(((preds == 1) & (y_true == 0)).sum())
    tn = int(((preds == 0) & (y_true == 0)).sum())
    fn = int(((preds == 0) & (y_true == 1)).sum())
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn}


def specificity_from_cm(cm: dict) -> float:
    denom = cm["tn"] + cm["fp"]
    return cm["tn"] / denom if denom > 0 else 0.0


def balanced_accuracy_from_cm(cm: dict) -> float:
    recall = cm["tp"] / (cm["tp"] + cm["fn"]) if (cm["tp"] + cm["fn"]) > 0 else 0.0
    spec = specificity_from_cm(cm)
    return (recall + spec) / 2.0


def expected_calibration_error(y_true: np.ndarray, probs: np.ndarray, n_bins: int = 10) -> float:
    """Standard equal-width-bin ECE: mean |accuracy - confidence| per bin, weighted by bin
    occupancy. probs must be in [0, 1] (already-calibrated/sigmoid-ed scores)."""
    probs = np.clip(probs, 0.0, 1.0)
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    n = len(probs)
    for i in range(n_bins):
        lo, hi = bin_edges[i], bin_edges[i + 1]
        in_bin = (probs > lo) & (probs <= hi) if i > 0 else (probs >= lo) & (probs <= hi)
        if not np.any(in_bin):
            continue
        bin_conf = probs[in_bin].mean()
        bin_acc = y_true[in_bin].mean()
        ece += (in_bin.sum() / n) * abs(bin_acc - bin_conf)
    return float(ece)


def full_report(y_true: np.ndarray, scores: np.ndarray, val_scores: np.ndarray,
                 val_labels: np.ndarray, operating_threshold: float = 0.5,
                 nominal_fprs=(0.01, 0.05, 0.10)) -> dict:
    """Everything requested by Parts 6/9/10 for one continuous-score model, evaluated at a
    fixed 0.5 operating point plus the existing FPR-indexed thresholds from val negatives."""
    base = full_metrics(y_true, scores, val_scores, val_labels, nominal_fprs=nominal_fprs)
    cm = confusion_matrix(y_true, scores, operating_threshold)
    at_thr = metrics_at_threshold(y_true, scores, operating_threshold)
    base.update({
        "n_evaluated": int(len(y_true)),
        "n_positive": int((y_true == 1).sum()),
        "n_negative": int((y_true == 0).sum()),
        "operating_threshold": operating_threshold,
        "precision": at_thr["precision"],
        "recall": at_thr["recall"],
        "specificity": specificity_from_cm(cm),
        "fpr": at_thr["observed_fpr"],
        "f1": at_thr["f1"],
        "balanced_accuracy": balanced_accuracy_from_cm(cm),
        "brier": brier(y_true, scores),
        "calibration_error": expected_calibration_error(y_true, scores),
        "confusion_matrix": cm,
    })
    return base


def binary_rule_report(y_true: np.ndarray, preds: np.ndarray) -> dict:
    """For the source static rule (already a hard 0/1 prediction, not a continuous score)."""
    cm = confusion_matrix(y_true, preds.astype(float), threshold=0.5)
    precision = cm["tp"] / (cm["tp"] + cm["fp"]) if (cm["tp"] + cm["fp"]) > 0 else 0.0
    recall = cm["tp"] / (cm["tp"] + cm["fn"]) if (cm["tp"] + cm["fn"]) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return {
        "n_evaluated": int(len(y_true)), "n_positive": int((y_true == 1).sum()),
        "n_negative": int((y_true == 0).sum()),
        "precision": precision, "recall": recall,
        "specificity": specificity_from_cm(cm), "fpr": 1 - specificity_from_cm(cm),
        "f1": f1, "balanced_accuracy": balanced_accuracy_from_cm(cm),
        "confusion_matrix": cm,
    }
