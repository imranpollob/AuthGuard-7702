"""Score preregistered external controls using only final frozen checkpoints.

This command must run immediately after post-cutoff retraining and before human annotation.
It never fits, calibrates, tunes, or selects a model.  It also proves that every evaluation
runtime and project was absent from the project-balanced model's development controls.
"""
from __future__ import annotations

import hashlib
import json
import os
import pickle
import sqlite3
import sys

import numpy as np
import pandas as pd
import torch

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
V3 = os.path.join(REPO_ROOT, "revision_v3")
sys.path.insert(0, os.path.join(V3, "src"))

from analysis.delegation_context import DCRG_FEATURE_ORDER  # noqa: E402
from evaluation.model_runtime import score_one  # noqa: E402
from features.encode import OPCODE_VOCAB, VOCAB_SIZE, encode_bytecode  # noqa: E402
from models.hybrid import HybridConfig, HybridModel  # noqa: E402
from training.calibration import apply_temperature  # noqa: E402

PROTOCOL = os.path.join(V3, "protocols", "external_legitimate_control_protocol_v1.json")
EXPECTED_PROTOCOL_SHA256 = "116f48c3878f9dc5173ff58913a2ba03e5655d82311aef06825edaaae1c56959"
REGISTRY = os.path.join(V3, "external_controls", "final_new_legitimate_projects.csv")
FEATURE_DIR = os.path.join(V3, "results", "external_legitimate_controls_features")
FEATURES = os.path.join(FEATURE_DIR, "external_legitimate_control_dcrg_features.csv.gz")
FEATURE_REPORT = os.path.join(FEATURE_DIR, "external_legitimate_control_dcrg_report.json")
TRAINING_DIR = os.path.join(V3, "results", "postcutoff_retraining")
TRAINING_MANIFEST = os.path.join(TRAINING_DIR, "postcutoff_training_manifest.json")
ANNOTATION_DB = os.path.join(V3, "annotation_app", "annotation.db")
OUT_DIR = os.path.join(V3, "results", "external_legitimate_controls_final")
SEED_OUTPUT = os.path.join(OUT_DIR, "external_legitimate_control_seed_scores.csv.gz")
ITEM_OUTPUT = os.path.join(OUT_DIR, "external_legitimate_control_results.csv")
REPORT = os.path.join(OUT_DIR, "external_legitimate_control_evaluation_report.json")

MODELS = [
    "dcrg_full",
    "dcrg_project_balanced",
    "dcrg_untyped_guards",
    "hist_ngram_xgb",
    "sequence",
]


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path: str) -> dict:
    with open(path) as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _logit(values: np.ndarray) -> np.ndarray:
    epsilon = 1e-6
    clipped = np.clip(values, epsilon, 1 - epsilon)
    return np.log(clipped / (1 - clipped)).reshape(-1, 1)


def consensus_decision(
    n_seed_warn: int,
    n_seeds: int,
    coverage: str,
    authority_context_available: bool,
) -> str:
    """Conservative fixed consensus: disagreement and incomplete context both defer."""
    if n_seeds != 3:
        raise ValueError("the frozen protocol requires exactly three seeds")
    if n_seed_warn >= 2:
        return "WARN"
    if n_seed_warn == 1:
        return "DEFER"
    if coverage != "COMPLETE" or not authority_context_available:
        return "DEFER"
    return "NO_MODEL_WARNING"


def assert_zero_postcutoff_annotations() -> None:
    connection = sqlite3.connect(ANNOTATION_DB)
    count = connection.execute(
        "SELECT COUNT(*) FROM annotations a JOIN items i ON i.item_id=a.item_id "
        "WHERE i.sample_set='postcutoff'"
    ).fetchone()[0]
    connection.close()
    if count:
        raise ValueError(
            "post-cutoff human annotations exist; external scoring was required before labels"
        )


def _load_runtime(row: dict) -> str:
    path = os.path.join(REPO_ROOT, str(row["frozen_bytecode_path"]))
    if sha256_file(path) != str(row["frozen_bytecode_file_sha256"]):
        raise ValueError(f"frozen bytecode file hash mismatch for {row['control_id']}")
    with open(path) as handle:
        value = handle.read().strip()
    return value if value.startswith("0x") else "0x" + value


def validate_preconditions() -> tuple[dict, dict, pd.DataFrame, pd.DataFrame]:
    if os.path.exists(OUT_DIR):
        raise FileExistsError("external control scores are already frozen")
    if sha256_file(PROTOCOL) != EXPECTED_PROTOCOL_SHA256:
        raise ValueError("external-control protocol hash differs from the frozen evaluator")
    protocol = _json(PROTOCOL)
    if protocol.get("status") != "EXTERNAL_LEGITIMATE_CONTROLS_PREREGISTERED_BEFORE_SCORING":
        raise ValueError("external-control protocol status is invalid")
    if not os.path.exists(TRAINING_MANIFEST):
        raise FileNotFoundError("final post-cutoff training manifest does not exist")
    training = _json(TRAINING_MANIFEST)
    if training.get("status") != "FROZEN_POSTCUTOFF_RETRAINING_COMPLETE":
        raise ValueError("post-cutoff checkpoint freeze is incomplete")
    assert_zero_postcutoff_annotations()

    feature_report = _json(FEATURE_REPORT)
    if feature_report.get("status") != "FROZEN_SCORE_BLIND_EXTERNAL_CONTROL_DCRG_FEATURES":
        raise ValueError("external feature artifact is not score-blind and frozen")
    if feature_report.get("protocol_sha256") != EXPECTED_PROTOCOL_SHA256:
        raise ValueError("external features were not built under the frozen protocol")
    if feature_report.get("features_sha256") != sha256_file(FEATURES):
        raise ValueError("external DCRG feature hash mismatch")
    if protocol["registry"]["sha256"] != sha256_file(REGISTRY):
        raise ValueError("external registry hash mismatch")

    registry = pd.read_csv(REGISTRY)
    features = pd.read_csv(FEATURES)
    if set(registry["control_id"]) != set(features["control_id"]):
        raise ValueError("registry and external feature populations differ")
    evaluation_projects = set(registry["project"].astype(str))
    evaluation_hashes = set(registry["runtime_bytecode_sha256"].astype(str))
    training_projects = set(map(str, training.get("legitimate_control_projects_used", [])))
    training_hashes = set(map(str, training.get("legitimate_control_runtime_hashes_used", [])))
    if evaluation_projects & training_projects:
        raise ValueError("external evaluation project leaked into project-balanced training")
    if evaluation_hashes & training_hashes:
        raise ValueError("external evaluation runtime leaked into project-balanced training")

    checkpoints = training.get("checkpoints", [])
    for model in MODELS:
        records = [record for record in checkpoints if record.get("model") == model]
        if len(records) != 3 or len({int(record["seed"]) for record in records}) != 3:
            raise ValueError(f"{model} does not have exactly three frozen seed checkpoints")
        for record in records:
            path = os.path.join(REPO_ROOT, record["checkpoint_path"])
            if sha256_file(path) != record["checkpoint_sha256"]:
                raise ValueError(f"checkpoint hash mismatch: {record['checkpoint_path']}")
    return protocol, training, registry, features


def _score_pickle_checkpoint(
    model: str, checkpoint_path: str, features: pd.DataFrame, hist_features: np.ndarray
) -> tuple[np.ndarray, float, int]:
    with open(checkpoint_path, "rb") as handle:
        checkpoint = pickle.load(handle)
    if model == "hist_ngram_xgb":
        classifier = checkpoint["classifier"]
        raw = classifier.predict_proba(hist_features)[:, 1]
        logits = torch.as_tensor(_logit(raw).reshape(-1), dtype=torch.float32)
        scores = apply_temperature(logits, checkpoint["temperature"]).numpy()
    else:
        feature_order = list(checkpoint["feature_order"])
        x = features[feature_order].to_numpy(np.float32)
        raw = checkpoint["classifier"].predict_proba(x)[:, 1]
        scores = checkpoint["calibrator"].predict_proba(_logit(raw))[:, 1]
    return np.asarray(scores, dtype=np.float64), float(checkpoint["threshold_5pct"]), int(
        checkpoint["seed"]
    )


def _score_sequence_checkpoint(
    checkpoint_path: str, bytecodes: list[str]
) -> tuple[np.ndarray, float, int]:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    config = checkpoint["model_config"]
    model = HybridModel(HybridConfig(
        vocab_size=int(config.get("vocab_size", VOCAB_SIZE)),
        chunk_size=int(config["chunk_size"]),
        max_chunks=int(config["max_chunks"]),
        use_dense=bool(config["use_dense"]),
    ))
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device).eval()
    scores = np.asarray([
        float(apply_temperature(
            torch.as_tensor(score_one({"kind": "hybrid"}, model, device, bytecode)),
            checkpoint["temperature"],
        ))
        for bytecode in bytecodes
    ])
    return scores, float(checkpoint["threshold_5pct"]), int(checkpoint["seed"])


def main() -> int:
    protocol, training, registry, features = validate_preconditions()
    merged = registry.merge(features, on=["control_id", "project", "classification"], validate="one_to_one")
    merged = merged.sort_values("control_id", kind="mergesort").reset_index(drop=True)
    bytecodes = [_load_runtime(row) for row in merged.to_dict("records")]
    histogram_dim = len(OPCODE_VOCAB)
    hist_features = np.stack([
        np.concatenate([
            encode_bytecode(bytecode).dense[:histogram_dim],
            encode_bytecode(bytecode).ngram,
        ])
        for bytecode in bytecodes
    ]).astype(np.float32)
    checkpoint_by_model = {
        model: sorted(
            [record for record in training["checkpoints"] if record["model"] == model],
            key=lambda record: int(record["seed"]),
        )
        for model in MODELS
    }
    seed_rows = []
    for model in MODELS:
        for record in checkpoint_by_model[model]:
            path = os.path.join(REPO_ROOT, record["checkpoint_path"])
            if model == "sequence":
                scores, threshold, seed = _score_sequence_checkpoint(path, bytecodes)
            else:
                scores, threshold, seed = _score_pickle_checkpoint(
                    model, path, merged, hist_features
                )
            if not np.isclose(threshold, float(record["threshold_5pct"])):
                raise ValueError(f"checkpoint threshold differs from manifest for {model} seed {seed}")
            for position, row in enumerate(merged.to_dict("records")):
                seed_rows.append({
                    "control_id": row["control_id"],
                    "project": row["project"],
                    "model": model,
                    "seed": seed,
                    "score": float(scores[position]),
                    "threshold_5pct": threshold,
                    "seed_warn": bool(scores[position] >= threshold),
                })
    seed_frame = pd.DataFrame(seed_rows).sort_values(
        ["control_id", "model", "seed"], kind="mergesort"
    )
    item_rows = []
    for row in merged.to_dict("records"):
        for model in MODELS:
            votes = seed_frame.loc[
                seed_frame["control_id"].eq(row["control_id"])
                & seed_frame["model"].eq(model)
            ]
            n_warn = int(votes["seed_warn"].sum())
            authority_available = row["authority_context_status"] != "UNAVAILABLE_DEPLOYMENT_ONLY"
            decision = consensus_decision(n_warn, len(votes), row["coverage"], authority_available)
            item_rows.append({
                "control_id": row["control_id"],
                "project": row["project"],
                "classification": row["classification"],
                "new_project_endpoint_eligible": row["new_project_endpoint_eligible"],
                "canonical_unseen_at_0_85": row["canonical_unseen_at_0_85"],
                "actual_use_status": row["actual_use_status"],
                "coverage": row["coverage"],
                "authority_context_status": row["authority_context_status"],
                "model": model,
                "score_mean": float(votes["score"].mean()),
                "score_min": float(votes["score"].min()),
                "score_max": float(votes["score"].max()),
                "threshold_mean": float(votes["threshold_5pct"].mean()),
                "n_seed_warn": n_warn,
                "consensus_decision": decision,
            })
    items = pd.DataFrame(item_rows).sort_values(["control_id", "model"], kind="mergesort")
    principal = items.loc[
        items["model"].eq(protocol["principal_descriptive_model"]["model"])
        & items["new_project_endpoint_eligible"].eq(True)  # noqa: E712
    ]

    def decision_counts(frame: pd.DataFrame) -> dict:
        counts = frame["consensus_decision"].value_counts().to_dict()
        return {key: int(counts.get(key, 0)) for key in ["WARN", "NO_MODEL_WARNING", "DEFER"]}

    used_projects = set(protocol["predeclared_strata"]["observed_use_new_projects"]["projects"])
    unseen_projects = set(
        protocol["predeclared_strata"]["canonical_unseen_runtime_families"]["projects"]
    )
    report = {
        "status": "FROZEN_EXTERNAL_LEGITIMATE_CONTROL_EVALUATION_COMPLETE",
        "protocol_sha256": sha256_file(PROTOCOL),
        "registry_sha256": sha256_file(REGISTRY),
        "feature_report_sha256": sha256_file(FEATURE_REPORT),
        "training_manifest_sha256": sha256_file(TRAINING_MANIFEST),
        "evaluator_sha256": sha256_file(__file__),
        "postcutoff_human_annotations_accessed": False,
        "n_controls": int(merged["control_id"].nunique()),
        "n_new_project_controls": int(principal["control_id"].nunique()),
        "principal_model": protocol["principal_descriptive_model"]["model"],
        "principal_decision_counts": decision_counts(principal),
        "observed_use_decision_counts": decision_counts(
            principal.loc[principal["project"].isin(used_projects)]
        ),
        "canonical_unseen_decision_counts": decision_counts(
            principal.loc[principal["project"].isin(unseen_projects)]
        ),
        "consensus_rule": (
            "WARN for at least two of three seed warnings; DEFER for one-seed disagreement, "
            "non-COMPLETE coverage, or missing authority context; otherwise NO_MODEL_WARNING"
        ),
        "seed_scores_sha256": "PENDING",
        "item_results_sha256": "PENDING",
        "claim_boundary": protocol["claim_boundary"],
    }
    os.makedirs(OUT_DIR, exist_ok=False)
    seed_frame.to_csv(
        SEED_OUTPUT,
        index=False,
        compression={"method": "gzip", "mtime": 0},
        lineterminator="\n",
    )
    items.to_csv(ITEM_OUTPUT, index=False, lineterminator="\n")
    report["seed_scores_sha256"] = sha256_file(SEED_OUTPUT)
    report["item_results_sha256"] = sha256_file(ITEM_OUTPUT)
    with open(REPORT, "w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
