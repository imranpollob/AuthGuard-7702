"""Create the one-time score-only Gold-Test lock before any human annotation exists."""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
V3 = os.path.join(REPO_ROOT, "revision_v3")
sys.path.insert(0, os.path.join(V3, "src"))

from analysis.dcrg_feature_groups import FEATURE_GROUPS  # noqa: E402
from evaluation.gold_test_provenance import (  # noqa: E402
    ABLATION_COLUMNS,
    FUSION_COLUMNS,
    LOCK_STATUS,
    sha256_file,
    validate_gold_test_frames,
)

MANIFEST = os.path.join(V3, "human_eval", "gold_test_manifest.csv")
SOURCE_FUSION = os.path.join(V3, "results", "delegation_context", "dcrg_fusion_predictions.csv.gz")
SOURCE_ABLATION = os.path.join(V3, "results", "delegation_context", "dcrg_ablation_predictions.csv.gz")
OUT_DIR = os.path.join(V3, "results", "human_final")
FROZEN_FUSION = os.path.join(OUT_DIR, "gold_test_frozen_predictions.csv.gz")
FROZEN_ABLATION = os.path.join(OUT_DIR, "gold_test_frozen_ablation_predictions.csv.gz")
LOCK = os.path.join(OUT_DIR, "gold_test_scoring_lock.json")
ANNOTATION_DB = os.path.join(V3, "annotation_app", "annotation.db")


def _relative_record(path: str) -> dict[str, str]:
    return {"path": os.path.relpath(path, REPO_ROOT), "sha256": sha256_file(path)}


def assert_no_gold_test_annotations(db_path: str, expected_ids: set[str]) -> None:
    connection = sqlite3.connect(db_path)
    try:
        observed = {
            str(row[0]) for row in connection.execute(
                "SELECT item_id FROM items WHERE sample_set='gold_test'"
            ).fetchall()
        }
        if observed != expected_ids:
            raise ValueError("annotation DB Gold-Test items do not match the frozen manifest")
        count = connection.execute(
            "SELECT COUNT(*) FROM annotations a JOIN items i ON i.item_id=a.item_id "
            "WHERE i.sample_set='gold_test'"
        ).fetchone()[0]
    finally:
        connection.close()
    if int(count) != 0:
        raise ValueError("Gold-Test annotations already exist; refusing a post-label score freeze")


def main() -> int:
    for path in (FROZEN_FUSION, FROZEN_ABLATION, LOCK):
        if os.path.exists(path):
            raise FileExistsError(f"Gold-Test scoring is already frozen: {path}")
    manifest = pd.read_csv(MANIFEST)
    expected_ids = set(manifest["item_id"].astype(str))
    assert_no_gold_test_annotations(ANNOTATION_DB, expected_ids)
    fusion_source = pd.read_csv(SOURCE_FUSION)
    ablation_source = pd.read_csv(SOURCE_ABLATION)
    fusion = fusion_source[fusion_source["sample_id"].isin(expected_ids)][list(FUSION_COLUMNS)].copy()
    ablation = ablation_source[ablation_source["sample_id"].isin(expected_ids)][list(ABLATION_COLUMNS)].copy()
    seeds, _ = validate_gold_test_frames(manifest, fusion, ablation)
    os.makedirs(OUT_DIR, exist_ok=True)
    fusion.sort_values(["seed", "sample_id"]).to_csv(
        FROZEN_FUSION, index=False,
        compression={"method": "gzip", "mtime": 0}, lineterminator="\n",
    )
    ablation.sort_values(["seed", "model", "sample_id"]).to_csv(
        FROZEN_ABLATION, index=False,
        compression={"method": "gzip", "mtime": 0}, lineterminator="\n",
    )
    lock = {
        "status": LOCK_STATUS,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "method_frozen_before_human_labels": True,
        "human_annotations_present_at_freeze": False,
        "n_items": len(manifest),
        "seeds": seeds,
        "dcrg_feature_groups": {
            name: list(features) for name, features in FEATURE_GROUPS.items()
        },
        "artifacts": {
            "gold_test_manifest": _relative_record(MANIFEST),
            "fusion_predictions": _relative_record(FROZEN_FUSION),
            "ablation_predictions": _relative_record(FROZEN_ABLATION),
        },
        "source_artifacts": {
            "fusion_predictions_sha256": sha256_file(SOURCE_FUSION),
            "ablation_predictions_sha256": sha256_file(SOURCE_ABLATION),
        },
        "claim_boundary": (
            "Scores use inherited source-rule training labels. The lock establishes only that "
            "score-only artifacts were fixed before any Gold-Test human annotation existed."
        ),
    }
    with open(LOCK, "w") as handle:
        json.dump(lock, handle, indent=2, sort_keys=True)
    print(json.dumps(lock, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
