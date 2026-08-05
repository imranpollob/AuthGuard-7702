"""Fail-closed project-family provenance gate for post-cutoff evaluation.

Exact-runtime deduplication is not a project-family hold.  This script creates a score-blind
audit template and validates the completed audit against the frozen review manifest and the
canonical family registry.  Its output is a machine-readable retraining holdout plan; it does
not infer provenance or score a model.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os

import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
V3 = os.path.join(REPO_ROOT, "revision_v3")
RESULTS_DIR = os.path.join(V3, "results", "postcutoff_snapshot")
MANIFEST_PATH = os.path.join(RESULTS_DIR, "postcutoff_review_manifest.csv")
AUDIT_PATH = os.path.join(RESULTS_DIR, "postcutoff_project_family_audit.csv")
PLAN_PATH = os.path.join(RESULTS_DIR, "postcutoff_family_holdout_plan.json")
CANONICAL_PATH = os.path.join(REPO_ROOT, "revision_v2", "data", "authguardbench_7702_v2.csv.gz")

AUDIT_COLUMNS = (
    "item_id",
    "postcutoff_project_family_id",
    "provenance_status",
    "evidence_reference",
    "evidence_notes",
    "related_canonical_family_ids",
    "related_control_projects",
    "auditor_id",
    "exclusion_reason",
)
ALLOWED_STATUS = {"CONFIRMED", "CONSERVATIVE_CLUSTER", "UNRESOLVED", "EXCLUDED"}


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _text(value) -> str:
    return "" if pd.isna(value) else str(value).strip()


def _split_ids(value) -> list[str]:
    text = _text(value)
    if not text or text.upper() == "NONE":
        return []
    return sorted({part.strip() for part in text.replace(";", ",").split(",") if part.strip()})


def build_audit_template(manifest: pd.DataFrame) -> pd.DataFrame:
    if "item_id" not in manifest or manifest["item_id"].duplicated().any():
        raise ValueError("manifest must contain unique item_id values")
    return pd.DataFrame([{
        "item_id": item_id,
        "postcutoff_project_family_id": "",
        "provenance_status": "UNRESOLVED",
        "evidence_reference": "",
        "evidence_notes": "",
        "related_canonical_family_ids": "",
        "related_control_projects": "",
        "auditor_id": "",
        "exclusion_reason": "",
    } for item_id in sorted(manifest["item_id"].astype(str))], columns=AUDIT_COLUMNS)


def validate_project_family_audit(
    manifest: pd.DataFrame,
    audit: pd.DataFrame,
    canonical_family_ids: set[str],
) -> dict:
    missing = set(AUDIT_COLUMNS) - set(audit.columns)
    if missing:
        raise ValueError(f"project-family audit is missing columns: {sorted(missing)}")
    if manifest["item_id"].duplicated().any() or audit["item_id"].duplicated().any():
        raise ValueError("manifest and audit item_id values must each be unique")
    manifest_ids = set(manifest["item_id"].astype(str))
    audit_ids = set(audit["item_id"].astype(str))
    if manifest_ids != audit_ids:
        raise ValueError(
            "audit/manifest item mismatch: "
            f"missing={sorted(manifest_ids - audit_ids)[:5]}, "
            f"extra={sorted(audit_ids - manifest_ids)[:5]}"
        )

    errors: list[str] = []
    projects: dict[str, dict] = {}
    excluded: list[str] = []
    for row in audit.sort_values("item_id").to_dict("records"):
        item_id = _text(row["item_id"])
        status = _text(row["provenance_status"]).upper()
        if status not in ALLOWED_STATUS:
            errors.append(f"{item_id}: invalid provenance_status {status!r}")
            continue
        if status == "UNRESOLVED":
            errors.append(f"{item_id}: project-family provenance remains UNRESOLVED")
            continue
        if not _text(row["auditor_id"]):
            errors.append(f"{item_id}: auditor_id is required")
        if status == "EXCLUDED":
            if not _text(row["exclusion_reason"]):
                errors.append(f"{item_id}: EXCLUDED requires exclusion_reason")
            excluded.append(item_id)
            continue

        project_id = _text(row["postcutoff_project_family_id"])
        evidence = _text(row["evidence_reference"])
        if not project_id:
            errors.append(f"{item_id}: CONFIRMED requires postcutoff_project_family_id")
            continue
        if not evidence:
            errors.append(f"{item_id}: terminal project cluster requires evidence_reference")
        if status == "CONSERVATIVE_CLUSTER" and "NO_BRAND_OWNERSHIP_CLAIM" not in _text(
            row["evidence_notes"]
        ):
            errors.append(
                f"{item_id}: CONSERVATIVE_CLUSTER must state NO_BRAND_OWNERSHIP_CLAIM"
            )
        related = _split_ids(row["related_canonical_family_ids"])
        unknown = sorted(set(related) - canonical_family_ids)
        if unknown:
            errors.append(f"{item_id}: unknown canonical family IDs {unknown}")
        controls = _split_ids(row["related_control_projects"])
        project = projects.setdefault(project_id, {
            "item_ids": [],
            "canonical_family_ids_to_hold_out": set(),
            "control_projects_to_hold_out": set(),
            "evidence_references": set(),
        })
        project["item_ids"].append(item_id)
        project["canonical_family_ids_to_hold_out"].update(related)
        project["control_projects_to_hold_out"].update(controls)
        project["evidence_references"].add(evidence)

    if errors:
        raise ValueError("project-family audit is not ready:\n- " + "\n- ".join(errors))
    if not projects:
        raise ValueError("project-family audit has no CONFIRMED items")

    serialized = {}
    for project_id, record in sorted(projects.items()):
        serialized[project_id] = {
            key: sorted(value) for key, value in record.items()
        }
    return {
        "status": "READY_FOR_PROJECT_FAMILY_RETRAINING_HOLDS",
        "n_manifest_items": len(manifest_ids),
        "n_confirmed_items": int(
            audit["provenance_status"].astype(str).str.upper().eq("CONFIRMED").sum()
        ),
        "n_conservative_cluster_items": int(
            audit["provenance_status"].astype(str).str.upper().eq(
                "CONSERVATIVE_CLUSTER"
            ).sum()
        ),
        "n_excluded_items": len(excluded),
        "n_postcutoff_project_families": len(serialized),
        "excluded_item_ids": sorted(excluded),
        "project_family_holds": serialized,
        "claim_boundary": (
            "This validates audit completeness and materializes holds; it does not convert "
            "conservative anonymous linkage clusters into brand attribution. Retraining must "
            "consume every listed canonical-family and control-project hold before scoring."
        ),
    }


def summarize_project_family_audit_progress(
    manifest: pd.DataFrame,
    audit: pd.DataFrame,
    canonical_family_ids: set[str],
) -> dict:
    """Validate completed rows without weakening the fail-closed final gate."""
    missing = set(AUDIT_COLUMNS) - set(audit.columns)
    if missing:
        raise ValueError(f"project-family audit is missing columns: {sorted(missing)}")
    if manifest["item_id"].duplicated().any() or audit["item_id"].duplicated().any():
        raise ValueError("manifest and audit item_id values must each be unique")
    manifest_ids = set(manifest["item_id"].astype(str))
    audit_ids = set(audit["item_id"].astype(str))
    if manifest_ids != audit_ids:
        raise ValueError("audit/manifest item mismatch")

    status_counts: dict[str, int] = {}
    errors = []
    confirmed_projects = set()
    for row in audit.to_dict("records"):
        item_id = _text(row["item_id"])
        status = _text(row["provenance_status"]).upper()
        status_counts[status] = status_counts.get(status, 0) + 1
        if status not in ALLOWED_STATUS:
            errors.append(f"{item_id}: invalid provenance_status {status!r}")
            continue
        if status == "UNRESOLVED":
            continue
        if not _text(row["auditor_id"]):
            errors.append(f"{item_id}: terminal row requires auditor_id")
        if status == "EXCLUDED":
            if not _text(row["exclusion_reason"]):
                errors.append(f"{item_id}: EXCLUDED requires exclusion_reason")
            continue
        project_id = _text(row["postcutoff_project_family_id"])
        if not project_id or not _text(row["evidence_reference"]):
            errors.append(f"{item_id}: terminal project cluster requires project ID and evidence")
        else:
            confirmed_projects.add(project_id)
        if status == "CONSERVATIVE_CLUSTER" and "NO_BRAND_OWNERSHIP_CLAIM" not in _text(
            row["evidence_notes"]
        ):
            errors.append(
                f"{item_id}: CONSERVATIVE_CLUSTER must state NO_BRAND_OWNERSHIP_CLAIM"
            )
        unknown = sorted(set(_split_ids(row["related_canonical_family_ids"])) - canonical_family_ids)
        if unknown:
            errors.append(f"{item_id}: unknown canonical family IDs {unknown}")
    if errors:
        raise ValueError("project-family progress contains invalid terminal rows:\n- " + "\n- ".join(errors))
    unresolved = status_counts.get("UNRESOLVED", 0)
    return {
        "status": "COMPLETE" if unresolved == 0 else "INCOMPLETE_PROJECT_FAMILY_AUDIT",
        "n_manifest_items": len(manifest_ids),
        "status_counts": dict(sorted(status_counts.items())),
        "n_terminal_items": len(manifest_ids) - unresolved,
        "n_confirmed_project_families": len(confirmed_projects),
        "confirmed_project_family_ids": sorted(confirmed_projects),
        "claim_boundary": (
            "This progress report validates only completed rows. UNRESOLVED rows still fail the "
            "final project-family gate and cannot be scored."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default=MANIFEST_PATH)
    parser.add_argument("--audit", default=AUDIT_PATH)
    parser.add_argument("--plan", default=PLAN_PATH)
    parser.add_argument("--init-template", action="store_true")
    parser.add_argument("--progress-only", action="store_true")
    args = parser.parse_args()

    manifest = pd.read_csv(args.manifest)
    if args.init_template:
        if os.path.exists(args.audit):
            raise FileExistsError(f"refusing to overwrite existing audit: {args.audit}")
        build_audit_template(manifest).to_csv(args.audit, index=False, lineterminator="\n")
        print(f"wrote unresolved score-blind audit template: {args.audit}")
        return 0

    audit = pd.read_csv(args.audit, keep_default_na=False)
    canonical_ids = set(pd.read_csv(CANONICAL_PATH, usecols=["family_id"])["family_id"].astype(str))
    report = (
        summarize_project_family_audit_progress(manifest, audit, canonical_ids)
        if args.progress_only else
        validate_project_family_audit(manifest, audit, canonical_ids)
    )
    report.update({
        "manifest_sha256": _sha256_file(args.manifest),
        "audit_sha256": _sha256_file(args.audit),
        "canonical_dataset_sha256": _sha256_file(CANONICAL_PATH),
        "validator_sha256": _sha256_file(__file__),
    })
    with open(args.plan, "w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
