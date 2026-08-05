#!/usr/bin/env python3
"""Fail-closed pre-review audit for the frozen post-cutoff human study.

This audit does not change the label taxonomy or evidence packets. It verifies that the
preregistered guide/constants remain byte-identical, the primary manifest is represented exactly
once in the annotation database, every item has two distinct primary assignments, no human
annotation exists, and no score/label key appears recursively in reviewer evidence. A separate
roster attestation is required before the report can say READY_FOR_INDEPENDENT_HUMAN_REVIEW.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB = ROOT / "revision_v3/annotation_app/annotation.db"
DEFAULT_MANIFEST = ROOT / "revision_v3/results/postcutoff_snapshot/postcutoff_review_manifest.csv"
DEFAULT_PREREG = ROOT / "revision_v3/protocols/final_evaluation_preregistration_v1.json"
DEFAULT_ROSTER = ROOT / "revision_v3/protocols/postcutoff_reviewer_roster.csv"
DEFAULT_OUTPUT = ROOT / "revision_v3/results/human_final/postcutoff_review_readiness.json"

FORBIDDEN_EVIDENCE_KEYS = {
    "label", "label_semantics", "label_source", "label_evidence_type", "label_strength",
    "authguard_score", "authguard_prediction", "raw_score", "calibrated_score", "model_score",
    "reviewer_judgment", "other_reviewer_labels", "is_false_positive", "is_false_negative",
    "dcrg_score", "dcrg_prediction", "source_rule_label", "llm_provisional_label",
    "human_final_label",
}
EXPECTED_PRIMARY_IDS = {"R1", "R2"}
EXPECTED_ADJUDICATOR_IDS = {"R3"}
TRUTHY_ATTESTATIONS = {"yes", "true", "1", "attested", "complete", "completed"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _read_json(path: Path) -> dict:
    with path.open() as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def _manifest_ids(path: Path) -> list[str]:
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    ids = [str(row.get("item_id") or "").strip() for row in rows]
    if not ids or any(not item_id for item_id in ids) or len(ids) != len(set(ids)):
        raise ValueError("post-cutoff manifest must contain nonempty unique item_id values")
    return ids


def _forbidden_key_paths(value: object, prefix: str = "$") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for raw_key, child in value.items():
            key = str(raw_key)
            child_path = f"{prefix}.{key}"
            if key.lower() in FORBIDDEN_EVIDENCE_KEYS:
                paths.append(child_path)
            paths.extend(_forbidden_key_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            paths.extend(_forbidden_key_paths(child, f"{prefix}[{index}]"))
    return paths


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in TRUTHY_ATTESTATIONS


def validate_roster(path: Path, guide_sha256: str) -> tuple[bool, list[str], list[dict]]:
    if not path.exists():
        return False, [f"missing reviewer roster: {path}"], []
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    issues: list[str] = []
    by_role: dict[str, set[str]] = defaultdict(set)
    stable_identities: list[str] = []
    required_columns = {
        "reviewer_id", "role", "stable_identity", "qualification_basis",
        "independence_attestation", "conflict_of_interest_attestation",
        "calibration_completed", "guide_sha256_acknowledged", "attested_at_utc",
    }
    if not rows:
        issues.append("reviewer roster has no rows")
        return False, issues, []
    missing_columns = required_columns - set(rows[0])
    if missing_columns:
        issues.append(f"reviewer roster missing columns: {sorted(missing_columns)}")
        return False, issues, rows
    for index, row in enumerate(rows, start=2):
        reviewer_id = str(row["reviewer_id"] or "").strip()
        role = str(row["role"] or "").strip().lower()
        identity = str(row["stable_identity"] or "").strip()
        if not reviewer_id or role not in {"primary", "adjudicator"}:
            issues.append(f"row {index}: invalid reviewer_id or role")
            continue
        by_role[role].add(reviewer_id)
        if not identity:
            issues.append(f"row {index}: stable identity is missing")
        else:
            stable_identities.append(identity.casefold())
        if len(str(row["qualification_basis"] or "").strip()) < 20:
            issues.append(f"row {index}: qualification basis is not substantive")
        for field in (
            "independence_attestation", "conflict_of_interest_attestation",
            "calibration_completed",
        ):
            if not _truthy(row[field]):
                issues.append(f"row {index}: {field} is not attested")
        if str(row["guide_sha256_acknowledged"] or "").strip() != guide_sha256:
            issues.append(f"row {index}: locked reviewer-guide hash was not acknowledged")
        if not str(row["attested_at_utc"] or "").strip():
            issues.append(f"row {index}: attestation time is missing")
    if by_role["primary"] != EXPECTED_PRIMARY_IDS:
        issues.append(f"primary roster must be exactly {sorted(EXPECTED_PRIMARY_IDS)}")
    if by_role["adjudicator"] != EXPECTED_ADJUDICATOR_IDS:
        issues.append(f"adjudicator roster must be exactly {sorted(EXPECTED_ADJUDICATOR_IDS)}")
    if len(stable_identities) != len(set(stable_identities)):
        issues.append("reviewer stable identities are not distinct")
    return not issues, issues, rows


def audit_review_readiness(
    *, db_path: Path, manifest_path: Path, prereg_path: Path, roster_path: Path,
) -> dict:
    prereg = _read_json(prereg_path)
    if prereg.get("status") != "FINAL_EVALUATION_PREREGISTERED_BEFORE_POSTCUTOFF_HUMAN_LABELS":
        raise ValueError("final evaluation preregistration has an invalid status")
    source_locks = prereg.get("source_locks") or {}
    locked_paths = {
        "reviewer_guide": ROOT / "revision_v3/human_eval/REVIEWER_GUIDE.md",
        "label_constants": ROOT / "revision_v3/annotation_app/constants.py",
    }
    current_hashes: dict[str, str] = {}
    for label, path in locked_paths.items():
        repository_relative = str(path.relative_to(ROOT))
        expected = source_locks.get(repository_relative)
        current = sha256_file(path)
        current_hashes[repository_relative] = current
        if not expected or current != expected:
            raise ValueError(f"locked {label} hash mismatch")

    manifest_ids = _manifest_ids(manifest_path)
    if len(manifest_ids) != 150:
        raise ValueError(f"expected 150 primary manifest items, observed {len(manifest_ids)}")
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        item_rows = connection.execute(
            "SELECT item_id, evidence_json FROM items WHERE sample_set='postcutoff' ORDER BY item_id"
        ).fetchall()
        db_ids = [str(row["item_id"]) for row in item_rows]
        if db_ids != sorted(manifest_ids):
            raise ValueError("annotation database post-cutoff IDs do not exactly match the manifest")
        annotation_count = int(connection.execute(
            "SELECT COUNT(*) FROM annotations a JOIN items i USING(item_id) "
            "WHERE i.sample_set='postcutoff'"
        ).fetchone()[0])
        if annotation_count != 0:
            raise ValueError("post-cutoff annotations already exist; pre-review audit is no longer valid")
        assignment_rows = connection.execute(
            "SELECT a.item_id, a.reviewer_id, a.is_adjudication, a.status "
            "FROM assignments a JOIN items i USING(item_id) "
            "WHERE i.sample_set='postcutoff' ORDER BY a.item_id, a.reviewer_id"
        ).fetchall()
    finally:
        connection.close()

    by_item: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for row in assignment_rows:
        by_item[str(row["item_id"])].append(row)
    for item_id in manifest_ids:
        rows = by_item.get(item_id, [])
        primary = {str(row["reviewer_id"]) for row in rows if not row["is_adjudication"]}
        adjudication = [row for row in rows if row["is_adjudication"]]
        statuses = {str(row["status"]) for row in rows}
        if primary != EXPECTED_PRIMARY_IDS or adjudication or statuses != {"pending"}:
            raise ValueError(
                f"{item_id}: expected pending R1/R2 primary assignments and no adjudicator"
            )

    forbidden_paths: list[dict[str, object]] = []
    evidence_hash = hashlib.sha256()
    for row in item_rows:
        raw = str(row["evidence_json"])
        evidence_hash.update(str(row["item_id"]).encode())
        evidence_hash.update(b"\0")
        evidence_hash.update(raw.encode())
        evidence_hash.update(b"\n")
        packet = json.loads(raw)
        paths = _forbidden_key_paths(packet)
        if paths:
            forbidden_paths.append({"item_id": row["item_id"], "paths": paths})
    if forbidden_paths:
        raise ValueError(f"forbidden score/label keys found in reviewer evidence: {forbidden_paths[:3]}")

    guide_path = locked_paths["reviewer_guide"]
    guide_sha = current_hashes[str(guide_path.relative_to(ROOT))]
    roster_ready, roster_issues, roster_rows = validate_roster(roster_path, guide_sha)
    return {
        "schema": "authguard-postcutoff-human-review-readiness-1.0",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": (
            "READY_FOR_INDEPENDENT_HUMAN_REVIEW"
            if roster_ready else "AWAITING_NAMED_REVIEWER_ATTESTATION"
        ),
        "claim_boundary": (
            "This attests pre-review blinding, assignments, and reviewer roster only. It does not "
            "supply labels, agreement, semantic validity, or model performance."
        ),
        "n_manifest_items": len(manifest_ids),
        "n_postcutoff_database_items": len(item_rows),
        "n_postcutoff_annotations": annotation_count,
        "n_primary_assignments": len(assignment_rows),
        "primary_reviewer_ids": sorted(EXPECTED_PRIMARY_IDS),
        "adjudicator_reviewer_ids": sorted(EXPECTED_ADJUDICATOR_IDS),
        "assignment_status_counts": dict(Counter(str(row["status"]) for row in assignment_rows)),
        "forbidden_evidence_key_occurrences": 0,
        "evidence_packets_aggregate_sha256": evidence_hash.hexdigest(),
        "roster_ready": roster_ready,
        "roster_issues": roster_issues,
        "n_roster_rows": len(roster_rows),
        "input_hashes": {
            _display_path(prereg_path): sha256_file(prereg_path),
            _display_path(manifest_path): sha256_file(manifest_path),
            _display_path(db_path): sha256_file(db_path),
            **current_hashes,
            **(
                {_display_path(roster_path): sha256_file(roster_path)}
                if roster_path.exists() else {}
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--prereg", type=Path, default=DEFAULT_PREREG)
    parser.add_argument("--roster", type=Path, default=DEFAULT_ROSTER)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = audit_review_readiness(
        db_path=args.db.resolve(), manifest_path=args.manifest.resolve(),
        prereg_path=args.prereg.resolve(), roster_path=args.roster.resolve(),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "status": report["status"], "n_items": report["n_manifest_items"],
        "n_annotations": report["n_postcutoff_annotations"],
        "roster_issues": report["roster_issues"], "output": str(args.output),
    }, indent=2))


if __name__ == "__main__":
    main()
