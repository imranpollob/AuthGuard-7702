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

EXPECTED_MODEL_NAMES = {
    "sequence", "hist_ngram_xgb", "dcrg_project_balanced", *FEATURE_GROUPS
}
BASE_SCORE_COLUMNS = {
    "sequence": ("sequence_score", "sequence_threshold_5pct"),
    "hist_ngram_xgb": ("hist_ngram_xgb_score", "hist_ngram_xgb_threshold_5pct"),
    "dcrg_full": ("dcrg_score", "dcrg_threshold_5pct"),
    "dcrg_project_balanced": (
        "dcrg_project_balanced_score", "dcrg_project_balanced_threshold_5pct"
    ),
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


def _project_family_map(
    holdout_plan: dict, expected_ids: set[str]
) -> tuple[dict[str, str], set[str], set[str], set[str]]:
    excluded = {str(value) for value in holdout_plan.get("excluded_item_ids", [])}
    if len(excluded) != int(holdout_plan.get("n_excluded_items", -1)):
        raise ValueError("project-family exclusion count mismatch")
    if not excluded.issubset(expected_ids):
        raise ValueError("project-family plan excludes unknown review items")
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
    scored_ids = expected_ids - excluded
    if set(mapping) != scored_ids:
        raise ValueError(
            "project-family holds do not cover every non-excluded frozen item exactly: "
            f"missing={len(scored_ids - set(mapping))}, extra={len(set(mapping) - scored_ids)}"
        )
    if not scored_ids:
        raise ValueError("project-family audit excludes every frozen review item")
    return mapping, canonical_holds, control_holds, excluded


def validate_postcutoff_scoring_provenance(
    *,
    review_manifest_path: str,
    predictions_path: str,
    holdout_plan_path: str,
    training_manifest_path: str,
    sample_lock_path: str,
    preregistration_path: str,
    dependence_clusters_path: str,
    dependence_report_path: str,
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
    preregistration = _load_json(preregistration_path)
    if preregistration.get("status") != (
        "FINAL_EVALUATION_PREREGISTERED_BEFORE_POSTCUTOFF_HUMAN_LABELS"
    ):
        raise ValueError("post-cutoff final evaluation protocol is not preregistered")
    primary_population = preregistration.get("populations", {}).get(
        "primary_confirmatory", {}
    )
    if primary_population.get("n_items") != len(expected_ids):
        raise ValueError("preregistered primary population size mismatch")

    holdout_plan = _load_json(holdout_plan_path)
    if holdout_plan.get("status") != HOLDOUT_STATUS:
        raise ValueError("project-family holdout plan is not ready for retraining")
    if holdout_plan.get("manifest_sha256") != manifest_hash:
        raise ValueError("project-family holdout plan targets a different review manifest")
    canonical_hash = sha256_file(canonical_dataset_path)
    if holdout_plan.get("canonical_dataset_sha256") != canonical_hash:
        raise ValueError("holdout plan canonical-dataset hash mismatch")
    project_by_item, canonical_holds, control_holds, excluded_ids = _project_family_map(
        holdout_plan, expected_ids
    )
    scored_ids = expected_ids - excluded_ids

    dependence = pd.read_csv(dependence_clusters_path)
    required_dependence = {"item_id", "dependence_cluster_id"}
    if missing := required_dependence - set(dependence.columns):
        raise ValueError(f"dependence artifact is missing columns: {sorted(missing)}")
    if dependence["item_id"].duplicated().any():
        raise ValueError("dependence artifact item IDs must be unique")
    if set(dependence["item_id"].astype(str)) != expected_ids:
        raise ValueError("dependence artifact does not cover the frozen review manifest")
    dependence_by_item = dependence.set_index("item_id")["dependence_cluster_id"].astype(str)
    dependence_report = _load_json(dependence_report_path)
    if dependence_report.get("status") != "SCORE_BLIND_DEPENDENCE_CLUSTERS_COMPLETE":
        raise ValueError("dependence-cluster report is incomplete")
    if dependence_report.get("output_sha256") != sha256_file(dependence_clusters_path):
        raise ValueError("dependence-cluster report output hash mismatch")
    if dependence_report.get("project_family_audit_sha256") != holdout_plan.get("audit_sha256"):
        raise ValueError("dependence clusters were not regenerated after the final project audit")

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
        "preregistration_sha256": sha256_file(preregistration_path),
        "holdout_plan_sha256": sha256_file(holdout_plan_path),
        "dependence_clusters_sha256": sha256_file(dependence_clusters_path),
        "dependence_report_sha256": sha256_file(dependence_report_path),
        "canonical_dataset_sha256": canonical_hash,
        "predictions_sha256": predictions_hash,
        "snapshot_sha256": sample_lock.get("snapshot_sha256"),
    }
    for field, expected in expected_locks.items():
        if training.get(field) != expected:
            raise ValueError(f"training manifest {field} mismatch")
    legitimate_registry = os.path.join(
        artifact_root, "revision_v3", "external_controls", "verified_legitimate_controls.csv"
    )
    if training.get("legitimate_control_registry_sha256") != sha256_file(legitimate_registry):
        raise ValueError("training manifest legitimate-control registry hash mismatch")
    if float(training.get("legitimate_project_weight_total", -1)) != 8.0:
        raise ValueError("training manifest does not freeze per-project benign weight 8")
    manifest_control_projects = {
        str(value) for value in training.get("legitimate_control_projects_used", [])
    }
    if not manifest_control_projects or manifest_control_projects & control_holds:
        raise ValueError("training manifest includes no controls or a held-out control project")
    training_control_records = training.get("legitimate_control_training_records")
    if not isinstance(training_control_records, list) or not training_control_records:
        raise ValueError("training manifest contains no legitimate-control training records")
    if {
        str(record.get("project")) for record in training_control_records
    } != manifest_control_projects:
        raise ValueError("legitimate-control training records differ from declared projects")
    if any(
        not record.get("runtime_sha256")
        or not record.get("dcrg_feature_sha256")
        or float(record.get("sample_weight", 0)) <= 0
        for record in training_control_records
    ):
        raise ValueError("legitimate-control training records are incomplete")

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
        "seed", "sample_id", "family_id", "dependence_cluster_id",
        "project_family_id", "coverage",
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
        if observed != scored_ids or frame["sample_id"].duplicated().any():
            raise ValueError(f"prediction coverage mismatch for seed {seed}")
    for row in predictions[[
        "sample_id", "family_id", "dependence_cluster_id", "project_family_id"
    ]].to_dict("records"):
        expected_project = project_by_item[str(row["sample_id"])]
        expected_cluster = dependence_by_item.loc[str(row["sample_id"])]
        if str(row["project_family_id"]) != expected_project:
            raise ValueError(f"prediction project-family mismatch for {row['sample_id']}")
        if str(row["dependence_cluster_id"]) != expected_cluster:
            raise ValueError(f"prediction dependence-cluster mismatch for {row['sample_id']}")
        if str(row["family_id"]) != expected_cluster:
            raise ValueError(
                "family bootstrap must use the conservative dependence cluster"
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
        if model == "dcrg_project_balanced":
            if record.get("feature_names") != list(FEATURE_GROUPS["dcrg_full"]):
                raise ValueError(f"{key} project-balanced model does not use full DCRG features")
            if float(record.get("legitimate_project_weight_total", -1)) != 8.0:
                raise ValueError(f"{key} does not use the frozen per-project benign weight 8")
            projects = {str(value) for value in record.get("legitimate_control_projects", [])}
            if projects & control_holds:
                raise ValueError(f"{key} trained on a held-out legitimate control project")
            if projects != manifest_control_projects:
                raise ValueError(f"{key} legitimate-control projects differ from the manifest")
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
        "hist_ngram_xgb": "hist_ngram_xgb_threshold_5pct",
        "dcrg_project_balanced": "dcrg_project_balanced_threshold_5pct",
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
        "n_locked_items": len(expected_ids),
        "n_scored_items": len(scored_ids),
        "n_excluded_items": len(excluded_ids),
        "excluded_item_ids": sorted(excluded_ids),
        "n_project_families": len(set(project_by_item.values())),
        "n_dependence_clusters": len(set(dependence_by_item.loc[sorted(scored_ids)])),
        "n_prediction_seeds": len(seeds),
        "n_locked_checkpoints": len(checkpoint_records),
        "n_canonical_families_held_out": len(canonical_holds),
        "n_control_projects_held_out": len(control_holds),
        "manifest_sha256": manifest_hash,
        **expected_locks,
        "training_manifest_sha256": sha256_file(training_manifest_path),
        "bootstrap_unit": "score-blind signer/deployer/project dependence cluster",
        "claim_boundary": (
            "Cryptographic and set-membership checks verify declared scoring provenance. They "
            "do not independently prove that human-entered project-family research is correct."
        ),
    }
