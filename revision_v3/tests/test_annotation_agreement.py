from __future__ import annotations

import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "annotation_app"))

from agreement import cohens_kappa, summarize_agreement  # noqa: E402
from assignment_rules import apply_post_submit_rules  # noqa: E402
from db import SCHEMA  # noqa: E402


def _annotation(item_id, reviewer, label, *, adjudication=False, reason=None):
    return {
        "item_id": item_id,
        "reviewer_id": reviewer,
        "label": label,
        "indeterminate_reason": reason,
        "is_adjudication": int(adjudication),
    }


def test_sample_specific_agreement_separates_primary_labels_from_adjudication():
    items = [{"item_id": value, "sample_set": "gold_test"} for value in "abcd"]
    annotations = [
        _annotation("a", "R1", "NO_CONCRETE_UNSAFE_BEHAVIOR_FOUND"),
        _annotation("a", "R2", "NO_CONCRETE_UNSAFE_BEHAVIOR_FOUND"),
        _annotation("b", "R1", "UNSAFE"),
        _annotation("b", "R2", "UNSAFE"),
        _annotation("c", "R1", "NO_CONCRETE_UNSAFE_BEHAVIOR_FOUND"),
        _annotation("c", "R2", "UNSAFE"),
        _annotation("c", "R3", "UNSAFE", adjudication=True),
        _annotation("d", "R1", "INDETERMINATE", reason="DYNAMIC"),
        _annotation("d", "R2", "INDETERMINATE", reason="DYNAMIC"),
    ]
    report = summarize_agreement(items, annotations, "gold_test")
    assert report["status"] == "COMPLETE_DUAL_REVIEW_AND_ADJUDICATION"
    assert report["raw_agreement_rate"] == 0.75
    assert report["n_primary_disagreements"] == 1
    assert report["n_adjudicated_disagreements"] == 1
    assert report["final_label_counts_on_resolved_dual_items"] == {
        "INDETERMINATE": 1,
        "NO_CONCRETE_UNSAFE_BEHAVIOR_FOUND": 1,
        "UNSAFE": 2,
    }
    assert report["primary_confusion_matrix"]["reviewer_a"] == "R1"


def test_cohen_kappa_is_not_combined_across_changing_reviewer_pairs():
    items = [{"item_id": "a", "sample_set": "gold_test"},
             {"item_id": "b", "sample_set": "gold_test"}]
    annotations = [
        _annotation("a", "R1", "NO_CONCRETE_UNSAFE_BEHAVIOR_FOUND"),
        _annotation("a", "R2", "NO_CONCRETE_UNSAFE_BEHAVIOR_FOUND"),
        _annotation("b", "R1", "UNSAFE"),
        _annotation("b", "R3", "UNSAFE"),
    ]
    report = summarize_agreement(items, annotations, "gold_test")
    assert report["status"] == "COMPLETE_DUAL_REVIEW_AND_ADJUDICATION"
    assert report["cohens_kappa"] is None
    assert report["cohens_kappa_interpretation"].startswith("MULTIPLE_REVIEWER_PAIRS")


def test_dual_review_report_fails_closed_when_an_item_has_one_primary():
    items = [{"item_id": "a", "sample_set": "postcutoff"}]
    report = summarize_agreement(
        items, [_annotation("a", "R1", "NO_CONCRETE_UNSAFE_BEHAVIOR_FOUND")], "postcutoff"
    )
    assert report["status"] == "NOT_READY_DUAL_REVIEW_OR_ADJUDICATION_INCOMPLETE"
    assert report["primary_review_count_distribution"] == {"1": 1}


def test_kappa_is_undefined_for_degenerate_single_label_marginals():
    negative = "NO_CONCRETE_UNSAFE_BEHAVIOR_FOUND"
    assert cohens_kappa([(negative, negative), (negative, negative)]) is None


def test_pilot_disagreement_now_assigns_an_adjudicator():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    now = "2026-01-01T00:00:00Z"
    for reviewer in ("R1", "R2"):
        conn.execute(
            "INSERT INTO reviewers VALUES (?, ?, 'primary', ?)",
            (reviewer, reviewer, now),
        )
    conn.execute(
        "INSERT INTO items VALUES ('pilot:a', 'pilot', '{}', 'F1', ?)", (now,)
    )
    for reviewer, label in (
        ("R1", "NO_CONCRETE_UNSAFE_BEHAVIOR_FOUND"), ("R2", "UNSAFE")
    ):
        conn.execute(
            "INSERT INTO annotations (item_id, reviewer_id, is_adjudication, label, "
            "is_draft, created_at, updated_at) VALUES ('pilot:a', ?, 0, ?, 0, ?, ?)",
            (reviewer, label, now, now),
        )
    apply_post_submit_rules(conn, "pilot:a", "pilot", [], ["R3"])
    assigned = conn.execute(
        "SELECT reviewer_id FROM assignments WHERE item_id='pilot:a' AND is_adjudication=1"
    ).fetchone()
    assert assigned["reviewer_id"] == "R3"
    conn.close()
