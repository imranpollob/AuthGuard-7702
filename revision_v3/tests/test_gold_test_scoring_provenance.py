from __future__ import annotations

import json

import pandas as pd
import pytest

from analysis.dcrg_feature_groups import FEATURE_GROUPS
from evaluation.gold_test_provenance import (
    LOCK_STATUS,
    sha256_file,
    validate_gold_test_scoring_provenance,
)


def _fixture(tmp_path):
    manifest_path = tmp_path / "manifest.csv"
    fusion_path = tmp_path / "fusion.csv"
    ablation_path = tmp_path / "ablation.csv"
    lock_path = tmp_path / "lock.json"
    pd.DataFrame({"item_id": ["a", "b"], "family_id": ["F1", "F2"]}).to_csv(
        manifest_path, index=False
    )
    fusion_rows = []
    ablation_rows = []
    for seed in (7702, 7703):
        for item_id, family_id in (("a", "F1"), ("b", "F2")):
            fusion_rows.append({
                "seed": seed, "sample_id": item_id, "family_id": family_id,
                "coverage": "COMPLETE", "sequence_score": 0.2, "dcrg_score": 0.3,
                "fusion_score": 0.44, "sequence_threshold_5pct": 0.5,
                "dcrg_threshold_5pct": 0.5, "fusion_threshold_5pct": 0.6,
            })
            for model in FEATURE_GROUPS:
                ablation_rows.append({
                    "seed": seed, "sample_id": item_id, "family_id": family_id,
                    "model": model, "score": 0.3, "threshold_5pct": 0.5,
                })
    pd.DataFrame(fusion_rows).to_csv(fusion_path, index=False)
    pd.DataFrame(ablation_rows).to_csv(ablation_path, index=False)
    artifacts = {}
    for name, path in (
        ("gold_test_manifest", manifest_path),
        ("fusion_predictions", fusion_path),
        ("ablation_predictions", ablation_path),
    ):
        artifacts[name] = {"path": path.name, "sha256": sha256_file(str(path))}
    lock_path.write_text(json.dumps({
        "status": LOCK_STATUS,
        "method_frozen_before_human_labels": True,
        "human_annotations_present_at_freeze": False,
        "n_items": 2,
        "seeds": [7702, 7703],
        "dcrg_feature_groups": {
            name: list(features) for name, features in FEATURE_GROUPS.items()
        },
        "artifacts": artifacts,
    }))
    return {
        "manifest_path": str(manifest_path),
        "fusion_predictions_path": str(fusion_path),
        "ablation_predictions_path": str(ablation_path),
        "lock_path": str(lock_path),
        "artifact_root": str(tmp_path),
    }


def test_gold_test_scoring_lock_accepts_exact_score_only_artifacts(tmp_path):
    paths = _fixture(tmp_path)
    fusion, ablation, report = validate_gold_test_scoring_provenance(**paths)
    assert len(fusion) == 4
    assert len(ablation) == 16
    assert report["status"] == "GOLD_TEST_SCORING_PROVENANCE_VERIFIED"


def test_gold_test_scoring_lock_rejects_hash_tampering(tmp_path):
    paths = _fixture(tmp_path)
    with open(paths["fusion_predictions_path"], "a") as handle:
        handle.write("\n")
    with pytest.raises(ValueError, match="locked hash mismatch"):
        validate_gold_test_scoring_provenance(**paths)


def test_gold_test_scoring_lock_rejects_label_bearing_artifact(tmp_path):
    paths = _fixture(tmp_path)
    frame = pd.read_csv(paths["ablation_predictions_path"])
    frame["label"] = 1
    frame.to_csv(paths["ablation_predictions_path"], index=False)
    lock = json.loads(open(paths["lock_path"]).read())
    lock["artifacts"]["ablation_predictions"]["sha256"] = sha256_file(
        paths["ablation_predictions_path"]
    )
    with open(paths["lock_path"], "w") as handle:
        json.dump(lock, handle)
    with pytest.raises(ValueError, match="unexpected or missing columns"):
        validate_gold_test_scoring_provenance(**paths)
