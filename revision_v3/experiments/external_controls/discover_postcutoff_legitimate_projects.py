"""Collect score-blind public provenance leads across the post-cutoff discovery pool.

This is a research-discovery pass, not a labeling or model-scoring pass.  It queries the
same restricted public metadata fields used by the frozen review worklists, but applies
them to every candidate unseen delegate address.  The resulting names and source matches
are leads for an investigator to connect to official project documentation; they are not
treated as evidence that a contract is benign.

Usage:
    python3 revision_v3/experiments/external_controls/discover_postcutoff_legitimate_projects.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter

import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "revision_v3", "experiments", "temporal_v2"))
import enrich_postcutoff_provenance as provenance  # noqa: E402

INPUT = os.path.join(
    REPO_ROOT, "revision_v3", "results", "postcutoff_snapshot", "ethereum_candidates.csv.gz"
)
BASE = os.path.join(REPO_ROOT, "revision_v3", "results", "legitimate_project_discovery")
WORKLIST = os.path.join(BASE, "postcutoff_discovery_worklist.csv")
CACHE = os.path.join(BASE, "postcutoff_discovery_public_provenance_cache.jsonl")
EVIDENCE = os.path.join(BASE, "postcutoff_discovery_public_provenance_evidence.csv")
REPORT = os.path.join(BASE, "postcutoff_discovery_public_provenance_report.json")


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_worklist(candidates: pd.DataFrame) -> pd.DataFrame:
    required = {
        "delegate_address",
        "first_tx_hash",
        "first_block",
        "first_timestamp_unix",
        "historical_bytecode_sha256",
        "postcutoff_exact_runtime_family",
        "is_candidate_unseen_family",
    }
    if missing := required - set(candidates.columns):
        raise ValueError(f"candidate table missing fields: {sorted(missing)}")
    unseen = candidates.loc[candidates["is_candidate_unseen_family"].eq(True)].copy()  # noqa: E712
    unseen["delegate_address"] = unseen["delegate_address"].astype(str).str.lower()
    unseen = unseen.sort_values(
        ["first_block", "delegate_address"], kind="mergesort"
    ).drop_duplicates("delegate_address", keep="first")
    rows = []
    for index, row in enumerate(unseen.itertuples(index=False), start=1):
        address = str(row.delegate_address).lower()
        tx_hash = str(row.first_tx_hash).lower()
        rows.append(
            {
                "item_id": f"DISC-{index:04d}",
                "delegate_address": address,
                "delegate_explorer_url": f"https://eth.blockscout.com/address/{address}",
                "authorization_tx_explorer_url": f"https://eth.blockscout.com/tx/{tx_hash}",
                "first_tx_hash": tx_hash,
                "first_block": int(row.first_block),
                "first_timestamp_unix": int(row.first_timestamp_unix),
                "historical_bytecode_sha256": str(row.historical_bytecode_sha256),
                "postcutoff_exact_runtime_family": str(row.postcutoff_exact_runtime_family),
            }
        )
    worklist = pd.DataFrame(rows)
    if worklist.empty:
        raise ValueError("no unseen post-cutoff delegate candidates found")
    if worklist["delegate_address"].duplicated().any():
        raise ValueError("discovery worklist contains duplicate delegate addresses")
    return worklist


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay-seconds", type=float, default=0.05)
    parser.add_argument("--max-items", type=int)
    parser.add_argument("--retry-errors", action="store_true")
    args = parser.parse_args()

    os.makedirs(BASE, exist_ok=True)
    worklist = build_worklist(pd.read_csv(INPUT))
    worklist.to_csv(WORKLIST, index=False, lineterminator="\n")
    worklist_hash = sha256_file(WORKLIST)
    records = provenance.collect_evidence(
        worklist,
        worklist_sha256=worklist_hash,
        cache_path=CACHE,
        delay_seconds=args.delay_seconds,
        max_items=args.max_items,
        retry_errors=args.retry_errors,
    )
    evidence = provenance.build_evidence_table(worklist, records)
    evidence.to_csv(EVIDENCE, index=False, lineterminator="\n")

    expected = len(worklist) * len(provenance.PROVIDERS)
    errors = sum(record.get("retrieval_status") == "ERROR" for record in records.values())
    named = evidence["candidate_name_signals"].fillna("").ne("")
    report = {
        "status": (
            "COMPLETE_SCORE_BLIND_PROJECT_DISCOVERY"
            if len(records) == expected and errors == 0
            else "INCOMPLETE_SCORE_BLIND_PROJECT_DISCOVERY"
        ),
        "n_candidate_unseen_delegate_addresses": len(worklist),
        "n_expected_provider_requests": expected,
        "n_cached_provider_requests": len(records),
        "n_request_errors": errors,
        "n_items_with_name_signals": int(named.sum()),
        "n_items_without_name_signals": int((~named).sum()),
        "name_signal_counts": dict(
            sorted(
                Counter(
                    name.strip()
                    for value in evidence.loc[named, "candidate_name_signals"]
                    for name in str(value).split(";")
                    if name.strip()
                ).items(),
                key=lambda item: (-item[1], item[0]),
            )
        ),
        "input_sha256": sha256_file(INPUT),
        "worklist_sha256": worklist_hash,
        "cache_sha256": sha256_file(CACHE),
        "evidence_sha256": sha256_file(EVIDENCE),
        "collector_sha256": sha256_file(__file__),
        "claim_boundary": (
            "Names and source-verification metadata are investigator leads only. A project is "
            "eligible for the external legitimate-control registry only after official ownership, "
            "deployment, audit or production status, and benchmark non-overlap are independently checked."
        ),
    }
    with open(REPORT, "w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "COMPLETE_SCORE_BLIND_PROJECT_DISCOVERY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
