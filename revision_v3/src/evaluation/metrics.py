"""Metrics for Revision v3: AUPRC, AUROC, Brier, precision/recall/F1, observed FPR, and
validation-derived nominal-FPR thresholds. Independent implementation on top of sklearn.
"""
from __future__ import annotations

import numpy as np
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score


def auprc(y_true: np.ndarray, scores: np.ndarray) -> float:
    return float(average_precision_score(y_true, scores))


def auroc(y_true: np.ndarray, scores: np.ndarray) -> float:
    return float(roc_auc_score(y_true, scores))


def brier(y_true: np.ndarray, scores: np.ndarray) -> float:
    return float(brier_score_loss(y_true, scores))


def threshold_at_nominal_fpr(val_scores: np.ndarray, val_labels: np.ndarray, nominal_fpr: float) -> float:
    """Order-statistic threshold on VALIDATION NEGATIVES ONLY, never touching test labels."""
    negatives = val_scores[val_labels == 0]
    if len(negatives) == 0:
        return float(np.max(val_scores)) if len(val_scores) else 0.5
    sorted_neg = np.sort(negatives)[::-1]  # descending
    k = max(1, int(round(nominal_fpr * len(sorted_neg))))
    k = min(k, len(sorted_neg))
    return float(sorted_neg[k - 1])


def metrics_at_threshold(y_true: np.ndarray, scores: np.ndarray, threshold: float) -> dict:
    preds = (scores >= threshold).astype(int)
    tp = int(((preds == 1) & (y_true == 1)).sum())
    fp = int(((preds == 1) & (y_true == 0)).sum())
    tn = int(((preds == 0) & (y_true == 0)).sum())
    fn = int(((preds == 0) & (y_true == 1)).sum())
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "observed_fpr": fpr}


def full_metrics(y_true: np.ndarray, scores: np.ndarray, val_scores: np.ndarray,
                  val_labels: np.ndarray, nominal_fprs=(0.01, 0.05, 0.10)) -> dict:
    out = {
        "auprc": auprc(y_true, scores),
        "auroc": auroc(y_true, scores),
        "brier": brier(y_true, scores),
    }
    for nf in nominal_fprs:
        thr = threshold_at_nominal_fpr(val_scores, val_labels, nf)
        m = metrics_at_threshold(y_true, scores, thr)
        tag = f"{int(nf * 100)}pct"
        out[f"threshold_{tag}"] = thr
        out[f"recall_at_{tag}"] = m["recall"]
        out[f"observed_fpr_at_{tag}"] = m["observed_fpr"]
        out[f"precision_at_{tag}"] = m["precision"]
        out[f"f1_at_{tag}"] = m["f1"]
    return out
