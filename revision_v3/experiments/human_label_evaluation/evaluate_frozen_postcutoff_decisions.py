#!/usr/bin/env python3
"""Descriptively evaluate the pre-label frozen post-cutoff decision contract."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
ALLOWED_LABELS = {
    "UNSAFE", "NO_CONCRETE_UNSAFE_BEHAVIOR_FOUND", "INDETERMINATE",
    "NOT_BYTECODE_SCREENABLE",
}
BINARY = {"UNSAFE": 1, "NO_CONCRETE_UNSAFE_BEHAVIOR_FOUND": 0}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _id_hash(values) -> str:
    return hashlib.sha256("\n".join(sorted(map(str, values))).encode()).hexdigest()


def _wilson_interval(successes: int, trials: int, z: float = 1.959963984540054) -> list[float] | None:
    """Return a two-sided 95% Wilson interval for a binomial proportion."""
    if trials <= 0:
        return None
    proportion = successes / trials
    denominator = 1.0 + (z * z / trials)
    center = (proportion + z * z / (2.0 * trials)) / denominator
    radius = z * math.sqrt(
        proportion * (1.0 - proportion) / trials + z * z / (4.0 * trials * trials)
    ) / denominator
    return [max(0.0, center - radius), min(1.0, center + radius)]


def _artifact_key(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def evaluate_decisions(
    *, release_path: Path, agreement_path: Path, manifest_path: Path, hold_plan_path: Path,
    decisions_path: Path, lock_path: Path,
) -> dict:
    lock = json.loads(lock_path.read_text())
    if lock.get("status") != "FROZEN_POSTCUTOFF_DECISION_CONTRACT_BEFORE_HUMAN_LABELS":
        raise ValueError("decision-contract lock has an invalid status")
    for relative, expected in lock.get("source_locks", {}).items():
        if sha256_file(ROOT / relative) != expected:
            raise ValueError(f"frozen decision-contract source hash mismatch: {relative}")
    if sha256_file(decisions_path) != lock.get("decisions_sha256"):
        raise ValueError("frozen decision artifact hash mismatch")
    supplied_inputs = {
        _artifact_key(manifest_path): manifest_path,
        _artifact_key(hold_plan_path): hold_plan_path,
    }
    for key, path in supplied_inputs.items():
        expected = lock.get("input_hashes", {}).get(key)
        if expected is None or sha256_file(path) != expected:
            raise ValueError(f"decision-contract input hash mismatch: {key}")
    manifest = pd.read_csv(manifest_path, usecols=["item_id"])
    if len(manifest) != 150 or manifest["item_id"].duplicated().any():
        raise ValueError("post-cutoff manifest is not the frozen 150-item population")
    hold_plan = json.loads(hold_plan_path.read_text())
    excluded = set(map(str, hold_plan.get("excluded_item_ids", [])))
    eligible = set(manifest["item_id"].astype(str)) - excluded
    release_rows = json.loads(release_path.read_text())
    if not isinstance(release_rows, list):
        raise ValueError("human release must be a list")
    release = pd.DataFrame(release_rows)
    required = {"item_id", "final_label", "n_primary_reviews", "resolution"}
    if missing := required - set(release.columns):
        raise ValueError(f"human release is missing columns: {sorted(missing)}")
    if set(release["item_id"].astype(str)) != set(manifest["item_id"].astype(str)):
        raise ValueError("human release does not exactly match the frozen manifest")
    if release["item_id"].duplicated().any() or len(release) != 150:
        raise ValueError("human release has duplicate or missing items")
    if unknown := set(release["final_label"].astype(str)) - ALLOWED_LABELS:
        raise ValueError(f"human release contains unknown labels: {sorted(unknown)}")
    if (pd.to_numeric(release["n_primary_reviews"], errors="coerce") != 2).any():
        raise ValueError("every post-cutoff item must have exactly two primary reviews")
    if not release["resolution"].isin({"unanimous", "adjudicated"}).all():
        raise ValueError("every disagreement must be adjudicated")
    agreement = json.loads(agreement_path.read_text())
    if agreement.get("sample_set") != "postcutoff":
        raise ValueError("agreement report sample_set mismatch")
    if agreement.get("status") != "COMPLETE_DUAL_REVIEW_AND_ADJUDICATION":
        raise ValueError("agreement/adjudication report is incomplete")
    if agreement.get("item_ids_sha256") != _id_hash(manifest["item_id"]):
        raise ValueError("agreement report is not bound to the frozen item IDs")
    if int(agreement.get("n_manifest_items", -1)) != 150:
        raise ValueError("agreement report manifest count mismatch")
    if int(agreement.get("n_exactly_dual_reviewed", -1)) != 150:
        raise ValueError("agreement report does not prove exactly two reviews per item")
    if int(agreement.get("n_pending_adjudications", -1)) != 0:
        raise ValueError("agreement report has pending adjudications")
    if int(agreement.get("n_primary_disagreements", -1)) != int(
        agreement.get("n_adjudicated_disagreements", -2)
    ):
        raise ValueError("agreement report has unresolved or multiply resolved disagreements")
    decisions = pd.read_csv(decisions_path)
    if set(decisions["sample_id"].astype(str)) != eligible:
        raise ValueError("decision artifact population mismatch")
    if decisions.duplicated(["sample_id", "model"]).any():
        raise ValueError("decision artifact contains duplicate item/model rows")
    expected_models = set(lock.get("models", []))
    if set(decisions["model"].astype(str)) != expected_models:
        raise ValueError("decision artifact model set differs from the frozen contract")
    if len(decisions) != len(eligible) * len(expected_models):
        raise ValueError("decision artifact cardinality differs from the frozen contract")
    allowed_decisions = {"WARN", "NO_MODEL_WARNING", "DEFER"}
    if unknown_decisions := set(decisions["consensus_decision"].astype(str)) - allowed_decisions:
        raise ValueError(f"decision artifact contains unknown outcomes: {sorted(unknown_decisions)}")
    scored_labels = release[release["item_id"].isin(eligible)].copy()
    scored_labels["binary_label"] = scored_labels["final_label"].map(BINARY)
    binary = scored_labels[scored_labels["binary_label"].notna()].copy()
    if binary["binary_label"].nunique() != 2:
        raise ValueError("decision evaluation requires both human binary classes")
    merged = decisions.merge(
        binary[["item_id", "binary_label"]], left_on="sample_id", right_on="item_id",
        how="inner", validate="many_to_one",
    )
    model_reports = {}
    for model, frame in merged.groupby("model", sort=True):
        y = frame["binary_label"].astype(int)
        decision = frame["consensus_decision"].astype(str)
        warn = decision == "WARN"
        no_warning = decision == "NO_MODEL_WARNING"
        defer = decision == "DEFER"
        positive = y == 1
        negative = y == 0
        tp = int((warn & positive).sum())
        fp = int((warn & negative).sum())
        n_positive = int(positive.sum())
        n_negative = int(negative.sum())
        n_warn = int(warn.sum())
        n_defer = int(defer.sum())
        n_no_warning = int(no_warning.sum())
        n_unsafe_no_warning = int((no_warning & positive).sum())
        model_reports[str(model)] = {
            "n_binary_items": int(len(frame)),
            "decision_counts_on_binary_items": dict(sorted(Counter(decision).items())),
            "warning_recall": float(tp / n_positive),
            "warning_recall_wilson_95ci": _wilson_interval(tp, n_positive),
            "warning_observed_fpr": float(fp / n_negative),
            "warning_observed_fpr_wilson_95ci": _wilson_interval(fp, n_negative),
            "warning_precision": float(tp / n_warn) if n_warn else None,
            "warning_precision_wilson_95ci": _wilson_interval(tp, n_warn),
            "defer_rate": float(n_defer / len(frame)),
            "defer_rate_wilson_95ci": _wilson_interval(n_defer, len(frame)),
            "n_no_model_warning": n_no_warning,
            "n_unsafe_within_no_model_warning": n_unsafe_no_warning,
            "unsafe_rate_within_no_model_warning": (
                float(n_unsafe_no_warning / n_no_warning) if n_no_warning else None
            ),
            "unsafe_rate_within_no_model_warning_wilson_95ci": _wilson_interval(
                n_unsafe_no_warning, n_no_warning
            ),
            "claim_boundary": "NO_MODEL_WARNING is a frozen operating outcome, not safety.",
        }
    return {
        "schema": "authguard-postcutoff-decision-evaluation-1.0",
        "status": "FROZEN_POSTCUTOFF_DECISION_CONTRACT_EVALUATED_ON_HUMAN_LABELS",
        "n_manifest_items": 150,
        "n_excluded_items": len(excluded),
        "n_scored_items": len(eligible),
        "n_binary_scored_items": int(len(binary)),
        "final_label_counts": dict(sorted(Counter(release["final_label"]).items())),
        "models": model_reports,
        "agreement": {
            "raw_agreement_rate": agreement.get("raw_agreement_rate"),
            "cohens_kappa": agreement.get("cohens_kappa"),
            "n_primary_disagreements": agreement.get("n_primary_disagreements"),
            "n_adjudicated_disagreements": agreement.get("n_adjudicated_disagreements"),
        },
        "input_hashes": {
            _artifact_key(release_path): sha256_file(release_path),
            _artifact_key(agreement_path): sha256_file(agreement_path),
            _artifact_key(decisions_path): sha256_file(decisions_path),
            _artifact_key(lock_path): sha256_file(lock_path),
        },
        "claim_boundary": (
            "All operating metrics are descriptive at a frozen validation-derived threshold. "
            "They do not certify safety or estimate deployment-wide prevalence."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("release", type=Path)
    parser.add_argument("--agreement", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=(
        ROOT / "revision_v3/results/postcutoff_snapshot/postcutoff_review_manifest.csv"
    ))
    parser.add_argument("--hold-plan", type=Path, default=(
        ROOT / "revision_v3/results/postcutoff_snapshot/postcutoff_family_holdout_plan.json"
    ))
    parser.add_argument("--decisions", type=Path, default=(
        ROOT / "revision_v3/results/postcutoff_retraining/postcutoff_consensus_decisions.csv.gz"
    ))
    parser.add_argument("--lock", type=Path, default=(
        ROOT / "revision_v3/results/postcutoff_retraining/postcutoff_decision_contract_lock.json"
    ))
    parser.add_argument("--output", type=Path, default=(
        ROOT / "revision_v3/results/human_final/postcutoff_decision_evaluation.json"
    ))
    args = parser.parse_args()
    report = evaluate_decisions(
        release_path=args.release.resolve(), agreement_path=args.agreement.resolve(),
        manifest_path=args.manifest.resolve(), hold_plan_path=args.hold_plan.resolve(),
        decisions_path=args.decisions.resolve(), lock_path=args.lock.resolve(),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
