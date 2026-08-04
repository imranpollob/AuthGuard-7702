from __future__ import annotations

import importlib.util
import json
import sqlite3

import pandas as pd
import pytest


def _load_module():
    path = __file__.replace(
        "tests/test_postcutoff_retraining_preconditions.py",
        "experiments/temporal_v2/run_postcutoff_retraining.py",
    )
    spec = importlib.util.spec_from_file_location("postcutoff_retraining", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


retraining = _load_module()


def _annotation_db(path, *, with_annotation=False):
    connection = sqlite3.connect(path)
    connection.executescript(
        "CREATE TABLE items (item_id TEXT PRIMARY KEY, sample_set TEXT);"
        "CREATE TABLE annotations (annotation_id INTEGER PRIMARY KEY, item_id TEXT);"
    )
    connection.executemany(
        "INSERT INTO items VALUES (?, 'postcutoff')", [("a",), ("b",)]
    )
    if with_annotation:
        connection.execute("INSERT INTO annotations VALUES (1, 'a')")
    connection.commit()
    connection.close()


def test_retraining_requires_zero_postcutoff_annotations(tmp_path):
    db = tmp_path / "annotations.db"
    _annotation_db(db)
    retraining.assert_postcutoff_labels_absent(str(db), {"a", "b"})
    connection = sqlite3.connect(db)
    connection.execute("INSERT INTO annotations VALUES (1, 'a')")
    connection.commit()
    connection.close()
    with pytest.raises(ValueError, match="security annotations already exist"):
        retraining.assert_postcutoff_labels_absent(str(db), {"a", "b"})


def test_project_holds_must_cover_manifest_and_lock_hashes(tmp_path):
    manifest = tmp_path / "review.csv"
    canonical = tmp_path / "canonical.bin"
    plan = tmp_path / "holds.json"
    pd.DataFrame({"item_id": ["a", "b"]}).to_csv(manifest, index=False)
    canonical.write_bytes(b"canonical")
    plan.write_text(json.dumps({
        "status": "READY_FOR_PROJECT_FAMILY_RETRAINING_HOLDS",
        "manifest_sha256": retraining.sha256_file(str(manifest)),
        "canonical_dataset_sha256": retraining.sha256_file(str(canonical)),
        "n_excluded_items": 0,
        "project_family_holds": {
            "P1": {
                "item_ids": ["a"],
                "canonical_family_ids_to_hold_out": ["F1"],
                "control_projects_to_hold_out": ["C1"],
            },
            "P2": {
                "item_ids": ["b"],
                "canonical_family_ids_to_hold_out": ["F2"],
                "control_projects_to_hold_out": [],
            },
        },
    }))
    mapping, canonical_holds, control_holds, _ = retraining.load_project_holds(
        str(plan), str(manifest), str(canonical)
    )
    assert mapping == {"a": "P1", "b": "P2"}
    assert canonical_holds == {"F1", "F2"}
    assert control_holds == {"C1"}

    altered = json.loads(plan.read_text())
    altered["project_family_holds"]["P2"]["item_ids"] = []
    plan.write_text(json.dumps(altered))
    with pytest.raises(ValueError, match="do not cover"):
        retraining.load_project_holds(str(plan), str(manifest), str(canonical))
