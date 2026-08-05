#!/usr/bin/env python3
"""Build score-blind dependence clusters for the frozen post-cutoff review sample.

Exact-runtime sampling removes byte-identical duplicates but does not make observations
independent.  This script conservatively joins sampled items when they share a recovered
authorizing EOA, share an externally-owned deployer, or have the same independently confirmed
project-family ID.  Contract deployers are not used for linking because public CREATE2 factories
serve unrelated projects.

No labels or model scores are read.  Public address-kind responses are cached so the artifact can
be audited and reproduced without silently depending on mutable provider state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[3]
RESULTS_DIR = REPO_ROOT / "revision_v3" / "results" / "postcutoff_snapshot"
WORKLIST_PATH = RESULTS_DIR / "postcutoff_project_family_worklist.csv"
PROVENANCE_CACHE_PATH = RESULTS_DIR / "postcutoff_public_provenance_cache.jsonl"
AUDIT_PATH = RESULTS_DIR / "postcutoff_project_family_audit.csv"
CREATOR_CACHE_PATH = RESULTS_DIR / "postcutoff_creator_kind_cache.jsonl"
OUTPUT_PATH = RESULTS_DIR / "postcutoff_dependence_clusters.csv"
REPORT_PATH = RESULTS_DIR / "postcutoff_dependence_clusters_report.json"


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_address(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip().lower()
    return text if text.startswith("0x") and len(text) == 42 else ""


def load_delegate_creators(path: str | Path) -> dict[str, str]:
    creators: dict[str, str] = {}
    with open(path) as handle:
        for line in handle:
            row = json.loads(line)
            if row.get("provider") != "blockscout_address":
                continue
            creator = normalized_address(row.get("summary", {}).get("creator_address"))
            creators[str(row["item_id"])] = creator
    return creators


def load_creator_kind_cache(path: str | Path) -> dict[str, dict]:
    if not os.path.exists(path):
        return {}
    rows = {}
    with open(path) as handle:
        for line in handle:
            row = json.loads(line)
            rows[normalized_address(row.get("address"))] = row
    return {key: value for key, value in rows.items() if key}


def fetch_creator_kind(address: str, *, timeout: float = 20.0) -> dict:
    url = f"https://eth.blockscout.com/api/v2/addresses/{address}"
    request = urllib.request.Request(url, headers={"User-Agent": "AuthGuard-7702-research/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
            status = int(response.status)
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        return {
            "address": address,
            "provider_url": url,
            "retrieval_status": "ERROR",
            "error_type": type(exc).__name__,
            "is_contract": None,
        }
    return {
        "address": address,
        "provider_url": url,
        "retrieval_status": "COMPLETE",
        "http_status": status,
        "is_contract": payload.get("is_contract"),
        "name": payload.get("name"),
        "public_tags": payload.get("public_tags") or [],
    }


def refresh_creator_cache(addresses: set[str], cache_path: str | Path) -> dict[str, dict]:
    cached = load_creator_kind_cache(cache_path)
    for position, address in enumerate(sorted(addresses - set(cached)), 1):
        row = fetch_creator_kind(address)
        row["retrieved_at_utc"] = datetime.now(timezone.utc).isoformat()
        cached[address] = row
        if position % 20 == 0:
            print(f"[dependence] fetched creator kind {position}", flush=True)
        time.sleep(0.05)
    tmp = str(cache_path) + ".tmp"
    with open(tmp, "w") as handle:
        for address in sorted(cached):
            handle.write(json.dumps(cached[address], sort_keys=True) + "\n")
    os.replace(tmp, cache_path)
    return cached


class UnionFind:
    def __init__(self, values: list[str]):
        self.parent = {value: value for value in values}

    def find(self, value: str) -> str:
        parent = self.parent[value]
        if parent != value:
            self.parent[value] = self.find(parent)
        return self.parent[value]

    def union(self, left: str, right: str) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root == right_root:
            return
        keep, merge = sorted((left_root, right_root))
        self.parent[merge] = keep


def _union_groups(uf: UnionFind, groups: dict[str, list[str]]) -> set[str]:
    linked_keys = set()
    for key, item_ids in groups.items():
        unique = sorted(set(item_ids))
        if key and len(unique) > 1:
            linked_keys.add(key)
            for item_id in unique[1:]:
                uf.union(unique[0], item_id)
    return linked_keys


def build_dependence_clusters(
    worklist: pd.DataFrame,
    creators: dict[str, str],
    creator_kinds: dict[str, dict],
    audit: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, dict]:
    required = {"item_id", "authority_address"}
    if missing := required - set(worklist.columns):
        raise ValueError(f"worklist missing columns: {sorted(missing)}")
    if worklist["item_id"].duplicated().any():
        raise ValueError("worklist item_id values must be unique")
    item_ids = sorted(worklist["item_id"].astype(str))
    uf = UnionFind(item_ids)
    reasons: dict[str, set[str]] = defaultdict(set)

    authority_groups: dict[str, list[str]] = defaultdict(list)
    creator_groups: dict[str, list[str]] = defaultdict(list)
    for row in worklist.to_dict("records"):
        item_id = str(row["item_id"])
        authority_groups[normalized_address(row["authority_address"])].append(item_id)
        creator = creators.get(item_id, "")
        kind = creator_kinds.get(creator, {})
        if creator and kind.get("retrieval_status") == "COMPLETE" and kind.get("is_contract") is False:
            creator_groups[creator].append(item_id)

    for key in _union_groups(uf, authority_groups):
        reasons[key].add("SHARED_AUTHORITY_EOA")
    for key in _union_groups(uf, creator_groups):
        reasons[key].add("SHARED_DEPLOYER_EOA")

    confirmed_project_groups: dict[str, list[str]] = defaultdict(list)
    if audit is not None and len(audit):
        for row in audit.to_dict("records"):
            if str(row.get("provenance_status", "")).strip().upper() != "CONFIRMED":
                continue
            project_id = str(row.get("postcutoff_project_family_id", "")).strip()
            if project_id:
                confirmed_project_groups[project_id].append(str(row["item_id"]))
        for key in _union_groups(uf, confirmed_project_groups):
            reasons[key].add("CONFIRMED_PROJECT_FAMILY")

    components: dict[str, list[str]] = defaultdict(list)
    for item_id in item_ids:
        components[uf.find(item_id)].append(item_id)
    ordered_components = sorted((sorted(values) for values in components.values()), key=lambda x: x[0])
    cluster_for = {
        item_id: f"D{position:04d}"
        for position, values in enumerate(ordered_components, 1)
        for item_id in values
    }
    size_for = {item_id: len(values) for values in ordered_components for item_id in values}

    rows = []
    for row in worklist.sort_values("item_id").to_dict("records"):
        item_id = str(row["item_id"])
        creator = creators.get(item_id, "")
        kind = creator_kinds.get(creator, {})
        evidence = []
        authority = normalized_address(row["authority_address"])
        if len(set(authority_groups.get(authority, []))) > 1:
            evidence.append("SHARED_AUTHORITY_EOA")
        if len(set(creator_groups.get(creator, []))) > 1:
            evidence.append("SHARED_DEPLOYER_EOA")
        if audit is not None and len(audit):
            match = audit[audit["item_id"].astype(str) == item_id]
            if len(match) and str(match.iloc[0].get("provenance_status", "")).upper() == "CONFIRMED":
                project_id = str(match.iloc[0].get("postcutoff_project_family_id", "")).strip()
                if len(set(confirmed_project_groups.get(project_id, []))) > 1:
                    evidence.append("CONFIRMED_PROJECT_FAMILY")
        rows.append({
            "item_id": item_id,
            "dependence_cluster_id": cluster_for[item_id],
            "dependence_cluster_size": size_for[item_id],
            "authority_address": authority,
            "creator_address": creator,
            "creator_kind": (
                "CONTRACT" if kind.get("is_contract") is True else
                "EOA" if kind.get("is_contract") is False else "UNKNOWN"
            ),
            "linkage_evidence": ";".join(sorted(set(evidence))) or "SINGLETON_NO_MUST_LINK",
        })
    output = pd.DataFrame(rows)
    sizes = output.groupby("dependence_cluster_id").size()
    report = {
        "status": "SCORE_BLIND_DEPENDENCE_CLUSTERS_COMPLETE",
        "n_items": len(output),
        "n_dependence_clusters": int(len(sizes)),
        "n_multi_item_clusters": int((sizes > 1).sum()),
        "n_items_in_multi_item_clusters": int(sizes[sizes > 1].sum()),
        "max_cluster_size": int(sizes.max()),
        "creator_kind_counts": dict(sorted(Counter(output["creator_kind"]).items())),
        "linkage_evidence_counts": dict(sorted(Counter(output["linkage_evidence"]).items())),
        "claim_boundary": (
            "These are conservative statistical-dependence must-links, not security labels or "
            "complete project ownership. Shared contract factories are deliberately not linked. "
            "Final project-family audit and all required training holds remain separate gates."
        ),
    }
    return output, report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worklist", default=str(WORKLIST_PATH))
    parser.add_argument("--provenance-cache", default=str(PROVENANCE_CACHE_PATH))
    parser.add_argument("--audit", default=str(AUDIT_PATH))
    parser.add_argument("--creator-cache", default=str(CREATOR_CACHE_PATH))
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    parser.add_argument("--report", default=str(REPORT_PATH))
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    worklist = pd.read_csv(args.worklist)
    creators = load_delegate_creators(args.provenance_cache)
    creator_addresses = {value for value in creators.values() if value}
    if args.refresh:
        creator_kinds = refresh_creator_cache(creator_addresses, args.creator_cache)
    else:
        creator_kinds = load_creator_kind_cache(args.creator_cache)
    missing = sorted(creator_addresses - set(creator_kinds))
    incomplete = sorted(
        address for address in creator_addresses
        if creator_kinds.get(address, {}).get("retrieval_status") != "COMPLETE"
    )
    if missing or incomplete:
        raise RuntimeError(
            "creator-kind cache is incomplete; rerun with --refresh: "
            f"missing={missing[:5]}, incomplete={incomplete[:5]}"
        )
    audit = pd.read_csv(args.audit, keep_default_na=False) if os.path.exists(args.audit) else None
    output, report = build_dependence_clusters(worklist, creators, creator_kinds, audit)
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    output.to_csv(args.output, index=False, lineterminator="\n")
    report.update({
        "worklist_sha256": sha256_file(args.worklist),
        "provenance_cache_sha256": sha256_file(args.provenance_cache),
        "project_family_audit_sha256": sha256_file(args.audit) if os.path.exists(args.audit) else None,
        "creator_kind_cache_sha256": sha256_file(args.creator_cache),
        "output_sha256": sha256_file(args.output),
        "builder_sha256": sha256_file(__file__),
    })
    with open(args.report, "w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
