from __future__ import annotations

import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "annotation_app"))

from review_gate import postcutoff_review_unlock_status  # noqa: E402


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _locked_files(tmp_path):
    predictions = tmp_path / "scores.csv"
    predictions.write_text("sample_id,score\na,0.2\n")
    training = tmp_path / "training.json"
    training.write_text(json.dumps({
        "status": "FROZEN_POSTCUTOFF_RETRAINING_COMPLETE",
        "method_frozen_before_postcutoff_labels": True,
        "postcutoff_labels_accessed": False,
        "predictions_path": "scores.csv",
        "predictions_sha256": _sha256(predictions),
    }))
    unlock = tmp_path / "unlock.json"
    unlock.write_text(json.dumps({
        "status": "POSTCUTOFF_REVIEW_UNLOCKED_AFTER_SCORING_FREEZE",
        "training_manifest": "training.json",
        "training_manifest_sha256": _sha256(training),
        "predictions_sha256": _sha256(predictions),
        "provenance_status": "POSTCUTOFF_SCORING_PROVENANCE_VERIFIED",
    }))
    return unlock, training, predictions


def test_review_gate_is_locked_without_unlock(tmp_path):
    unlocked, reason = postcutoff_review_unlock_status(
        str(tmp_path / "missing.json"), repo_root=str(tmp_path)
    )
    assert unlocked is False
    assert "not frozen" in reason


def test_review_gate_accepts_hash_locked_manifest_and_predictions(tmp_path):
    unlock, _, _ = _locked_files(tmp_path)
    unlocked, reason = postcutoff_review_unlock_status(
        str(unlock), repo_root=str(tmp_path)
    )
    assert unlocked is True
    assert "are frozen" in reason


def test_review_gate_rejects_tampered_prediction_file(tmp_path):
    unlock, _, predictions = _locked_files(tmp_path)
    predictions.write_text("sample_id,score\na,0.9\n")
    unlocked, reason = postcutoff_review_unlock_status(
        str(unlock), repo_root=str(tmp_path)
    )
    assert unlocked is False
    assert "file hash mismatch" in reason


def test_review_gate_rejects_manifest_path_escape(tmp_path):
    unlock = tmp_path / "unlock.json"
    unlock.write_text(json.dumps({
        "status": "POSTCUTOFF_REVIEW_UNLOCKED_AFTER_SCORING_FREEZE",
        "training_manifest": "../outside.json",
        "training_manifest_sha256": "unused",
        "predictions_sha256": "unused",
        "provenance_status": "POSTCUTOFF_SCORING_PROVENANCE_VERIFIED",
    }))
    unlocked, reason = postcutoff_review_unlock_status(
        str(unlock), repo_root=str(tmp_path)
    )
    assert unlocked is False
    assert "outside" in reason
