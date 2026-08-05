"""Fail-closed validation for human annotation submissions."""
from __future__ import annotations

from constants import (
    CONFIDENCE_LEVELS,
    INDETERMINATE_REASONS,
    NEGATIVE_LABEL,
    POSITIVE_LABEL,
    PRIMARY_LABELS,
    UNSAFE_CATEGORIES,
)

INDETERMINATE_LABELS = {"INDETERMINATE", "NOT_BYTECODE_SCREENABLE"}
ALLOWED_ACTIONS = {"save_draft", "submit"}


def validate_annotation_submission(
    *,
    label: str,
    unsafe_category: str,
    indeterminate_reason: str,
    confidence: str,
    rationale: str,
    evidence_consulted: str,
    action: str,
) -> dict[str, str | None | bool]:
    label = label.strip()
    unsafe_category = unsafe_category.strip()
    indeterminate_reason = indeterminate_reason.strip()
    confidence = confidence.strip()
    rationale = rationale.strip()
    evidence_consulted = evidence_consulted.strip()
    if action not in ALLOWED_ACTIONS:
        raise ValueError(f"invalid annotation action: {action!r}")
    if label not in PRIMARY_LABELS:
        raise ValueError(f"unknown annotation label: {label!r}")
    if confidence not in CONFIDENCE_LEVELS:
        raise ValueError(f"unknown confidence level: {confidence!r}")
    if unsafe_category and unsafe_category not in UNSAFE_CATEGORIES:
        raise ValueError(f"unknown unsafe category: {unsafe_category!r}")
    if indeterminate_reason and indeterminate_reason not in INDETERMINATE_REASONS:
        raise ValueError(f"unknown indeterminate reason: {indeterminate_reason!r}")

    is_final = action == "submit"
    if label == POSITIVE_LABEL:
        if is_final and not unsafe_category:
            raise ValueError("final UNSAFE judgment requires an unsafe category")
        if indeterminate_reason:
            raise ValueError("UNSAFE judgment cannot carry an indeterminate reason")
    elif label in INDETERMINATE_LABELS:
        if is_final and not indeterminate_reason:
            raise ValueError(f"final {label} judgment requires an indeterminate reason")
        if unsafe_category:
            raise ValueError(f"{label} judgment cannot carry an unsafe category")
    elif label == NEGATIVE_LABEL:
        if unsafe_category or indeterminate_reason:
            raise ValueError("bounded-negative judgment cannot carry unsafe/indeterminate fields")

    if is_final and len(rationale) < 20:
        raise ValueError("final judgment requires a substantive rationale of at least 20 characters")
    if is_final and not evidence_consulted:
        raise ValueError("final judgment requires the evidence-consulted field")
    return {
        "label": label,
        "unsafe_category": unsafe_category or None,
        "indeterminate_reason": indeterminate_reason or None,
        "confidence": confidence,
        "rationale": rationale,
        "evidence_consulted": evidence_consulted,
        "is_draft": not is_final,
    }
