"""Cryptographic and coverage validation for pre-human-label Gold-Test scores."""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any

import numpy as np
import pandas as pd

from analysis.dcrg_feature_groups import FEATURE_GROUPS

LOCK_STATUS = "FROZEN_GOLD_TEST_SCORING_BEFORE_HUMAN_LABELS"
FUSION_COLUMNS = (
    "seed", "sample_id", "family_id", "coverage",
    "sequence_score", "dcrg_score", "fusion_score",
    "sequence_threshold_5pct", "dcrg_threshold_5pct", "fusion_threshold_5pct",
)
ABLATION_COLUMNS = (
    "seed", "sample_id", "family_id", "model", "score", "threshold_5pct",
)


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path: str) -> dict[str, Any]:
    with open(path) as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _validate_probability_columns(frame: pd.DataFrame, columns: list[str]) -> None:
    for column in columns:
        values = pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=float)
        if not np.isfinite(values).all() or ((values < 0) | (values > 1)).any():
            raise ValueError(f"{column} must contain only finite values in [0,1]")


def validate_gold_test_frames(
    manifest: pd.DataFrame,
    fusion: pd.DataFrame,
    ablation: pd.DataFrame,
) -> tuple[list[int], dict[str, str]]:
    """Require exact item/family/model/seed coverage and label-free score columns."""
    if set(fusion.columns) != set(FUSION_COLUMNS):
        raise ValueError("Gold-Test fusion artifact has unexpected or missing columns")
    if set(ablation.columns) != set(ABLATION_COLUMNS):
        raise ValueError("Gold-Test ablation artifact has unexpected or missing columns")
    if not {"item_id", "family_id"}.issubset(manifest.columns):
        raise ValueError("Gold-Test manifest is missing item_id or family_id")
    if manifest["item_id"].isna().any() or manifest["item_id"].duplicated().any():
        raise ValueError("Gold-Test manifest item IDs must be unique and nonempty")
    family_by_item = dict(zip(
        manifest["item_id"].astype(str), manifest["family_id"].astype(str), strict=True
    ))
    expected_ids = set(family_by_item)
    fusion_seeds = sorted(int(seed) for seed in fusion["seed"].unique())
    ablation_seeds = sorted(int(seed) for seed in ablation["seed"].unique())
    if not fusion_seeds or fusion_seeds != ablation_seeds:
        raise ValueError("Gold-Test fusion and ablation seeds do not match")
    for seed in fusion_seeds:
        rows = fusion[fusion["seed"] == seed]
        if set(rows["sample_id"].astype(str)) != expected_ids or rows["sample_id"].duplicated().any():
            raise ValueError(f"Gold-Test fusion coverage mismatch for seed {seed}")
    if set(ablation["model"].astype(str)) != set(FEATURE_GROUPS):
        raise ValueError("Gold-Test ablation model set differs from the predeclared groups")
    for seed in ablation_seeds:
        for model in FEATURE_GROUPS:
            rows = ablation[(ablation["seed"] == seed) & (ablation["model"] == model)]
            if set(rows["sample_id"].astype(str)) != expected_ids or rows["sample_id"].duplicated().any():
                raise ValueError(f"Gold-Test ablation coverage mismatch for {model}/seed {seed}")
    for frame in (fusion, ablation):
        for row in frame[["sample_id", "family_id"]].drop_duplicates().to_dict("records"):
            if family_by_item.get(str(row["sample_id"])) != str(row["family_id"]):
                raise ValueError(f"Gold-Test family mismatch for {row['sample_id']}")
    _validate_probability_columns(
        fusion,
        [column for column in FUSION_COLUMNS if column.endswith("score") or "threshold" in column],
    )
    _validate_probability_columns(ablation, ["score", "threshold_5pct"])
    return fusion_seeds, family_by_item


def validate_gold_test_scoring_provenance(
    *,
    manifest_path: str,
    fusion_predictions_path: str,
    ablation_predictions_path: str,
    lock_path: str,
    artifact_root: str,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Validate the immutable lock and return the score-only frozen artifacts."""
    lock = _json(lock_path)
    if lock.get("status") != LOCK_STATUS:
        raise ValueError("Gold-Test scoring lock is not complete")
    if lock.get("method_frozen_before_human_labels") is not True:
        raise ValueError("Gold-Test scoring lock lacks the pre-label freeze attestation")
    if lock.get("human_annotations_present_at_freeze") is not False:
        raise ValueError("Gold-Test scoring was not frozen before annotations")
    paths = {
        "gold_test_manifest": manifest_path,
        "fusion_predictions": fusion_predictions_path,
        "ablation_predictions": ablation_predictions_path,
    }
    root = os.path.realpath(artifact_root)
    for name, supplied in paths.items():
        record = lock.get("artifacts", {}).get(name, {})
        relative = record.get("path")
        if not isinstance(relative, str) or os.path.isabs(relative):
            raise ValueError(f"invalid locked path for {name}")
        resolved = os.path.realpath(os.path.join(root, relative))
        if os.path.commonpath([root, resolved]) != root or resolved != os.path.realpath(supplied):
            raise ValueError(f"Gold-Test lock points to a different {name} artifact")
        if not os.path.isfile(resolved) or record.get("sha256") != sha256_file(resolved):
            raise ValueError(f"Gold-Test locked hash mismatch for {name}")
    expected_groups = {name: list(features) for name, features in FEATURE_GROUPS.items()}
    if lock.get("dcrg_feature_groups") != expected_groups:
        raise ValueError("Gold-Test lock feature groups differ from the predeclared ablations")
    manifest = pd.read_csv(manifest_path)
    fusion = pd.read_csv(fusion_predictions_path)
    ablation = pd.read_csv(ablation_predictions_path)
    seeds, _ = validate_gold_test_frames(manifest, fusion, ablation)
    if int(lock.get("n_items", -1)) != len(manifest) or lock.get("seeds") != seeds:
        raise ValueError("Gold-Test lock count or seed metadata mismatch")
    return fusion, ablation, {
        "status": "GOLD_TEST_SCORING_PROVENANCE_VERIFIED",
        "lock_sha256": sha256_file(lock_path),
        "n_items": len(manifest),
        "n_prediction_seeds": len(seeds),
        "n_ablation_models": len(FEATURE_GROUPS),
        "claim_boundary": (
            "The lock proves artifact identity and that no annotation rows existed at freeze time; "
            "it does not establish semantic correctness of subsequent human labels."
        ),
    }
