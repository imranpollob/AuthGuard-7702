from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from revision_v3.experiments.human_label_evaluation.audit_postcutoff_review_readiness import (
    audit_review_readiness,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path: Path, *, forbidden: bool = False, annotation: bool = False):
    root = Path(__file__).resolve().parents[2]
    guide = root / "revision_v3/human_eval/REVIEWER_GUIDE.md"
    constants = root / "revision_v3/annotation_app/constants.py"
    manifest = tmp_path / "manifest.csv"
    with manifest.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["item_id"])
        writer.writeheader()
        for index in range(150):
            writer.writerow({"item_id": f"i{index:03d}"})
    prereg = tmp_path / "prereg.json"
    prereg.write_text(json.dumps({
        "status": "FINAL_EVALUATION_PREREGISTERED_BEFORE_POSTCUTOFF_HUMAN_LABELS",
        "source_locks": {
            "revision_v3/human_eval/REVIEWER_GUIDE.md": _sha(guide),
            "revision_v3/annotation_app/constants.py": _sha(constants),
        },
    }))
    db = tmp_path / "annotation.db"
    connection = sqlite3.connect(db)
    connection.executescript("""
        CREATE TABLE items(item_id TEXT PRIMARY KEY, sample_set TEXT, evidence_json TEXT);
        CREATE TABLE assignments(item_id TEXT, reviewer_id TEXT, is_adjudication INTEGER, status TEXT);
        CREATE TABLE annotations(item_id TEXT);
    """)
    for index in range(150):
        item_id = f"i{index:03d}"
        evidence = {"structural": {"n_call": 1}}
        if forbidden and index == 0:
            evidence["nested"] = {"model_score": 0.9}
        connection.execute("INSERT INTO items VALUES (?, 'postcutoff', ?)", (item_id, json.dumps(evidence)))
        for reviewer in ("R1", "R2"):
            connection.execute("INSERT INTO assignments VALUES (?, ?, 0, 'pending')", (item_id, reviewer))
    if annotation:
        connection.execute("INSERT INTO annotations VALUES ('i000')")
    connection.commit()
    connection.close()
    return db, manifest, prereg, tmp_path / "missing_roster.csv"


def test_structurally_ready_study_still_waits_for_named_roster(tmp_path):
    db, manifest, prereg, roster = _fixture(tmp_path)
    report = audit_review_readiness(
        db_path=db, manifest_path=manifest, prereg_path=prereg, roster_path=roster,
    )
    assert report["status"] == "AWAITING_NAMED_REVIEWER_ATTESTATION"
    assert report["n_manifest_items"] == 150
    assert report["n_postcutoff_annotations"] == 0
    assert report["forbidden_evidence_key_occurrences"] == 0


def test_review_readiness_rejects_recursive_score_or_label_key(tmp_path):
    db, manifest, prereg, roster = _fixture(tmp_path, forbidden=True)
    with pytest.raises(ValueError, match="forbidden score/label keys"):
        audit_review_readiness(
            db_path=db, manifest_path=manifest, prereg_path=prereg, roster_path=roster,
        )


def test_review_readiness_rejects_preexisting_postcutoff_annotation(tmp_path):
    db, manifest, prereg, roster = _fixture(tmp_path, annotation=True)
    with pytest.raises(ValueError, match="annotations already exist"):
        audit_review_readiness(
            db_path=db, manifest_path=manifest, prereg_path=prereg, roster_path=roster,
        )
