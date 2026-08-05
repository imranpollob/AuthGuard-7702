"""Freeze the confirmatory AuthGuard-7702 endpoints before post-cutoff human review."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone

import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
V3 = os.path.join(REPO_ROOT, "revision_v3")
POST = os.path.join(V3, "results", "postcutoff_snapshot")
RESERVE = os.path.join(V3, "results", "confirmatory_snapshot")
MANIFEST = os.path.join(POST, "postcutoff_review_manifest.csv")
SAMPLE_LOCK = os.path.join(POST, "postcutoff_review_lock.json")
RESERVE_MANIFEST = os.path.join(RESERVE, "confirmatory_review_manifest.csv")
RESERVE_LOCK = os.path.join(RESERVE, "confirmatory_review_lock.json")
ANNOTATION_DB = os.path.join(V3, "annotation_app", "annotation.db")
OUTPUT = os.path.join(V3, "protocols", "final_evaluation_preregistration_v1.json")
TRAINING_MANIFEST = os.path.join(V3, "results", "postcutoff_retraining", "postcutoff_training_manifest.json")
REVIEW_UNLOCK = os.path.join(POST, "postcutoff_review_unlock.json")


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative(path: str) -> str:
    return os.path.relpath(path, REPO_ROOT)


def assert_zero_postcutoff_annotations(expected_ids: set[str]) -> dict:
    connection = sqlite3.connect(ANNOTATION_DB)
    items = connection.execute(
        "SELECT item_id FROM items WHERE sample_set='postcutoff'"
    ).fetchall()
    annotated = connection.execute(
        "SELECT a.item_id FROM annotations a JOIN items i ON i.item_id=a.item_id "
        "WHERE i.sample_set='postcutoff'"
    ).fetchall()
    connection.close()
    db_ids = {str(row[0]) for row in items}
    if db_ids != expected_ids:
        raise ValueError("annotation DB post-cutoff population differs from the frozen manifest")
    if annotated:
        raise ValueError("post-cutoff annotations exist; preregistration is too late")
    return {"n_seeded_items": len(db_ids), "n_annotation_rows": 0}


def main() -> int:
    if os.path.exists(OUTPUT):
        raise FileExistsError("final evaluation protocol is already frozen")
    if os.path.exists(TRAINING_MANIFEST) or os.path.exists(REVIEW_UNLOCK):
        raise FileExistsError("post-cutoff scoring has already started; refusing late preregistration")

    primary = pd.read_csv(MANIFEST, usecols=["item_id", "family_id", "bytecode_sha256"])
    reserve = pd.read_csv(RESERVE_MANIFEST, usecols=["item_id", "family_id", "bytecode_sha256"])
    if len(primary) != 150 or len(reserve) != 150:
        raise ValueError("primary and reserve manifests must each contain 150 items")
    if set(primary["item_id"].astype(str)) & set(reserve["item_id"].astype(str)):
        raise ValueError("primary and reserve item IDs overlap")
    if set(primary["family_id"].astype(str)) & set(reserve["family_id"].astype(str)):
        raise ValueError("primary and reserve exact-runtime families overlap")
    label_state = assert_zero_postcutoff_annotations(set(primary["item_id"].astype(str)))

    locked_sources = [
        MANIFEST,
        SAMPLE_LOCK,
        RESERVE_MANIFEST,
        RESERVE_LOCK,
        os.path.join(REPO_ROOT, "revision_v2", "data", "authguardbench_7702_v2.csv.gz"),
        os.path.join(V3, "external_controls", "verified_legitimate_controls.csv"),
        os.path.join(V3, "src", "analysis", "delegation_context.py"),
        os.path.join(V3, "src", "analysis", "dcrg_feature_groups.py"),
        os.path.join(V3, "src", "evaluation", "bootstrap_v2.py"),
        os.path.join(V3, "src", "evaluation", "postcutoff_provenance.py"),
        os.path.join(V3, "experiments", "human_label_evaluation", "evaluate_against_human_labels.py"),
        os.path.join(V3, "experiments", "temporal_v2", "run_postcutoff_retraining.py"),
        os.path.join(V3, "experiments", "temporal_v2", "build_postcutoff_dependence_clusters.py"),
        os.path.join(V3, "annotation_app", "constants.py"),
        os.path.join(V3, "annotation_app", "agreement.py"),
        os.path.join(V3, "human_eval", "REVIEWER_GUIDE.md"),
    ]
    source_locks = {_relative(path): sha256_file(path) for path in locked_sources}
    protocol = {
        "status": "FINAL_EVALUATION_PREREGISTERED_BEFORE_POSTCUTOFF_HUMAN_LABELS",
        "schema": "authguard-final-evaluation-preregistration-1.0",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "human_label_state_at_freeze": label_state,
        "populations": {
            "development": (
                "Canonical corpus and separate 150-item Gold-Test provisional-label proxy; "
                "neither may provide confirmatory human-performance evidence."
            ),
            "primary_confirmatory": {
                "manifest": _relative(MANIFEST),
                "n_items": len(primary),
                "selection": "score-blind random sample over unseen exact-runtime families",
            },
            "replication_reserve": {
                "manifest": _relative(RESERVE_MANIFEST),
                "n_items": len(reserve),
                "use_rule": (
                    "Do not inspect labels or scores for method selection. Use only as a fully "
                    "reported replication or predeclared replacement after documenting why the "
                    "primary population could not be evaluated."
                ),
            },
        },
        "pre_scoring_gates": [
            "Complete score-blind project-family audit or document pre-label provenance exclusions.",
            "Hold every related canonical family and legitimate-control project out of every contributing checkpoint.",
            "Regenerate signer/deployer/project dependence clusters after the final audit.",
            "Retrain three fixed seeds and fit nominal 5% FPR thresholds only on held-out canonical fold 0.",
            "Freeze checkpoints and label-free predictions before the annotation app unlocks.",
        ],
        "models": {
            "dcrg_full": "primary guard-aware aggregate DCRG representation with XGBoost",
            "dcrg_untyped_guards": "type-erased guard ablation",
            "cfg_capability_only": "capability-only ablation",
            "dcrg_without_protocol_actors": "protocol-actor ablation",
            "hist_ngram_xgb": "225-bin normalized opcode histogram plus 512-bin hashed opcode 4-grams",
            "sequence": "learned chunk-attention opcode sequence plus dense structural branch",
            "dcrg_project_balanced": "full DCRG with total bounded-negative training weight 8 per eligible legitimate project",
            "dcrg_sequence_noisy_or": "fixed exploratory fusion; never a primary novelty claim",
        },
        "primary_endpoint": {
            "estimand": "mean-across-seeds AUPRC(dcrg_full) - AUPRC(dcrg_untyped_guards)",
            "population": "adjudicated UNSAFE and bounded-negative items among pre-label provenance-eligible primary items",
            "exclusions": "INDETERMINATE and NOT_BYTECODE_SCREENABLE remain reported but are excluded from binary metrics",
            "uncertainty": "two-sided 95% percentile interval from 10000 paired seed-aware dependence-cluster bootstrap replicates",
            "support_rule": "typed-guard contribution supported only if the interval lower bound is greater than zero",
        },
        "secondary_endpoints": [
            "AUPRC dcrg_full minus hist_ngram_xgb with the same paired dependence-cluster interval",
            "AUPRC dcrg_full minus learned sequence+dense baseline with the same paired dependence-cluster interval",
            "AUROC, Brier score, calibration error, prevalence, and class counts for every frozen model",
            "recall and observed FPR at the validation-derived nominal 5% FPR threshold, reported with no certification claim",
            "COMPLETE/PARTIAL analysis coverage and DEFER rate",
            "project-level warning and defer counts on wholly new legitimate projects for the frozen weight-8 variant",
        ],
        "multiplicity": (
            "Only the full-versus-untyped AUPRC contrast is confirmatory. All secondary and "
            "error-taxonomy analyses are descriptive with intervals and no unadjusted superiority claims."
        ),
        "annotation": {
            "reviewers": "two independent primary reviewers per item, blinded to all model scores and inherited labels",
            "adjudication": "exactly one adjudicator for every primary-label disagreement",
            "reported_agreement": "raw agreement, Cohen kappa when defined, class counts, disagreement count, and adjudication count",
            "missingness": "no partial release; every frozen item must have a final label, including explicit indeterminate outcomes",
        },
        "paper_decision_gate": {
            "method_paper": (
                "Use representation-superiority language only if the primary endpoint supports it; "
                "baseline superiority requires its own secondary interval to exclude zero."
            ),
            "measurement_paper": (
                "If the primary interval crosses zero, center the benchmark, coverage correction, "
                "label shift, false-warning analysis, and negative method findings."
            ),
        },
        "forbidden_claims": [
            "safe to authorize or certified low risk",
            "sound or complete EVM analysis",
            "learned graph neural network",
            "universal adversarial robustness",
            "production readiness or wallet integration",
            "first EIP-7702 detector",
        ],
        "source_locks": source_locks,
        "claim_boundary": (
            "AuthGuard-7702 is a bytecode-only warning/triage study at authorization time. It "
            "does not infer intent, prove exploitability or safety, or replace audit, simulation, "
            "reputation, allowlisting, or transaction-aware defenses."
        ),
    }
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w") as handle:
        json.dump(protocol, handle, indent=2, sort_keys=True)
    print(json.dumps({
        "status": protocol["status"],
        "output": _relative(OUTPUT),
        "output_sha256": sha256_file(OUTPUT),
        "n_source_locks": len(source_locks),
        **label_state,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
