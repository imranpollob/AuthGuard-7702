"""Sample-set-specific assignment rules, applied automatically after a primary annotation is
submitted (called from app.py's POST /review/{item_id} handler).

- pilot: both primary reviewers assigned up front; disagreements receive an adjudicator.
- gold_dev: one primary reviewer assigned up front; after that review is submitted, assign a
  second reviewer if the item was pre-selected into the 20% random second-review sample, OR
  if the submitted label is INDETERMINATE / NOT_BYTECODE_SCREENABLE / confidence == 'low'.
- gold_test/postcutoff: two primary reviewers assigned up front; after BOTH submit, if their
  labels disagree, assign a third reviewer as adjudicator.
"""
from __future__ import annotations

import random

from db import log_action, now_iso

GOLD_DEV_SECOND_REVIEW_FRACTION = 0.20


def _ensure_reviewer_exists(conn, reviewer_id: str) -> None:
    conn.execute(
        "INSERT INTO reviewers (reviewer_id, display_name, role, created_at) VALUES (?, ?, 'primary', ?) "
        "ON CONFLICT(reviewer_id) DO NOTHING", (reviewer_id, reviewer_id, now_iso()),
    )


def apply_post_submit_rules(conn, item_id: str, sample_set: str, second_reviewer_pool: list[str],
                             adjudicator_pool: list[str]) -> None:
    if sample_set == "gold_dev":
        _maybe_assign_gold_dev_second_review(conn, item_id, second_reviewer_pool)
    elif sample_set in {"pilot", "gold_test", "postcutoff"}:
        _maybe_assign_gold_test_adjudicator(conn, item_id, adjudicator_pool)


def _maybe_assign_gold_dev_second_review(conn, item_id: str, pool: list[str]) -> None:
    existing = conn.execute(
        "SELECT reviewer_id FROM assignments WHERE item_id = ? AND is_adjudication = 0", (item_id,),
    ).fetchall()
    if len(existing) >= 2:
        return  # already has a second reviewer

    annotation = conn.execute(
        "SELECT label, confidence FROM annotations WHERE item_id = ? AND is_draft = 0 "
        "ORDER BY updated_at DESC LIMIT 1", (item_id,),
    ).fetchone()
    if annotation is None:
        return

    pre_selected = conn.execute(
        "SELECT detail FROM audit_log WHERE item_id = ? AND action = 'gold_dev_second_review_preselected'",
        (item_id,),
    ).fetchone()
    needs_second = (
        pre_selected is not None
        or annotation["label"] in ("INDETERMINATE", "NOT_BYTECODE_SCREENABLE")
        or annotation["confidence"] == "low"
    )
    if not needs_second:
        return

    already_assigned = {r["reviewer_id"] for r in existing}
    candidates = [r for r in pool if r not in already_assigned]
    if not candidates:
        return
    chosen = random.Random(item_id).choice(candidates)
    _ensure_reviewer_exists(conn, chosen)
    conn.execute(
        "INSERT OR IGNORE INTO assignments (item_id, reviewer_id, is_adjudication, status, assigned_at) "
        "VALUES (?, ?, 0, 'pending', ?)", (item_id, chosen, now_iso()),
    )
    log_action(conn, "system", "gold_dev_second_review_assigned", item_id, {"reviewer": chosen})


def _maybe_assign_gold_test_adjudicator(conn, item_id: str, pool: list[str]) -> None:
    primary = conn.execute(
        "SELECT reviewer_id, label FROM annotations WHERE item_id = ? AND is_adjudication = 0 AND is_draft = 0",
        (item_id,),
    ).fetchall()
    if len(primary) < 2:
        return
    labels = {r["label"] for r in primary}
    if len(labels) == 1:
        return  # unanimous, no adjudication needed

    existing_adjudicator = conn.execute(
        "SELECT 1 FROM assignments WHERE item_id = ? AND is_adjudication = 1", (item_id,),
    ).fetchone()
    if existing_adjudicator:
        return

    reviewed_by = {r["reviewer_id"] for r in primary}
    candidates = [r for r in pool if r not in reviewed_by]
    if not candidates:
        return
    chosen = random.Random(item_id + ":adjudicator").choice(candidates)
    _ensure_reviewer_exists(conn, chosen)
    conn.execute(
        "INSERT OR IGNORE INTO assignments (item_id, reviewer_id, is_adjudication, status, assigned_at) "
        "VALUES (?, ?, 1, 'pending', ?)", (item_id, chosen, now_iso()),
    )
    log_action(conn, "system", "gold_test_adjudicator_assigned", item_id, {"reviewer": chosen, "disagreement": list(labels)})
