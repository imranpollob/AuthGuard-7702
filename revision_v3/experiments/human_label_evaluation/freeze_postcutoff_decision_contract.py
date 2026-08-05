#!/usr/bin/env python3
"""Freeze label-free WARN/NO_MODEL_WARNING/DEFER decisions before human review."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PREDICTIONS = ROOT / "revision_v3/results/postcutoff_retraining/postcutoff_predictions.csv.gz"
DEFAULT_TRAINING = ROOT / "revision_v3/results/postcutoff_retraining/postcutoff_training_manifest.json"
DEFAULT_MANIFEST = ROOT / "revision_v3/results/postcutoff_snapshot/postcutoff_review_manifest.csv"
DEFAULT_HOLD_PLAN = ROOT / "revision_v3/results/postcutoff_snapshot/postcutoff_family_holdout_plan.json"
DEFAULT_DB = ROOT / "revision_v3/annotation_app/annotation.db"
DEFAULT_DECISIONS = ROOT / "revision_v3/results/postcutoff_retraining/postcutoff_consensus_decisions.csv.gz"
DEFAULT_REPORT = ROOT / "revision_v3/results/postcutoff_retraining/postcutoff_decision_contract_lock.json"

EXPECTED_SEEDS = {7702, 7703, 7704}
MODEL_COLUMNS = {
    "sequence": ("sequence_score", "sequence_threshold_5pct"),
    "hist_ngram_xgb": ("hist_ngram_xgb_score", "hist_ngram_xgb_threshold_5pct"),
    "cfg_capability_only": ("cfg_capability_only_score", "cfg_capability_only_threshold_5pct"),
    "dcrg_untyped_guards": ("dcrg_untyped_guards_score", "dcrg_untyped_guards_threshold_5pct"),
    "dcrg_without_protocol_actors": (
        "dcrg_without_protocol_actors_score", "dcrg_without_protocol_actors_threshold_5pct"
    ),
    "dcrg_full": ("dcrg_full_score", "dcrg_full_threshold_5pct"),
    "dcrg_project_balanced": (
        "dcrg_project_balanced_score", "dcrg_project_balanced_threshold_5pct"
    ),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def consensus_decision(
    seed_warning_votes: list[bool], *, coverage: str, authority_available: bool,
) -> str:
    if len(seed_warning_votes) != 3:
        raise ValueError("decision consensus requires exactly three frozen seeds")
    n_warn = sum(bool(value) for value in seed_warning_votes)
    if n_warn >= 2:
        return "WARN"
    if n_warn == 1:
        return "DEFER"
    if str(coverage) != "COMPLETE" or not authority_available:
        return "DEFER"
    return "NO_MODEL_WARNING"


def build_consensus_decisions(
    predictions: pd.DataFrame, manifest: pd.DataFrame, excluded_item_ids: set[str],
) -> pd.DataFrame:
    forbidden = {
        column for column in predictions.columns
        if any(token in column.lower() for token in ("label", "judgment", "outcome"))
    }
    if forbidden:
        raise ValueError(f"prediction artifact contains label-like columns: {sorted(forbidden)}")
    required = {"seed", "sample_id", "coverage", *(
        column for pair in MODEL_COLUMNS.values() for column in pair
    )}
    missing = required - set(predictions.columns)
    if missing:
        raise ValueError(f"prediction artifact is missing columns: {sorted(missing)}")
    if set(pd.to_numeric(predictions["seed"]).astype(int)) != EXPECTED_SEEDS:
        raise ValueError("prediction artifact must contain exactly seeds 7702, 7703, and 7704")
    if manifest["item_id"].duplicated().any() or len(manifest) != 150:
        raise ValueError("post-cutoff manifest must contain exactly 150 unique items")
    eligible = set(manifest["item_id"].astype(str)) - excluded_item_ids
    if set(predictions["sample_id"].astype(str)) != eligible:
        raise ValueError("scored item IDs do not equal manifest IDs minus frozen exclusions")
    context = manifest.set_index("item_id")["authority_address"].fillna("").astype(str)
    rows: list[dict] = []
    for item_id in sorted(eligible):
        item = predictions[predictions["sample_id"] == item_id].sort_values("seed")
        if len(item) != 3 or set(pd.to_numeric(item["seed"]).astype(int)) != EXPECTED_SEEDS:
            raise ValueError(f"{item_id}: incomplete or duplicated three-seed predictions")
        coverages = set(item["coverage"].astype(str))
        if len(coverages) != 1:
            raise ValueError(f"{item_id}: coverage differs across seeds")
        coverage = next(iter(coverages))
        authority_available = bool(context.get(item_id, "").strip())
        for model, (score_column, threshold_column) in MODEL_COLUMNS.items():
            scores = pd.to_numeric(item[score_column], errors="coerce").to_numpy(float)
            thresholds = pd.to_numeric(item[threshold_column], errors="coerce").to_numpy(float)
            if not np.isfinite(scores).all() or not np.isfinite(thresholds).all():
                raise ValueError(f"{item_id}/{model}: nonfinite score or threshold")
            votes = (scores >= thresholds).tolist()
            rows.append({
                "sample_id": item_id,
                "model": model,
                "coverage": coverage,
                "authority_available": authority_available,
                "n_seed_warning_votes": int(sum(votes)),
                "consensus_decision": consensus_decision(
                    votes, coverage=coverage, authority_available=authority_available
                ),
            })
    result = pd.DataFrame(rows).sort_values(["model", "sample_id"]).reset_index(drop=True)
    if len(result) != len(eligible) * len(MODEL_COLUMNS):
        raise AssertionError("decision artifact cardinality mismatch")
    return result


def _postcutoff_annotation_count(path: Path) -> int:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return int(connection.execute(
            "SELECT COUNT(*) FROM annotations a JOIN items i USING(item_id) "
            "WHERE i.sample_set='postcutoff'"
        ).fetchone()[0])
    finally:
        connection.close()


def freeze_decision_contract(
    *, predictions_path: Path, training_path: Path, manifest_path: Path,
    hold_plan_path: Path, db_path: Path, decisions_path: Path,
) -> dict:
    if _postcutoff_annotation_count(db_path) != 0:
        raise ValueError("refusing to freeze the decision contract after human annotation began")
    training = json.loads(training_path.read_text())
    hold_plan = json.loads(hold_plan_path.read_text())
    if training.get("status") != "FROZEN_POSTCUTOFF_RETRAINING_COMPLETE":
        raise ValueError("post-cutoff retraining is not frozen")
    if training.get("predictions_sha256") != sha256_file(predictions_path):
        raise ValueError("prediction hash does not match the frozen training manifest")
    if training.get("holdout_plan_sha256") != sha256_file(hold_plan_path):
        raise ValueError("hold-plan hash does not match the frozen training manifest")
    excluded = set(map(str, hold_plan.get("excluded_item_ids", [])))
    predictions = pd.read_csv(predictions_path)
    manifest = pd.read_csv(manifest_path, usecols=["item_id", "authority_address"])
    decisions = build_consensus_decisions(predictions, manifest, excluded)
    decisions_path.parent.mkdir(parents=True, exist_ok=True)
    decisions.to_csv(decisions_path, index=False, compression="gzip", lineterminator="\n")
    evaluation_source = (
        ROOT / "revision_v3/experiments/human_label_evaluation/"
        "evaluate_frozen_postcutoff_decisions.py"
    )
    source_path = Path(__file__).resolve()
    by_model = {}
    for model, frame in decisions.groupby("model", sort=True):
        counts = Counter(frame["consensus_decision"])
        by_model[str(model)] = {
            key: int(counts.get(key, 0)) for key in ("WARN", "NO_MODEL_WARNING", "DEFER")
        }
    return {
        "schema": "authguard-postcutoff-decision-contract-1.0",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "FROZEN_POSTCUTOFF_DECISION_CONTRACT_BEFORE_HUMAN_LABELS",
        "claim_boundary": (
            "Decisions are label-free frozen operating outputs. NO_MODEL_WARNING is not safety, "
            "legitimacy, or authorization advice; all later label-based rates are descriptive."
        ),
        "consensus_rule": (
            "WARN for at least two of three seed warnings; DEFER for one-seed disagreement, "
            "non-COMPLETE coverage, or missing authority; otherwise NO_MODEL_WARNING"
        ),
        "n_manifest_items": int(len(manifest)),
        "n_excluded_items": int(len(excluded)),
        "n_scored_items": int(decisions["sample_id"].nunique()),
        "n_postcutoff_annotations_at_freeze": 0,
        "models": sorted(MODEL_COLUMNS),
        "decision_counts_by_model": by_model,
        "decisions_path": str(decisions_path.relative_to(ROOT)),
        "decisions_sha256": sha256_file(decisions_path),
        "source_locks": {
            str(source_path.relative_to(ROOT)): sha256_file(source_path),
            str(evaluation_source.relative_to(ROOT)): sha256_file(evaluation_source),
        },
        "input_hashes": {
            str(predictions_path.relative_to(ROOT)): sha256_file(predictions_path),
            str(training_path.relative_to(ROOT)): sha256_file(training_path),
            str(manifest_path.relative_to(ROOT)): sha256_file(manifest_path),
            str(hold_plan_path.relative_to(ROOT)): sha256_file(hold_plan_path),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--training", type=Path, default=DEFAULT_TRAINING)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--hold-plan", type=Path, default=DEFAULT_HOLD_PLAN)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--decisions", type=Path, default=DEFAULT_DECISIONS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    report = freeze_decision_contract(
        predictions_path=args.predictions.resolve(), training_path=args.training.resolve(),
        manifest_path=args.manifest.resolve(), hold_plan_path=args.hold_plan.resolve(),
        db_path=args.db.resolve(), decisions_path=args.decisions.resolve(),
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "status": report["status"], "n_scored_items": report["n_scored_items"],
        "decision_counts_by_model": report["decision_counts_by_model"],
        "report": str(args.report),
    }, indent=2))


if __name__ == "__main__":
    main()
