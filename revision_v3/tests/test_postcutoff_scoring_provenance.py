from __future__ import annotations

import json

import pandas as pd
import pytest

from analysis.dcrg_feature_groups import FEATURE_GROUPS
from evaluation.postcutoff_provenance import (
    sha256_file,
    validate_postcutoff_scoring_provenance,
)


def _locked_fixture(tmp_path):
    manifest_path = tmp_path / "review.csv"
    predictions_path = tmp_path / "predictions.csv"
    holdout_path = tmp_path / "holds.json"
    training_path = tmp_path / "training.json"
    sample_lock_path = tmp_path / "sample_lock.json"
    canonical_path = tmp_path / "canonical.bin"
    canonical_path.write_bytes(b"canonical")
    pd.DataFrame({"item_id": ["a", "b"]}).to_csv(manifest_path, index=False)
    manifest_hash = sha256_file(str(manifest_path))
    sample_lock_path.write_text(json.dumps({
        "sampling_status": "COMPLETE",
        "manifest_sha256": manifest_hash,
        "snapshot_sha256": "snapshot-hash",
    }))
    holdout_path.write_text(json.dumps({
        "status": "READY_FOR_PROJECT_FAMILY_RETRAINING_HOLDS",
        "manifest_sha256": manifest_hash,
        "canonical_dataset_sha256": sha256_file(str(canonical_path)),
        "n_excluded_items": 0,
        "project_family_holds": {
            "PF1": {
                "item_ids": ["a"],
                "canonical_family_ids_to_hold_out": ["F1"],
                "control_projects_to_hold_out": ["ControlA"],
            },
            "PF2": {
                "item_ids": ["b"],
                "canonical_family_ids_to_hold_out": ["F2"],
                "control_projects_to_hold_out": [],
            },
        },
    }))
    prediction_rows = []
    for seed in (1, 2):
        for item_id, project in (("a", "PF1"), ("b", "PF2")):
            row = {
                "seed": seed,
                "sample_id": item_id,
                "family_id": project,
                "project_family_id": project,
                "coverage": "COMPLETE",
                "sequence_score": 0.5,
                "dcrg_score": 0.5,
                "fusion_score": 0.75,
                "sequence_threshold_5pct": 0.4,
                "dcrg_threshold_5pct": 0.4,
                "fusion_threshold_5pct": 0.6,
            }
            for model_name in FEATURE_GROUPS:
                row[f"{model_name}_score"] = 0.5
                row[f"{model_name}_threshold_5pct"] = 0.4
            prediction_rows.append(row)
    pd.DataFrame(prediction_rows).to_csv(predictions_path, index=False)

    checkpoints = []
    for model in ("sequence", *FEATURE_GROUPS):
        for seed in (1, 2):
            relative = f"checkpoints/{model}_{seed}.bin"
            path = tmp_path / relative
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(f"{model}:{seed}".encode())
            checkpoint = {
                "model": model,
                "seed": seed,
                "checkpoint_path": relative,
                "checkpoint_sha256": sha256_file(str(path)),
                "training_family_ids": ["F3", "F4"],
                "excluded_canonical_family_ids": ["F1", "F2"],
                "excluded_control_projects": ["ControlA"],
                "threshold_fit_after_holds": True,
                "threshold_5pct": 0.4,
            }
            if model in FEATURE_GROUPS:
                checkpoint["feature_names"] = list(FEATURE_GROUPS[model])
            checkpoints.append(checkpoint)
    group_source = tmp_path / "revision_v3/src/analysis/dcrg_feature_groups.py"
    group_source.parent.mkdir(parents=True)
    group_source.write_text("# frozen feature groups\n")
    training = {
        "status": "FROZEN_POSTCUTOFF_RETRAINING_COMPLETE",
        "method_frozen_before_postcutoff_labels": True,
        "postcutoff_labels_accessed": False,
        "predictions_path": "predictions.csv",
        "sample_lock_sha256": sha256_file(str(sample_lock_path)),
        "holdout_plan_sha256": sha256_file(str(holdout_path)),
        "canonical_dataset_sha256": sha256_file(str(canonical_path)),
        "predictions_sha256": sha256_file(str(predictions_path)),
        "snapshot_sha256": "snapshot-hash",
        "dcrg_feature_groups": {
            name: list(features) for name, features in FEATURE_GROUPS.items()
        },
        "dcrg_feature_groups_source_sha256": sha256_file(str(group_source)),
        "checkpoints": checkpoints,
    }
    training_path.write_text(json.dumps(training))
    return {
        "review_manifest_path": str(manifest_path),
        "predictions_path": str(predictions_path),
        "holdout_plan_path": str(holdout_path),
        "training_manifest_path": str(training_path),
        "sample_lock_path": str(sample_lock_path),
        "canonical_dataset_path": str(canonical_path),
        "artifact_root": str(tmp_path),
    }


def test_postcutoff_scoring_provenance_accepts_complete_locked_retraining(tmp_path):
    paths = _locked_fixture(tmp_path)
    predictions, report = validate_postcutoff_scoring_provenance(**paths)
    assert len(predictions) == 4
    assert report["status"] == "POSTCUTOFF_SCORING_PROVENANCE_VERIFIED"
    assert report["n_project_families"] == 2
    assert report["n_locked_checkpoints"] == 10


def test_postcutoff_scoring_provenance_rejects_training_family_leakage(tmp_path):
    paths = _locked_fixture(tmp_path)
    training = json.loads(open(paths["training_manifest_path"]).read())
    training["checkpoints"][0]["training_family_ids"].append("F1")
    with open(paths["training_manifest_path"], "w") as handle:
        json.dump(training, handle)
    with pytest.raises(ValueError, match="trained on a mandatory held-out"):
        validate_postcutoff_scoring_provenance(**paths)


def test_postcutoff_scoring_provenance_rejects_label_bearing_predictions(tmp_path):
    paths = _locked_fixture(tmp_path)
    predictions = pd.read_csv(paths["predictions_path"])
    predictions["human_label"] = "UNSAFE"
    predictions.to_csv(paths["predictions_path"], index=False)
    training = json.loads(open(paths["training_manifest_path"]).read())
    training["predictions_sha256"] = sha256_file(paths["predictions_path"])
    with open(paths["training_manifest_path"], "w") as handle:
        json.dump(training, handle)
    with pytest.raises(ValueError, match="forbidden human/label fields"):
        validate_postcutoff_scoring_provenance(**paths)


def test_postcutoff_scoring_provenance_rejects_exact_runtime_bootstrap_unit(tmp_path):
    paths = _locked_fixture(tmp_path)
    predictions = pd.read_csv(paths["predictions_path"])
    predictions.loc[predictions["sample_id"] == "a", "family_id"] = "T0001"
    predictions.to_csv(paths["predictions_path"], index=False)
    training = json.loads(open(paths["training_manifest_path"]).read())
    training["predictions_sha256"] = sha256_file(paths["predictions_path"])
    with open(paths["training_manifest_path"], "w") as handle:
        json.dump(training, handle)
    with pytest.raises(ValueError, match="bootstrap must use audited project_family_id"):
        validate_postcutoff_scoring_provenance(**paths)


def test_postcutoff_scoring_provenance_rejects_different_locked_prediction_path(tmp_path):
    paths = _locked_fixture(tmp_path)
    other = tmp_path / "other.csv"
    other.write_bytes(open(paths["predictions_path"], "rb").read())
    training = json.loads(open(paths["training_manifest_path"]).read())
    training["predictions_path"] = "other.csv"
    with open(paths["training_manifest_path"], "w") as handle:
        json.dump(training, handle)
    with pytest.raises(ValueError, match="different prediction artifact"):
        validate_postcutoff_scoring_provenance(**paths)


def test_postcutoff_scoring_provenance_rejects_nonfinite_scores(tmp_path):
    paths = _locked_fixture(tmp_path)
    predictions = pd.read_csv(paths["predictions_path"])
    predictions.loc[0, "fusion_score"] = float("nan")
    predictions.to_csv(paths["predictions_path"], index=False)
    training = json.loads(open(paths["training_manifest_path"]).read())
    training["predictions_sha256"] = sha256_file(paths["predictions_path"])
    with open(paths["training_manifest_path"], "w") as handle:
        json.dump(training, handle)
    with pytest.raises(ValueError, match=r"finite in \[0,1\]"):
        validate_postcutoff_scoring_provenance(**paths)


def test_postcutoff_scoring_provenance_binds_thresholds_to_checkpoints(tmp_path):
    paths = _locked_fixture(tmp_path)
    predictions = pd.read_csv(paths["predictions_path"])
    predictions.loc[predictions["seed"] == 1, "sequence_threshold_5pct"] = 0.41
    predictions.to_csv(paths["predictions_path"], index=False)
    training = json.loads(open(paths["training_manifest_path"]).read())
    training["predictions_sha256"] = sha256_file(paths["predictions_path"])
    with open(paths["training_manifest_path"], "w") as handle:
        json.dump(training, handle)
    with pytest.raises(ValueError, match="thresholds differ from checkpoint"):
        validate_postcutoff_scoring_provenance(**paths)
