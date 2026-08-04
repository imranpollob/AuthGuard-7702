from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from annotation_app.constants import (  # noqa: E402
    INDETERMINATE_REASONS,
    NEGATIVE_LABEL,
    POSITIVE_LABEL,
    PRIMARY_LABELS,
    UNSAFE_CATEGORIES,
)


def test_reviewer_guide_uses_application_label_taxonomy():
    guide = open(os.path.join(ROOT, "human_eval", "REVIEWER_GUIDE.md")).read()
    assert "UNCERTAIN" not in guide
    for label in PRIMARY_LABELS:
        assert label in guide
    for reason in (
        "UNRESOLVED_PROXY", "EXTERNAL_DEPENDENCY", "DYNAMIC_OR_STATE_DEPENDENT"
    ):
        assert reason in INDETERMINATE_REASONS
        assert reason in guide
    for category in (
        "UNAUTHORIZED_VALUE_MOVEMENT", "PRIVILEGE_OR_OWNERSHIP_RISK"
    ):
        assert category in UNSAFE_CATEGORIES
        assert category in guide


def test_human_evaluator_uses_the_same_binary_taxonomy():
    evaluator_path = os.path.join(
        ROOT, "experiments", "human_label_evaluation", "evaluate_against_human_labels.py"
    )
    source = open(evaluator_path).read()
    assert "from constants import NEGATIVE_LABEL, POSITIVE_LABEL" in source
    assert NEGATIVE_LABEL in PRIMARY_LABELS
    assert POSITIVE_LABEL in PRIMARY_LABELS


def test_review_template_exposes_neutral_postcutoff_authority_context():
    template = open(os.path.join(ROOT, "annotation_app", "templates", "review.html")).read()
    assert "AVAILABLE_FROM_FROZEN_COLLECTOR" in template
    assert "evidence.authorization_history | tojson" in template
    assert "not a model" in template
