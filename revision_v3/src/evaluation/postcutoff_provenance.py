"""Fail-closed provenance validation for post-cutoff model evaluation.

The post-cutoff review set must not be scored with the historical cross-validation ensemble.
Every contributing model is retrained after removing canonical and control-project families
identified by the human project-family audit.  This module verifies the resulting artifacts
before the human-label evaluator is allowed to read labels.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any

import numpy as np
import pandas as pd

from analysis.dcrg_feature_groups import FEATURE_GROUPS

EXPECTED_MODEL_NAMES = {"sequence", *FEATURE_GROUPS}
BASE_SCORE_COLUMNS = {
    "sequence": ("sequence_score", "sequence_threshold_5pct"),
    "dcrg_full": ("dcrg_score", "dcrg_threshold_5pct"),
    "fusion": ("fusion_score", "fusion_threshold_5pct"),
}
TRAINING_STATUS = "FROZEN_POSTCUTOFF_RETRAINING_COMPLETE"
HOLDOUT_STATUS = "READY_FOR_PROJECT_FAMILY_RETRAINING_HOLDS"
SAMPLE_STATUS = "COMPLETE"
FORBIDDEN_PREDICTION_MARKERS = (
    "label",
    "ground_truth",
    "human",
    "reviewer",
    "adjudicat",
)


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: str) -> dict[str, Any]:
    with open(path) as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def _resolve_locked_artifact(path: str, artifact_root: str) -> str:
    if os.path.isabs(path):
        raise ValueError(f"artifact paths must be repository-relative: {path}")
    root = os.path.realpath(artifact_root)
    resolved = os.path.realpath(os.path.join(root, path))
    if os.path.commonpath([root, resolved]) != root:
        raise ValueError(f"checkpoint path escapes artifact root: {path}")
    if not os.path.isfile(resolved):
        raise ValueError(f"locked checkpoint does not exist: {path}")
    return resolved


def _project_family_map(holdout_plan: dict, expected_ids: set[str]) -> tuple[dict[str, str], set[str], set[str]]:
    if int(holdout_plan.get("n_excluded_items", -1)) != 0:
        raise ValueError(
            "post-cutoff conference evaluation requires zero project-provenance exclusions; "
            "revise and re-lock the review manifest instead of silently dropping items"
        )
    mapping: dict[str, str] = {}
    canonical_holds: set[str] = set()
    control_holds: set[str] = set()
    projects = holdout_plan.get("project_family_holds")
    if not isinstance(projects, dict) or not projects:
        raise ValueError("holdout plan contains no project_family_holds")
    for project_id, record in projects.items():
        if not project_id or not isinstance(record, dict):
            raise ValueError("invalid project-family hold record")
        for item_id in record.get("item_ids", []):
            item_id = str(item_id)
            if item_id in mapping:
                raise ValueError(f"item belongs to multiple project families: {item_id}")
            mapping[item_id] = str(project_id)
        canonical_holds.update(str(value) for value in record.get(
            "canonical_family_ids_to_hold_out", []
        ))
        control_holds.update(str(value) for value in record.get(
            "control_projects_to_hold_out", []
        ))
    if set(mapping) != expected_ids:
        raise ValueError(
            "project-family holds do not cover the frozen review manifest exactly: "
            f"missing={len(expected_ids - set(mapping))}, extra={len(set(mapping) - expected_ids)}"
        )
    return mapping, canonical_holds, control_holds


def validate_postcutoff_scoring_provenance(
    *,
    review_manifest_path: str,
    predictions_path: str,
    holdout_plan_path: str,
    training_manifest_path: str,
    sample_lock_path: str,
    canonical_dataset_path: str,
    artifact_root: str,
) -> tuple[pd.DataFrame, dict]:
    """Validate every pre-label scoring dependency and return locked predictions + audit."""
    manifest = pd.read_csv(review_manifest_path, usecols=["item_id"])
    if manifest["item_id"].isna().any() or manifest["item_id"].duplicated().any():
        raise ValueError("post-cutoff review manifest must contain unique nonempty item_id values")
    expected_ids = set(manifest["item_id"].astype(str))
    manifest_hash = sha256_file(review_manifest_path)

    sample_lock = _load_json(sample_lock_path)
    if sample_lock.get("sampling_status") != SAMPLE_STATUS:
        raise ValueError("post-cutoff sample lock is not COMPLETE")
    if sample_lock.get("manifest_sha256") != manifest_hash:
        raise ValueError("post-cutoff manifest hash does not match the score-blind sample lock")

    holdout_plan = _load_json(holdout_plan_path)
    if holdout_plan.get("status") != HOLDOUT_STATUS:
        raise ValueError("project-family holdout plan is not ready for retraining")
    if holdout_plan.get("manifest_sha256") != manifest_hash:
        raise ValueError("project-family holdout plan targets a different review manifest")
    canonical_hash = sha256_file(canonical_dataset_path)
    if holdout_plan.get("canonical_dataset_sha256") != canonical_hash:
        raise ValueError("holdout plan canonical-dataset hash mismatch")
    project_by_item, canonical_holds, control_holds = _project_family_map(
        holdout_plan, expected_ids
    )

    predictions_hash = sha256_file(predictions_path)
    training = _load_json(training_manifest_path)
    if training.get("status") != TRAINING_STATUS:
        raise ValueError("post-cutoff training manifest is not frozen and complete")
    if training.get("method_frozen_before_postcutoff_labels") is not True:
        raise ValueError("training manifest does not attest pre-label method freezing")
    if training.get("postcutoff_labels_accessed") is not False:
        raise ValueError("training manifest must attest that post-cutoff labels were not accessed")
    locked_predictions_path = _resolve_locked_artifact(
        str(training.get("predictions_path")), artifact_root
    )
    if os.path.realpath(locked_predictions_path) != os.path.realpath(predictions_path):
        raise ValueError("training manifest points to a different prediction artifact")
    expected_locks = {
        "sample_lock_sha256": sha256_file(sample_lock_path),
        "holdout_plan_sha256": sha256_file(holdout_plan_path),
        "canonical_dataset_sha256": canonical_hash,
        "predictions_sha256": predictions_hash,
        "snapshot_sha256": sample_lock.get("snapshot_sha256"),
    }
    for field, expected in expected_locks.items():
        if training.get(field) != expected:
            raise ValueError(f"training manifest {field} mismatch")

    predictions = pd.read_csv(predictions_path)
    forbidden = sorted(
        column for column in predictions.columns
        if any(marker in column.lower() for marker in FORBIDDEN_PREDICTION_MARKERS)
    )
    if forbidden:
        raise ValueError(
            "pre-label post-cutoff predictions contain forbidden human/label fields: "
            + ", ".join(forbidden)
        )
    required_prediction_columns = {
        "seed", "sample_id", "family_id", "project_family_id", "coverage",
        *(column for pair in BASE_SCORE_COLUMNS.values() for column in pair),
        *(f"{name}_{suffix}" for name in FEATURE_GROUPS for suffix in (
            "score", "threshold_5pct"
        )),
    }
    missing = required_prediction_columns - set(predictions.columns)
    if missing:
        raise ValueError(f"post-cutoff predictions are missing columns: {sorted(missing)}")
    numeric_columns = {
        *(column for pair in BASE_SCORE_COLUMNS.values() for column in pair),
        *(f"{name}_{suffix}" for name in FEATURE_GROUPS for suffix in (
            "score", "threshold_5pct"
        )),
    }
    for column in numeric_columns:
        values = pd.to_numeric(predictions[column], errors="coerce").to_numpy(dtype=float)
        if not np.isfinite(values).all() or ((values < 0) | (values > 1)).any():
            raise ValueError(f"post-cutoff prediction column {column} must be finite in [0,1]")
    if not np.allclose(predictions["dcrg_score"], predictions["dcrg_full_score"]):
        raise ValueError("dcrg_score is not an exact alias of dcrg_full_score")
    if not np.allclose(
        predictions["dcrg_threshold_5pct"],
        predictions["dcrg_full_threshold_5pct"],
    ):
        raise ValueError("dcrg_threshold_5pct is not an exact alias of the full DCRG threshold")
    seeds = sorted(int(value) for value in predictions["seed"].unique())
    if not seeds:
        raise ValueError("post-cutoff predictions contain no seeds")
    for seed in seeds:
        frame = predictions[predictions["seed"] == seed]
        observed = set(frame["sample_id"].astype(str))
        if observed != expected_ids or frame["sample_id"].duplicated().any():
            raise ValueError(f"prediction coverage mismatch for seed {seed}")
    for row in predictions[["sample_id", "family_id", "project_family_id"]].to_dict("records"):
        expected_project = project_by_item[str(row["sample_id"])]
        if str(row["project_family_id"]) != expected_project:
            raise ValueError(f"prediction project-family mismatch for {row['sample_id']}")
        if str(row["family_id"]) != expected_project:
            raise ValueError(
                "family bootstrap must use audited project_family_id, not exact-runtime family"
            )

    checkpoint_records = training.get("checkpoints")
    if not isinstance(checkpoint_records, list) or not checkpoint_records:
        raise ValueError("training manifest contains no checkpoint records")
    seen_model_seed: set[tuple[str, int]] = set()
    checkpoint_thresholds: dict[tuple[str, int], float] = {}
    for record in checkpoint_records:
        if not isinstance(record, dict):
            raise ValueError("invalid checkpoint record")
        model = str(record.get("model"))
        seed = int(record.get("seed"))
        key = (model, seed)
        if key in seen_model_seed:
            raise ValueError(f"duplicate checkpoint record: {key}")
        seen_model_seed.add(key)
        checkpoint_path = _resolve_locked_artifact(str(record.get("checkpoint_path")), artifact_root)
        if record.get("checkpoint_sha256") != sha256_file(checkpoint_path):
            raise ValueError(f"checkpoint hash mismatch: {record.get('checkpoint_path')}")
        training_families = {str(value) for value in record.get("training_family_ids", [])}
        excluded_canonical = {
            str(value) for value in record.get("excluded_canonical_family_ids", [])
        }
        excluded_controls = {
            str(value) for value in record.get("excluded_control_projects", [])
        }
        if training_families & canonical_holds:
            raise ValueError(f"{key} trained on a mandatory held-out canonical family")
        if not canonical_holds.issubset(excluded_canonical):
            raise ValueError(f"{key} does not attest every canonical family hold")
        if not control_holds.issubset(excluded_controls):
            raise ValueError(f"{key} does not attest every control-project hold")
        if record.get("threshold_fit_after_holds") is not True:
            raise ValueError(f"{key} threshold was not fit after applying holds")
        threshold = float(record.get("threshold_5pct"))
        if not np.isfinite(threshold) or not 0 <= threshold <= 1:
            raise ValueError(f"{key} has an invalid threshold")
        checkpoint_thresholds[key] = threshold
        if model in FEATURE_GROUPS and record.get("feature_names") != list(FEATURE_GROUPS[model]):
            raise ValueError(f"{key} feature group differs from the predeclared ablation")
    expected_model_seed = {
        (model, seed) for model in EXPECTED_MODEL_NAMES for seed in seeds
    }
    if seen_model_seed != expected_model_seed:
        raise ValueError(
            "training checkpoint coverage mismatch: "
            f"missing={sorted(expected_model_seed - seen_model_seed)}, "
            f"extra={sorted(seen_model_seed - expected_model_seed)}"
        )
    threshold_columns = {
        "sequence": "sequence_threshold_5pct",
        **{name: f"{name}_threshold_5pct" for name in FEATURE_GROUPS},
    }
    for (model, seed), expected_threshold in checkpoint_thresholds.items():
        observed = predictions.loc[
            predictions["seed"] == seed, threshold_columns[model]
        ].to_numpy(dtype=float)
        if not np.allclose(observed, expected_threshold):
            raise ValueError(f"prediction thresholds differ from checkpoint for {(model, seed)}")
    if training.get("dcrg_feature_groups") != {
        name: list(features) for name, features in FEATURE_GROUPS.items()
    }:
        raise ValueError("training manifest DCRG feature groups differ from the predeclared ablation")
    group_source = os.path.join(
        artifact_root, "revision_v3", "src", "analysis", "dcrg_feature_groups.py"
    )
    if training.get("dcrg_feature_groups_source_sha256") != sha256_file(group_source):
        raise ValueError("training manifest DCRG feature-group source hash mismatch")

    return predictions, {
        "status": "POSTCUTOFF_SCORING_PROVENANCE_VERIFIED",
        "n_items": len(expected_ids),
        "n_project_families": len(set(project_by_item.values())),
        "n_prediction_seeds": len(seeds),
        "n_locked_checkpoints": len(checkpoint_records),
        "n_canonical_families_held_out": len(canonical_holds),
        "n_control_projects_held_out": len(control_holds),
        "manifest_sha256": manifest_hash,
        **expected_locks,
        "training_manifest_sha256": sha256_file(training_manifest_path),
        "bootstrap_unit": "audited postcutoff project family",
        "claim_boundary": (
            "Cryptographic and set-membership checks verify declared scoring provenance. They "
            "do not independently prove that human-entered project-family research is correct."
        ),
    }
