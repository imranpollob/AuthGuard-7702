"""Retrain and freeze post-cutoff scoring artifacts before security labels are collected.

This command is intentionally unavailable until the project-family audit is complete. It
removes every related canonical family, reserves canonical fold 0 for validation, trains the
fixed sequence model and all predeclared DCRG ablations for three seeds, fits calibration and
nominal 5%-FPR thresholds after applying holds, scores the locked post-cutoff sample without
reading security labels, validates all provenance locks, and only then unlocks annotation.
"""
from __future__ import annotations

import json
import os
import pickle
import sqlite3
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import torch
from sklearn.linear_model import LogisticRegression
from xgboost import XGBClassifier

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
V3 = os.path.join(REPO_ROOT, "revision_v3")
sys.path.insert(0, os.path.join(V3, "src"))

from analysis.delegation_context import DCRG_FEATURE_ORDER  # noqa: E402
from analysis.dcrg_feature_groups import FEATURE_GROUPS  # noqa: E402
from data.loader import load_primary_dataset  # noqa: E402
from evaluation.metrics import threshold_at_nominal_fpr  # noqa: E402
from evaluation.model_runtime import score_one  # noqa: E402
from evaluation.postcutoff_provenance import (  # noqa: E402
    sha256_file,
    validate_postcutoff_scoring_provenance,
)
from evaluation.selective_policy import risk_union  # noqa: E402
from features.encode import VOCAB_SIZE  # noqa: E402
from models.forward_fns import hybrid_forward  # noqa: E402
from models.hybrid import HybridConfig, HybridModel  # noqa: E402
from training.calibration import apply_temperature, fit_temperature  # noqa: E402
from training.dataset import build_token_cache, chunks_array_for_spec  # noqa: E402
from training.harness import SEEDS, score_indices, train_one_model  # noqa: E402

POST_DIR = os.path.join(V3, "results", "postcutoff_snapshot")
OUT_DIR = os.path.join(V3, "results", "postcutoff_retraining")
REVIEW_MANIFEST = os.path.join(POST_DIR, "postcutoff_review_manifest.csv")
SAMPLE_LOCK = os.path.join(POST_DIR, "postcutoff_review_lock.json")
HOLDOUT_PLAN = os.path.join(POST_DIR, "postcutoff_family_holdout_plan.json")
DCRG_FEATURES = os.path.join(POST_DIR, "postcutoff_authority_dcrg_features.csv.gz")
DCRG_REPORT = os.path.join(POST_DIR, "postcutoff_authority_dcrg_report.json")
PRIMARY_DCRG_FEATURES = os.path.join(
    V3, "results", "delegation_context", "dcrg_primary_features.csv.gz"
)
CANONICAL_DATASET = os.path.join(
    REPO_ROOT, "revision_v2", "data", "authguardbench_7702_v2.csv.gz"
)
ANNOTATION_DB = os.path.join(V3, "annotation_app", "annotation.db")
PREDICTIONS = os.path.join(OUT_DIR, "postcutoff_predictions.csv.gz")
TRAINING_MANIFEST = os.path.join(OUT_DIR, "postcutoff_training_manifest.json")
REVIEW_UNLOCK = os.path.join(POST_DIR, "postcutoff_review_unlock.json")
DCRG_FEATURE_GROUP_SOURCE = os.path.join(V3, "src", "analysis", "dcrg_feature_groups.py")
VALIDATION_FOLD = 0


def _json(path: str) -> dict:
    with open(path) as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def assert_postcutoff_labels_absent(db_path: str, expected_item_ids: set[str]) -> None:
    """Fail before training if any draft/final security judgment already exists."""
    if not os.path.exists(db_path):
        raise FileNotFoundError(
            "annotation DB is missing; seed the locked manifest before retraining"
        )
    connection = sqlite3.connect(db_path)
    rows = connection.execute(
        "SELECT i.item_id, COUNT(a.annotation_id) FROM items i "
        "LEFT JOIN annotations a ON a.item_id=i.item_id "
        "WHERE i.sample_set='postcutoff' GROUP BY i.item_id"
    ).fetchall()
    connection.close()
    observed_ids = {str(item_id) for item_id, _ in rows}
    if observed_ids != expected_item_ids:
        raise ValueError(
            "annotation DB postcutoff items do not match locked manifest: "
            f"missing={len(expected_item_ids-observed_ids)}, extra={len(observed_ids-expected_item_ids)}"
        )
    annotated = {str(item_id): int(count) for item_id, count in rows if int(count) > 0}
    if annotated:
        raise ValueError(
            "post-cutoff security annotations already exist; refusing label-aware retraining: "
            f"{len(annotated)} items"
        )


def load_project_holds(
    holdout_plan_path: str,
    manifest_path: str,
    canonical_dataset_path: str,
) -> tuple[dict[str, str], set[str], set[str], dict]:
    manifest = pd.read_csv(manifest_path, usecols=["item_id"])
    if manifest["item_id"].duplicated().any():
        raise ValueError("post-cutoff manifest item IDs are not unique")
    expected_ids = set(manifest["item_id"].astype(str))
    plan = _json(holdout_plan_path)
    if plan.get("status") != "READY_FOR_PROJECT_FAMILY_RETRAINING_HOLDS":
        raise ValueError("project-family holdout plan is incomplete")
    if plan.get("manifest_sha256") != sha256_file(manifest_path):
        raise ValueError("holdout plan review-manifest hash mismatch")
    if plan.get("canonical_dataset_sha256") != sha256_file(canonical_dataset_path):
        raise ValueError("holdout plan canonical-dataset hash mismatch")
    if int(plan.get("n_excluded_items", -1)) != 0:
        raise ValueError("re-lock the sample before training; excluded provenance items remain")

    project_by_item: dict[str, str] = {}
    canonical_holds: set[str] = set()
    control_holds: set[str] = set()
    for project_id, record in plan.get("project_family_holds", {}).items():
        for item_id in record.get("item_ids", []):
            item_id = str(item_id)
            if item_id in project_by_item:
                raise ValueError(f"duplicate project-family membership: {item_id}")
            project_by_item[item_id] = str(project_id)
        canonical_holds.update(
            str(value) for value in record.get("canonical_family_ids_to_hold_out", [])
        )
        control_holds.update(
            str(value) for value in record.get("control_projects_to_hold_out", [])
        )
    if set(project_by_item) != expected_ids:
        raise ValueError("project-family holds do not cover the review manifest exactly")
    return project_by_item, canonical_holds, control_holds, plan


def _logit(values: np.ndarray) -> np.ndarray:
    epsilon = 1e-6
    clipped = np.clip(values, epsilon, 1 - epsilon)
    return np.log(clipped / (1 - clipped)).reshape(-1, 1)


def _fit_dcrg(train_x, train_y, val_x, val_y, external_x, seed: int):
    classifier = XGBClassifier(
        n_estimators=250,
        max_depth=3,
        learning_rate=0.03,
        min_child_weight=3,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_lambda=2.0,
        objective="binary:logistic",
        eval_metric="logloss",
        scale_pos_weight=int((train_y == 0).sum()) / max(int((train_y == 1).sum()), 1),
        random_state=seed,
        n_jobs=1,
        tree_method="hist",
    )
    classifier.fit(train_x, train_y, verbose=False)
    raw_val = classifier.predict_proba(val_x)[:, 1]
    calibrator = LogisticRegression(C=1.0, random_state=seed)
    calibrator.fit(_logit(raw_val), val_y)
    val_scores = calibrator.predict_proba(_logit(raw_val))[:, 1]
    external_scores = calibrator.predict_proba(
        _logit(classifier.predict_proba(external_x)[:, 1])
    )[:, 1]
    return classifier, calibrator, val_scores, external_scores


def _checkpoint_record(
    *, model: str, seed: int, path: str, training_families: set[str],
    canonical_holds: set[str], control_holds: set[str], threshold: float,
    feature_names: tuple[str, ...] | None = None,
) -> dict:
    record = {
        "model": model,
        "seed": seed,
        "checkpoint_path": os.path.relpath(path, REPO_ROOT),
        "checkpoint_sha256": sha256_file(path),
        "training_family_ids": sorted(training_families),
        "excluded_canonical_family_ids": sorted(canonical_holds),
        "excluded_control_projects": sorted(control_holds),
        "validation_fold": VALIDATION_FOLD,
        "threshold_5pct": float(threshold),
        "threshold_fit_after_holds": True,
    }
    if feature_names is not None:
        record["feature_names"] = list(feature_names)
    return record


def main() -> int:
    if os.path.exists(TRAINING_MANIFEST) or os.path.exists(REVIEW_UNLOCK):
        raise FileExistsError(
            "post-cutoff scoring is already frozen; refusing a second training run that could "
            "be selected after labels"
        )
    os.makedirs(OUT_DIR, exist_ok=True)
    review = pd.read_csv(REVIEW_MANIFEST)
    expected_ids = set(review["item_id"].astype(str))
    project_by_item, canonical_holds, control_holds, _ = load_project_holds(
        HOLDOUT_PLAN, REVIEW_MANIFEST, CANONICAL_DATASET
    )
    assert_postcutoff_labels_absent(ANNOTATION_DB, expected_ids)

    sample_lock = _json(SAMPLE_LOCK)
    if sample_lock.get("sampling_status") != "COMPLETE":
        raise ValueError("score-blind sample lock is incomplete")
    if sample_lock.get("manifest_sha256") != sha256_file(REVIEW_MANIFEST):
        raise ValueError("sample lock review-manifest hash mismatch")
    dcrg_report = _json(DCRG_REPORT)
    if dcrg_report.get("snapshot_sha256") != sample_lock.get("snapshot_sha256"):
        raise ValueError("authority-DCRG artifact targets a different snapshot")
    if dcrg_report.get("features_sha256") != sha256_file(DCRG_FEATURES):
        raise ValueError("authority-DCRG feature hash mismatch")

    primary = load_primary_dataset()
    filtered = primary[~primary["family_id"].astype(str).isin(canonical_holds)].reset_index(drop=True)
    train_mask = filtered["fold_id"].to_numpy() != VALIDATION_FOLD
    val_mask = ~train_mask
    if filtered.loc[train_mask, "label"].nunique() != 2 or filtered.loc[val_mask, "label"].nunique() != 2:
        raise ValueError("post-hold train/validation data must each contain both classes")
    train_idx = np.flatnonzero(train_mask)
    val_idx = np.flatnonzero(val_mask)
    train_families = set(filtered.loc[train_mask, "family_id"].astype(str))

    historical_dcrg = pd.read_csv(PRIMARY_DCRG_FEATURES)
    filtered = filtered.merge(
        historical_dcrg[["sample_id", *DCRG_FEATURE_ORDER]],
        on="sample_id", how="left", validate="one_to_one",
    )
    if filtered[list(DCRG_FEATURE_ORDER)].isna().any().any():
        raise ValueError("historical DCRG features are incomplete")
    post_dcrg = pd.read_csv(DCRG_FEATURES)
    post = review.merge(
        post_dcrg[["sample_id", "coverage", *DCRG_FEATURE_ORDER]],
        left_on="item_id", right_on="sample_id", how="left", validate="one_to_one",
    )
    if post[list(DCRG_FEATURE_ORDER)].isna().any().any():
        raise ValueError("review sample is missing authority-aware DCRG features")

    token_cache = build_token_cache(primary, force=True)
    tensors = chunks_array_for_spec(filtered, token_cache, chunk_size=256, max_chunks=64)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[postcutoff_retraining] device={device}", flush=True)
    checkpoint_records = []
    prediction_rows = []
    for seed in SEEDS:
        # Model construction consumes the RNG, so seed before constructing it (the shared
        # harness also re-seeds before minibatch generation and optimization).
        np.random.seed(seed)
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
        model = HybridModel(HybridConfig(
            vocab_size=VOCAB_SIZE, chunk_size=256, max_chunks=64, use_dense=True
        ))
        model = train_one_model(
            model, hybrid_forward, tensors, train_idx, val_idx, device, seed=seed
        )
        val_logits = torch.as_tensor(
            score_indices(model, hybrid_forward, tensors, val_idx, device)
        )
        val_labels = filtered.loc[val_mask, "label"].to_numpy(dtype=np.int64)
        temperature = fit_temperature(
            val_logits, torch.as_tensor(val_labels, dtype=torch.float32)
        )
        sequence_val = apply_temperature(val_logits, temperature).numpy()
        sequence_external = np.asarray([
            float(apply_temperature(
                torch.as_tensor(
                    score_one({"kind": "hybrid"}, model, device, bytecode)
                ),
                temperature,
            ))
            for bytecode in post["runtime_bytecode"]
        ])
        sequence_threshold = threshold_at_nominal_fpr(sequence_val, val_labels, 0.05)
        sequence_path = os.path.join(OUT_DIR, f"sequence_seed{seed}.pt")
        torch.save({
            "model_state_dict": model.state_dict(),
            "model_config": {
                "vocab_size": VOCAB_SIZE, "chunk_size": 256,
                "max_chunks": 64, "use_dense": True,
            },
            "temperature": temperature,
            "threshold_5pct": sequence_threshold,
            "seed": seed,
            "validation_fold": VALIDATION_FOLD,
            "training_family_ids": sorted(train_families),
            "excluded_canonical_family_ids": sorted(canonical_holds),
        }, sequence_path)
        checkpoint_records.append(_checkpoint_record(
            model="sequence", seed=seed, path=sequence_path,
            training_families=train_families, canonical_holds=canonical_holds,
            control_holds=control_holds, threshold=sequence_threshold,
        ))

        train_y = filtered.loc[train_mask, "label"].to_numpy(np.int64)
        dcrg_val_by_group: dict[str, np.ndarray] = {}
        dcrg_external_by_group: dict[str, np.ndarray] = {}
        dcrg_threshold_by_group: dict[str, float] = {}
        for group_name, feature_names in FEATURE_GROUPS.items():
            train_x = filtered.loc[train_mask, list(feature_names)].to_numpy(np.float32)
            val_x = filtered.loc[val_mask, list(feature_names)].to_numpy(np.float32)
            post_x = post[list(feature_names)].to_numpy(np.float32)
            classifier, calibrator, group_val, group_external = _fit_dcrg(
                train_x, train_y, val_x, val_labels, post_x, seed
            )
            group_threshold = threshold_at_nominal_fpr(group_val, val_labels, 0.05)
            group_path = os.path.join(OUT_DIR, f"{group_name}_seed{seed}.pkl")
            with open(group_path, "wb") as handle:
                pickle.dump({
                    "classifier": classifier,
                    "calibrator": calibrator,
                    "feature_order": list(feature_names),
                    "threshold_5pct": group_threshold,
                    "seed": seed,
                    "validation_fold": VALIDATION_FOLD,
                    "training_family_ids": sorted(train_families),
                    "excluded_canonical_family_ids": sorted(canonical_holds),
                    "excluded_control_projects": sorted(control_holds),
                }, handle)
            checkpoint_records.append(_checkpoint_record(
                model=group_name, seed=seed, path=group_path,
                training_families=train_families, canonical_holds=canonical_holds,
                control_holds=control_holds, threshold=group_threshold,
                feature_names=tuple(feature_names),
            ))
            dcrg_val_by_group[group_name] = group_val
            dcrg_external_by_group[group_name] = group_external
            dcrg_threshold_by_group[group_name] = group_threshold

        dcrg_val = dcrg_val_by_group["dcrg_full"]
        dcrg_external = dcrg_external_by_group["dcrg_full"]
        dcrg_threshold = dcrg_threshold_by_group["dcrg_full"]

        fusion_val = risk_union(sequence_val, dcrg_val)
        fusion_external = risk_union(sequence_external, dcrg_external)
        fusion_threshold = threshold_at_nominal_fpr(fusion_val, val_labels, 0.05)
        for position, row in enumerate(post.itertuples(index=False)):
            project_id = project_by_item[str(row.item_id)]
            prediction = {
                "seed": seed,
                "sample_id": row.item_id,
                "family_id": project_id,
                "project_family_id": project_id,
                "coverage": row.coverage,
                "sequence_score": float(sequence_external[position]),
                "dcrg_score": float(dcrg_external[position]),
                "fusion_score": float(fusion_external[position]),
                "sequence_threshold_5pct": float(sequence_threshold),
                "dcrg_threshold_5pct": float(dcrg_threshold),
                "fusion_threshold_5pct": float(fusion_threshold),
            }
            for group_name in FEATURE_GROUPS:
                prediction[f"{group_name}_score"] = float(
                    dcrg_external_by_group[group_name][position]
                )
                prediction[f"{group_name}_threshold_5pct"] = float(
                    dcrg_threshold_by_group[group_name]
                )
            prediction_rows.append(prediction)
        print(f"[postcutoff_retraining] seed={seed} complete", flush=True)

    predictions = pd.DataFrame(prediction_rows).sort_values(["seed", "sample_id"])
    predictions.to_csv(
        PREDICTIONS, index=False,
        compression={"method": "gzip", "mtime": 0}, lineterminator="\n",
    )
    training_manifest = {
        "status": "FROZEN_POSTCUTOFF_RETRAINING_COMPLETE",
        "method_frozen_before_postcutoff_labels": True,
        "postcutoff_labels_accessed": False,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "validation_protocol": "canonical fold 0 after all mandatory family holds",
        "label_source_for_training": "inherited canonical source-rule labels only",
        "sample_lock_sha256": sha256_file(SAMPLE_LOCK),
        "holdout_plan_sha256": sha256_file(HOLDOUT_PLAN),
        "canonical_dataset_sha256": sha256_file(CANONICAL_DATASET),
        "predictions_path": os.path.relpath(PREDICTIONS, REPO_ROOT),
        "predictions_sha256": sha256_file(PREDICTIONS),
        "snapshot_sha256": sample_lock["snapshot_sha256"],
        "retraining_source_sha256": sha256_file(__file__),
        "dcrg_feature_source_sha256": dcrg_report["dcrg_source_sha256"],
        "dcrg_feature_groups": {
            name: list(features) for name, features in FEATURE_GROUPS.items()
        },
        "dcrg_feature_groups_source_sha256": sha256_file(DCRG_FEATURE_GROUP_SOURCE),
        "checkpoints": checkpoint_records,
        "n_training_rows": int(train_mask.sum()),
        "n_validation_rows": int(val_mask.sum()),
        "n_mandatory_canonical_family_holds": len(canonical_holds),
        "n_mandatory_control_project_holds": len(control_holds),
        "claim_boundary": (
            "Training labels remain inherited source-rule labels. Independent post-cutoff "
            "security labels are used only after predictions and checkpoints are frozen."
        ),
    }
    with open(TRAINING_MANIFEST, "w") as handle:
        json.dump(training_manifest, handle, indent=2, sort_keys=True)

    _, provenance = validate_postcutoff_scoring_provenance(
        review_manifest_path=REVIEW_MANIFEST,
        predictions_path=PREDICTIONS,
        holdout_plan_path=HOLDOUT_PLAN,
        training_manifest_path=TRAINING_MANIFEST,
        sample_lock_path=SAMPLE_LOCK,
        canonical_dataset_path=CANONICAL_DATASET,
        artifact_root=REPO_ROOT,
    )
    unlock = {
        "status": "POSTCUTOFF_REVIEW_UNLOCKED_AFTER_SCORING_FREEZE",
        "training_manifest": os.path.relpath(TRAINING_MANIFEST, REPO_ROOT),
        "training_manifest_sha256": sha256_file(TRAINING_MANIFEST),
        "predictions_sha256": sha256_file(PREDICTIONS),
        "provenance_status": provenance["status"],
        "claim_boundary": "This unlock exposes no model scores or labels to reviewers.",
    }
    with open(REVIEW_UNLOCK, "w") as handle:
        json.dump(unlock, handle, indent=2, sort_keys=True)
    print(json.dumps(unlock, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
