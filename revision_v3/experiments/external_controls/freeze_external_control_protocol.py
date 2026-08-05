"""Preregister the external legitimate-control analysis before any model scoring."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone

import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
V3 = os.path.join(REPO_ROOT, "revision_v3")
REGISTRY = os.path.join(V3, "external_controls", "final_new_legitimate_projects.csv")
REGISTRY_REPORT = os.path.join(
    V3, "external_controls", "final_new_legitimate_projects_report.json"
)
BYTECODE_DIR = os.path.join(V3, "external_controls", "final_bytecode_cache")
PRIMARY_PROTOCOL = os.path.join(V3, "protocols", "final_evaluation_preregistration_v1.json")
OUTPUT = os.path.join(V3, "protocols", "external_legitimate_control_protocol_v1.json")
ANNOTATION_DB = os.path.join(V3, "annotation_app", "annotation.db")
POSTCUTOFF_TRAINING = os.path.join(
    V3, "results", "postcutoff_retraining", "postcutoff_training_manifest.json"
)
EXTERNAL_SCORES = os.path.join(V3, "results", "external_legitimate_controls_final")


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative(path: str) -> str:
    return os.path.relpath(path, REPO_ROOT)


def assert_no_postcutoff_labels_or_scores() -> dict:
    connection = sqlite3.connect(ANNOTATION_DB)
    n_annotations = connection.execute(
        "SELECT COUNT(*) FROM annotations a JOIN items i ON i.item_id=a.item_id "
        "WHERE i.sample_set='postcutoff'"
    ).fetchone()[0]
    connection.close()
    if n_annotations:
        raise ValueError("post-cutoff human labels exist; external protocol freeze is too late")
    if os.path.exists(POSTCUTOFF_TRAINING):
        raise FileExistsError("post-cutoff model scoring already started")
    if os.path.exists(EXTERNAL_SCORES):
        raise FileExistsError("external legitimate-control scores already exist")
    return {
        "n_postcutoff_annotation_rows": 0,
        "postcutoff_training_manifest_exists": False,
        "external_score_directory_exists": False,
    }


def main() -> int:
    if os.path.exists(OUTPUT):
        raise FileExistsError("external legitimate-control protocol is already frozen")
    score_state = assert_no_postcutoff_labels_or_scores()
    registry = pd.read_csv(REGISTRY)
    eligible = registry.loc[registry["new_project_endpoint_eligible"].eq(True)]  # noqa: E712
    used = eligible.loc[
        eligible["actual_use_status"].eq("OBSERVED_IN_POSTCUTOFF_AUTHORIZATION_WINDOW")
    ]
    canonical_unseen = eligible.loc[eligible["canonical_unseen_at_0_85"].eq(True)]  # noqa: E712
    independent = eligible.loc[
        eligible["independent_lineage_endpoint_eligible"].eq(True)  # noqa: E712
    ]
    excluded = registry.loc[registry["new_project_endpoint_eligible"].eq(False)]  # noqa: E712
    if set(eligible["project"]) != {"Tangem", "Startale", "Rainbow"}:
        raise ValueError("unexpected new-project control population")
    if set(used["project"]) != {"Tangem", "Rainbow"}:
        raise ValueError("unexpected observed-use stratum")
    if set(canonical_unseen["project"]) != {"Tangem", "Startale"}:
        raise ValueError("unexpected canonical-unseen stratum")
    if set(independent["project"]) != {"Tangem"}:
        raise ValueError("unexpected independent-lineage stratum")

    bytecode_files = sorted(
        os.path.join(BYTECODE_DIR, name)
        for name in os.listdir(BYTECODE_DIR)
        if name.endswith(".hex")
    )
    locked_sources = [
        REGISTRY,
        REGISTRY_REPORT,
        *bytecode_files,
        PRIMARY_PROTOCOL,
        os.path.join(
            V3,
            "experiments",
            "external_controls",
            "freeze_final_legitimate_projects.py",
        ),
        os.path.join(
            V3,
            "experiments",
            "external_controls",
            "freeze_external_control_protocol.py",
        ),
        os.path.join(
            V3,
            "experiments",
            "external_controls",
            "discover_postcutoff_legitimate_projects.py",
        ),
        os.path.join(
            V3,
            "results",
            "legitimate_project_discovery",
            "postcutoff_discovery_worklist.csv",
        ),
        os.path.join(
            V3,
            "results",
            "legitimate_project_discovery",
            "postcutoff_discovery_public_provenance_evidence.csv",
        ),
        os.path.join(
            V3,
            "results",
            "legitimate_project_discovery",
            "postcutoff_discovery_public_provenance_report.json",
        ),
    ]
    protocol = {
        "status": "EXTERNAL_LEGITIMATE_CONTROLS_PREREGISTERED_BEFORE_SCORING",
        "schema": "authguard-external-legitimate-control-protocol-1.0",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "score_and_label_state_at_freeze": score_state,
        "parent_confirmatory_protocol": {
            "path": relative(PRIMARY_PROTOCOL),
            "sha256": sha256_file(PRIMARY_PROTOCOL),
            "relationship": (
                "This protocol refines only the parent's descriptive external-control endpoint. "
                "It does not change the confirmatory population, model, estimand, or support rule."
            ),
        },
        "registry": {
            "path": relative(REGISTRY),
            "sha256": sha256_file(REGISTRY),
            "n_audited_candidates": len(registry),
            "n_new_project_controls": len(eligible),
        },
        "predeclared_strata": {
            "all_new_projects": {
                "projects": eligible["project"].tolist(),
                "n": len(eligible),
                "interpretation": "new project identity; runtime lineage may still be known",
            },
            "observed_use_new_projects": {
                "projects": used["project"].tolist(),
                "n": len(used),
                "interpretation": "at least one authorization in the frozen post-cutoff window",
            },
            "canonical_unseen_runtime_families": {
                "projects": canonical_unseen["project"].tolist(),
                "n": len(canonical_unseen),
                "interpretation": (
                    "exact runtime absent from v2 and best opcode-4-gram Jaccard below 0.85; "
                    "this is a leakage screen, not proof of genealogical independence"
                ),
            },
            "documented_independent_lineage_case_study": {
                "projects": independent["project"].tolist(),
                "n": len(independent),
                "interpretation": (
                    "official project documentation explicitly describes a custom implementation; "
                    "n=1 permits a case study only"
                ),
            },
            "known_project_or_lineage_diagnostics": {
                "projects": excluded["project"].tolist(),
                "n": len(excluded),
                "interpretation": (
                    "Porto and Rhinestone Nexus remain diagnostic rows and may not be counted as "
                    "new-project evidence"
                ),
            },
        },
        "frozen_models": [
            "dcrg_full",
            "dcrg_project_balanced",
            "dcrg_untyped_guards",
            "hist_ngram_xgb",
            "sequence",
        ],
        "principal_descriptive_model": {
            "model": "dcrg_project_balanced",
            "training_rule": (
                "total bounded-negative training weight 8 per eligible development-control "
                "project; none of the controls in this registry may enter training, validation, "
                "threshold fitting, calibration, or model selection"
            ),
            "threshold": "nominal 5% FPR threshold fitted only on held-out canonical fold 0",
        },
        "outputs": {
            "per_control": [
                "three-seed scores and seed mean for every frozen model",
                "validation-derived threshold and WARN or NO_MODEL_WARNING decision",
                "COMPLETE, PARTIAL, or UNKNOWN DCRG coverage",
                "DEFER decision and machine-readable reason",
                "project, runtime, use, audit, and lineage stratum fields from the registry",
            ],
            "aggregate": [
                "WARN, NO_MODEL_WARNING, and DEFER counts for all three new projects",
                "the same counts for the two observed-use projects",
                "the same counts for the two canonical-unseen runtime families",
            ],
            "diagnostic": (
                "Report Porto and Rhinestone Nexus individually, outside every new-project total."
            ),
        },
        "analysis_rules": [
            "Score every frozen row exactly once after all checkpoints and thresholds are frozen.",
            "Do not tune a threshold, feature, control weight, or presentation stratum on these outcomes.",
            "Do not pool chain deployments or authorization counts as independent samples.",
            "Do not compute AUPRC or AUROC on the all-legitimate control set.",
            "Do not use a significance or superiority claim from n=3 project controls.",
            "Report Startale as deployment-only unless a separately frozen authorization collector supplies use evidence.",
            "Report Rainbow as a known-Calibur-lineage project and never as unseen-runtime evidence.",
            "Treat audit status as provenance metadata, not a ground-truth safety label.",
        ],
        "success_criterion": (
            "Descriptive support for the operational proposal requires the project-balanced model "
            "to avoid model warnings on at least two of three new projects while preserving any "
            "coverage-triggered DEFER. This criterion cannot establish safety or population-level "
            "false-positive performance and is not a confirmatory hypothesis test."
        ),
        "source_locks": {relative(path): sha256_file(path) for path in locked_sources},
        "claim_boundary": (
            "These are provenance-backed bounded-negative controls. The study may report warning "
            "and defer behavior, but must not call any runtime safe, certified, benign by proof, or "
            "representative of all legitimate EIP-7702 projects."
        ),
    }
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w") as handle:
        json.dump(protocol, handle, indent=2, sort_keys=True)
    print(json.dumps({
        "status": protocol["status"],
        "output": relative(OUTPUT),
        "output_sha256": sha256_file(OUTPUT),
        "n_source_locks": len(locked_sources),
        "n_new_project_controls": len(eligible),
        "n_observed_use_controls": len(used),
        "n_canonical_unseen_controls": len(canonical_unseen),
        "n_independent_lineage_controls": len(independent),
        **score_state,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
