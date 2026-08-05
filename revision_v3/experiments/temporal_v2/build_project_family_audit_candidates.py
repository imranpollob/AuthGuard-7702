"""Build score-blind project-family proposals without editing the authoritative audit.

The output is an auditor work aid, not a completed project-ownership decision. It combines the
already conservative authority/deployer must-links with verified on-chain source identity and
keeps every unsupported item as an explicit anonymous singleton proposal.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re

import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
BASE = os.path.join(REPO_ROOT, "revision_v3", "results", "postcutoff_snapshot")


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalized_name(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _cache_metadata(path: str) -> dict[str, dict]:
    by_item: dict[str, dict] = {}
    with open(path) as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("retrieval_status") != "COMPLETE":
                continue
            item = by_item.setdefault(str(record["item_id"]), {
                "creator_address": "", "verified_names": set(), "references": set()
            })
            item["references"].add(str(record.get("provider_url", "")))
            summary = record.get("summary", {})
            if record.get("provider") == "blockscout_address":
                item["creator_address"] = str(summary.get("creator_address") or "").lower()
                if summary.get("is_verified") and summary.get("name"):
                    item["verified_names"].add(str(summary["name"]))
            elif record.get("provider") == "blockscout_contract":
                if summary.get("is_verified") and summary.get("name"):
                    item["verified_names"].add(str(summary["name"]))
            elif record.get("provider") == "sourcify":
                if summary.get("lookup_status") == "VERIFIED" and summary.get("contract_name"):
                    item["verified_names"].add(str(summary["contract_name"]))
    return by_item


def build_candidates(
    worklist: pd.DataFrame,
    dependence: pd.DataFrame,
    metadata: dict[str, dict],
) -> pd.DataFrame:
    required = {"item_id", "dependence_cluster_id", "dependence_cluster_size", "linkage_evidence"}
    if missing := required - set(dependence.columns):
        raise ValueError(f"dependence input is missing columns: {sorted(missing)}")
    if set(worklist["item_id"].astype(str)) != set(dependence["item_id"].astype(str)):
        raise ValueError("worklist and dependence populations differ")
    merged = worklist.merge(dependence, on="item_id", validate="one_to_one")
    # Names link deployments only when both the verified name and creator match. Reused names
    # under unrelated creators are deliberately not treated as a project identity.
    name_creator_groups: dict[tuple[str, str], list[str]] = {}
    for item_id in merged["item_id"].astype(str):
        record = metadata.get(item_id, {})
        creator = str(record.get("creator_address") or "")
        for name in record.get("verified_names", set()):
            normalized = _normalized_name(name)
            if normalized and creator:
                name_creator_groups.setdefault((normalized, creator), []).append(item_id)

    parent = {item_id: item_id for item_id in merged["item_id"].astype(str)}

    def find(value: str) -> str:
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    def union(left: str, right: str) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[max(left_root, right_root)] = min(left_root, right_root)

    for _, group in merged.groupby("dependence_cluster_id"):
        ids = sorted(group["item_id"].astype(str))
        for item_id in ids[1:]:
            union(ids[0], item_id)
    for ids in name_creator_groups.values():
        for item_id in sorted(ids)[1:]:
            union(sorted(ids)[0], item_id)

    groups: dict[str, list[str]] = {}
    for item_id in sorted(parent):
        groups.setdefault(find(item_id), []).append(item_id)
    project_id_by_item = {}
    for items in groups.values():
        digest = hashlib.sha256("\n".join(items).encode()).hexdigest()[:12].upper()
        for item_id in items:
            project_id_by_item[item_id] = f"PF_CANDIDATE_{digest}"

    rows = []
    for row in merged.sort_values("item_id").to_dict("records"):
        item_id = str(row["item_id"])
        record = metadata.get(item_id, {})
        names = sorted(record.get("verified_names", set()))
        cluster_items = groups[find(item_id)]
        if len(cluster_items) > 1:
            status = "STRONG_ONCHAIN_CLUSTER_PROPOSAL"
        elif names:
            status = "VERIFIED_SOURCE_SINGLETON_PROPOSAL"
        else:
            status = "ANONYMOUS_SINGLETON_REQUIRES_RESEARCH"
        references = sorted(filter(None, record.get("references", set())))
        rows.append({
            "item_id": item_id,
            "proposed_project_family_id": project_id_by_item[item_id],
            "proposal_status": status,
            "proposed_cluster_size": len(cluster_items),
            "dependence_cluster_id": row["dependence_cluster_id"],
            "dependence_linkage_evidence": row["linkage_evidence"],
            "verified_source_names": ";".join(names),
            "creator_address": record.get("creator_address", ""),
            "evidence_reference_candidates": ";".join(references),
            "auditor_instruction": (
                "Verify ownership/related deployments independently. A source name establishes "
                "deployed code identity only and must never be interpreted as legitimacy or an "
                "official brand association. Copy accepted fields into the authoritative audit "
                "only after review."
            ),
        })
    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worklist", default=os.path.join(BASE, "postcutoff_project_family_worklist.csv"))
    parser.add_argument("--dependence", default=os.path.join(BASE, "postcutoff_dependence_clusters.csv"))
    parser.add_argument("--cache", default=os.path.join(BASE, "postcutoff_public_provenance_cache.jsonl"))
    parser.add_argument("--output", default=os.path.join(BASE, "postcutoff_project_family_candidates.csv"))
    parser.add_argument("--report", default=os.path.join(BASE, "postcutoff_project_family_candidates_report.json"))
    args = parser.parse_args()
    output = build_candidates(
        pd.read_csv(args.worklist), pd.read_csv(args.dependence), _cache_metadata(args.cache)
    )
    output.to_csv(args.output, index=False, lineterminator="\n")
    counts = output["proposal_status"].value_counts().sort_index().to_dict()
    report = {
        "status": "SCORE_BLIND_PROJECT_FAMILY_CANDIDATES_ONLY",
        "n_items": len(output),
        "n_proposed_families": int(output["proposed_project_family_id"].nunique()),
        "proposal_status_counts": {key: int(value) for key, value in counts.items()},
        "n_items_with_verified_source_names": int(output["verified_source_names"].ne("").sum()),
        "worklist_sha256": sha256_file(args.worklist),
        "dependence_sha256": sha256_file(args.dependence),
        "public_provenance_cache_sha256": sha256_file(args.cache),
        "output_sha256": sha256_file(args.output),
        "builder_sha256": sha256_file(__file__),
        "claim_boundary": (
            "This artifact proposes conservative research clusters only. It does not complete "
            "the authoritative audit, prove ownership, establish legitimacy, or supply labels."
        ),
    }
    with open(args.report, "w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
