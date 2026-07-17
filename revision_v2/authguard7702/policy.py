"""Validation-derived warning policy for AuthGuard-7702."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def threshold_at_fpr(negative_scores, target: float) -> float:
    scores = np.sort(np.asarray(negative_scores, dtype=float))[::-1]
    if not len(scores):
        raise ValueError("no negative validation scores")
    allowed = int(np.floor(target * len(scores) + 1e-12))
    if allowed <= 0:
        return float(np.nextafter(scores[0], np.inf))
    if allowed >= len(scores):
        return float(np.nextafter(scores[-1], -np.inf))
    upper, lower = scores[allowed - 1], scores[allowed]
    return float((upper + lower) / 2.0 if upper > lower else np.nextafter(upper, np.inf))


@dataclass(frozen=True)
class WarningPolicy:
    threshold_01: float
    threshold_05: float
    threshold_10: float

    @classmethod
    def from_validation_negatives(cls, scores) -> "WarningPolicy":
        return cls(*(threshold_at_fpr(scores, target) for target in (0.01, 0.05, 0.10)))

    def __post_init__(self):
        if not (self.threshold_01 >= self.threshold_05 >= self.threshold_10):
            raise ValueError("warning thresholds must be monotone")

    def level(self, score: float) -> str:
        if score >= self.threshold_01:
            return "high"
        if score >= self.threshold_05:
            return "warning"
        if score >= self.threshold_10:
            return "caution"
        return "low_observed_risk"

    def to_dict(self) -> dict[str, float]:
        return {
            "fpr_01": self.threshold_01,
            "fpr_05": self.threshold_05,
            "fpr_10": self.threshold_10,
        }

