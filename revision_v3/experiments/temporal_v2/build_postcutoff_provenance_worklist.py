"""Build a score-blind research worklist for the post-cutoff project-family audit.

The output supplies reproducible lookup leads, not project-family conclusions.  A named
auditor must still inspect the evidence and fill ``postcutoff_project_family_audit.csv``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os

import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
BASE = os.path.join(REPO_ROOT, "revision_v3", "results", "postcutoff_snapshot")
DEFAULT_SNAPSHOT = os.path.join(BASE, "ethereum_candidates.csv.gz")
DEFAULT_SNAPSHOT_REPORT = os.path.join(BASE, "ethereum_snapshot_report.json")
DEFAULT_MANIFEST = os.path.join(BASE, "postcutoff_review_manifest.csv")
DEFAULT_SAMPLE_LOCK = os.path.join(BASE, "postcutoff_review_lock.json")
DEFAULT_OUTPUT = os.path.join(BASE, "postcutoff_project_family_worklist.csv")
DEFAULT_REPORT = os.path.join(BASE, "postcutoff_project_family_worklist_report.json")

FORBIDDEN_MARKERS = ("label", "score", "prediction", "decision", "reviewer", "adjudicat")


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


def build_worklist(snapshot: pd.DataFrame, manifest: pd.DataFrame) -> pd.DataFrame:
    forbidden = sorted(
        column for column in set(snapshot.columns) | set(manifest.columns)
        if any(marker in column.lower() for marker in FORBIDDEN_MARKERS)
    )
    if forbidden:
        raise ValueError(
            "provenance worklist refuses label/model/review columns: " + ", ".join(forbidden)
        )
    required_snapshot = {
        "delegate_address", "authority_address", "first_tx_hash", "first_block",
        "first_timestamp_unix", "last_block", "last_timestamp_unix",
        "authorization_count", "historical_code_bytes", "historical_bytecode_sha256",
        "postcutoff_exact_runtime_family", "matched_historical_family",
        "best_historical_family_similarity", "runtime_changed_since_first_authorization",
    }
    required_manifest = {"item_id", "address", "bytecode_sha256", "family_id"}
    missing = (required_snapshot - set(snapshot.columns)) | (
        required_manifest - set(manifest.columns)
    )
    if missing:
        raise ValueError(f"provenance inputs are missing fields: {sorted(missing)}")
    if manifest["item_id"].duplicated().any() or manifest["address"].duplicated().any():
        raise ValueError("review manifest item IDs and addresses must be unique")

    snapshot = snapshot.copy()
    snapshot["delegate_address"] = snapshot["delegate_address"].astype(str).str.lower()
    manifest = manifest.copy()
    manifest["address"] = manifest["address"].astype(str).str.lower()
    grouped = snapshot.groupby("postcutoff_exact_runtime_family", dropna=False)
    peers = grouped["delegate_address"].agg(
        lambda values: ";".join(sorted(set(str(value).lower() for value in values)))
    )
    peer_counts = grouped["delegate_address"].nunique()
    # Restrict the manifest side to locked identity fields. Other duplicated provenance
    # columns (authority, first transaction, etc.) come from the hash-verified snapshot.
    manifest_identity = manifest[["item_id", "address", "bytecode_sha256", "family_id"]]
    selected = manifest_identity.merge(
        snapshot,
        left_on="address",
        right_on="delegate_address",
        how="left",
        validate="one_to_one",
    )
    if selected["delegate_address"].isna().any():
        raise ValueError("every review item must match one authoritative snapshot address")
    if not selected["bytecode_sha256"].str.lower().eq(
        selected["historical_bytecode_sha256"].str.lower()
    ).all():
        raise ValueError("review-manifest bytecode hash differs from the snapshot")
    if not selected["family_id"].astype(str).eq(
        selected["postcutoff_exact_runtime_family"].astype(str)
    ).all():
        raise ValueError("review-manifest exact-runtime family differs from the snapshot")

    selected["exact_runtime_peer_count"] = selected[
        "postcutoff_exact_runtime_family"
    ].map(peer_counts).astype(int)
    selected["exact_runtime_peer_addresses"] = selected[
        "postcutoff_exact_runtime_family"
    ].map(peers)
    selected["delegate_explorer_url"] = (
        "https://etherscan.io/address/" + selected["delegate_address"]
    )
    selected["authority_explorer_url"] = (
        "https://etherscan.io/address/" + selected["authority_address"].astype(str).str.lower()
    )
    selected["authorization_tx_explorer_url"] = (
        "https://etherscan.io/tx/" + selected["first_tx_hash"].astype(str).str.lower()
    )
    selected["first_timestamp_utc"] = pd.to_datetime(
        selected["first_timestamp_unix"], unit="s", utc=True
    ).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    selected["last_timestamp_utc"] = pd.to_datetime(
        selected["last_timestamp_unix"], unit="s", utc=True
    ).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    selected["audit_instruction"] = (
        "Research project ownership and related deployments; do not infer project family "
        "from exact-runtime similarity alone. Enter conclusions only in the separate audit CSV."
    )
    columns = [
        "item_id", "delegate_address", "delegate_explorer_url", "authority_address",
        "authority_explorer_url", "first_tx_hash", "authorization_tx_explorer_url",
        "first_block", "first_timestamp_utc", "last_block", "last_timestamp_utc",
        "authorization_count", "historical_code_bytes", "historical_bytecode_sha256",
        "postcutoff_exact_runtime_family", "exact_runtime_peer_count",
        "exact_runtime_peer_addresses", "matched_historical_family",
        "best_historical_family_similarity", "runtime_changed_since_first_authorization",
        "audit_instruction",
    ]
    return selected[columns].sort_values("item_id").reset_index(drop=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", default=DEFAULT_SNAPSHOT)
    parser.add_argument("--snapshot-report", default=DEFAULT_SNAPSHOT_REPORT)
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--sample-lock", default=DEFAULT_SAMPLE_LOCK)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--report", default=DEFAULT_REPORT)
    args = parser.parse_args()

    snapshot_report = _json(args.snapshot_report)
    sample_lock = _json(args.sample_lock)
    if snapshot_report.get("snapshot_sha256") != sha256_file(args.snapshot):
        raise ValueError("snapshot hash does not match its authoritative report")
    if sample_lock.get("snapshot_sha256") != sha256_file(args.snapshot):
        raise ValueError("sample lock targets a different snapshot")
    if sample_lock.get("manifest_sha256") != sha256_file(args.manifest):
        raise ValueError("sample lock targets a different review manifest")

    worklist = build_worklist(pd.read_csv(args.snapshot), pd.read_csv(args.manifest))
    worklist.to_csv(args.output, index=False, lineterminator="\n")
    report = {
        "status": "SCORE_BLIND_PROVENANCE_WORKLIST_COMPLETE",
        "n_items": len(worklist),
        "n_exact_runtime_families": int(worklist["postcutoff_exact_runtime_family"].nunique()),
        "n_items_with_exact_runtime_peers": int((worklist["exact_runtime_peer_count"] > 1).sum()),
        "snapshot_sha256": sha256_file(args.snapshot),
        "manifest_sha256": sha256_file(args.manifest),
        "worklist_sha256": sha256_file(args.output),
        "builder_sha256": sha256_file(__file__),
        "claim_boundary": (
            "Links, hashes, and exact-runtime peers are research leads only. This artifact "
            "does not establish project ownership, family independence, or a security label."
        ),
    }
    with open(args.report, "w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
