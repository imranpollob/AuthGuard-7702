from __future__ import annotations

import os
import sys

import pytest
from fastapi.testclient import TestClient

APP = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "annotation_app"))
sys.path.insert(0, APP)

from annotation_validation import validate_annotation_submission  # noqa: E402
from constants import NEGATIVE_LABEL  # noqa: E402
import app as annotation_web  # noqa: E402
import db as annotation_db  # noqa: E402


def _valid(**changes):
    values = {
        "label": NEGATIVE_LABEL,
        "unsafe_category": "",
        "indeterminate_reason": "",
        "confidence": "high",
        "rationale": "No concrete unsafe path was found in the inspected evidence.",
        "evidence_consulted": "verified_source,authorization_context",
        "action": "submit",
    }
    values.update(changes)
    return values


def test_valid_final_negative_is_normalized():
    result = validate_annotation_submission(**_valid())
    assert result["label"] == NEGATIVE_LABEL
    assert result["unsafe_category"] is None
    assert result["is_draft"] is False


def test_unknown_taxonomy_values_and_actions_are_rejected():
    for changes, message in (
        ({"label": "SAFE"}, "unknown annotation label"),
        ({"confidence": "certain"}, "unknown confidence"),
        ({"unsafe_category": "MADE_UP"}, "unknown unsafe category"),
        ({"indeterminate_reason": "MADE_UP"}, "unknown indeterminate reason"),
        ({"action": "delete"}, "invalid annotation action"),
    ):
        with pytest.raises(ValueError, match=message):
            validate_annotation_submission(**_valid(**changes))


def test_final_category_and_reason_consistency_is_enforced():
    with pytest.raises(ValueError, match="requires an unsafe category"):
        validate_annotation_submission(**_valid(label="UNSAFE"))
    with pytest.raises(ValueError, match="cannot carry an indeterminate reason"):
        validate_annotation_submission(**_valid(
            label="UNSAFE", unsafe_category="OTHER_UNSAFE",
            indeterminate_reason="INSUFFICIENT_EVIDENCE",
        ))
    with pytest.raises(ValueError, match="requires an indeterminate reason"):
        validate_annotation_submission(**_valid(label="INDETERMINATE"))
    with pytest.raises(ValueError, match="cannot carry an unsafe category"):
        validate_annotation_submission(**_valid(
            label="INDETERMINATE", unsafe_category="OTHER_UNSAFE",
            indeterminate_reason="INSUFFICIENT_EVIDENCE",
        ))


def test_final_requires_rationale_and_evidence_but_draft_may_be_incomplete():
    with pytest.raises(ValueError, match="substantive rationale"):
        validate_annotation_submission(**_valid(rationale="too short"))
    with pytest.raises(ValueError, match="evidence-consulted"):
        validate_annotation_submission(**_valid(evidence_consulted=""))
    result = validate_annotation_submission(**_valid(
        action="save_draft", rationale="", evidence_consulted=""
    ))
    assert result["is_draft"] is True


def test_web_route_rejects_invalid_values_and_final_annotation_overwrite(tmp_path, monkeypatch):
    db_path = str(tmp_path / "annotation.db")
    monkeypatch.setattr(annotation_db, "DB_PATH", db_path)
    annotation_db.init_db()
    with annotation_db.db_session() as conn:
        now = annotation_db.now_iso()
        conn.execute("INSERT INTO reviewers VALUES ('R1', 'R1', 'primary', ?)", (now,))
        conn.execute(
            "INSERT INTO items VALUES ('item:a', 'gold_test', '{}', 'F1', ?)", (now,)
        )
        conn.execute(
            "INSERT INTO assignments (item_id, reviewer_id, is_adjudication, status, assigned_at) "
            "VALUES ('item:a', 'R1', 0, 'pending', ?)", (now,),
        )
    client = TestClient(annotation_web.app)
    client.cookies.set("reviewer_id", "R1")
    invalid = client.post(
        "/review/item:a", follow_redirects=False,
        data=_valid(label="SAFE"),
    )
    assert invalid.status_code == 422

    submitted = client.post(
        "/review/item:a", follow_redirects=False, data=_valid()
    )
    assert submitted.status_code == 303
    overwrite = client.post(
        "/review/item:a", follow_redirects=False,
        data=_valid(rationale="A different rationale that must never replace the final one."),
    )
    assert overwrite.status_code == 409
    connection = annotation_db.get_connection()
    row = connection.execute(
        "SELECT label, rationale, is_draft FROM annotations WHERE item_id='item:a'"
    ).fetchone()
    connection.close()
    assert row["label"] == NEGATIVE_LABEL
    assert row["rationale"] == _valid()["rationale"]
    assert row["is_draft"] == 0
