"""Phase 2, Part 9: automated legitimate EIP-7702 candidate inventory.

Source: `benign_7702_bytecode.csv` (repo root), itself produced by the existing
`fetch_benign_7702_delegates.py`'s `SEED_DELEGATES` list -- documented legitimate
account-abstraction / wallet-delegate projects with a cited source URL per entry (read
read-only here, nothing re-fetched). Cross-referenced against the canonical Revision v2
benchmark (`revision_v2/data/authguardbench_7702_v2.csv.gz`) to attach family_id and
population tag where the address survived task alignment.

Per the audit brief: source-rule-unflagged primary delegates are NEVER auto-classified as
legitimate here -- this script only ever emits entries that trace to a project explicitly
documented in SEED_DELEGATES. If more evidence existed it would be added the same way (a new
SEED_DELEGATES-style entry with a citable source URL); this pass does not invent new sources.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
OUT_DIR = os.path.join(REPO_ROOT, "revision_v3", "external_controls")
os.makedirs(OUT_DIR, exist_ok=True)

BENIGN_CSV = os.path.join(REPO_ROOT, "benign_7702_bytecode.csv")
V2_BENCHMARK = os.path.join(REPO_ROOT, "revision_v2", "data", "authguardbench_7702_v2.csv.gz")


def sha256_hex(hex_str: str) -> str:
    h = hex_str.lower().replace("0x", "")
    if len(h) % 2:
        h = h[:-1]
    try:
        return hashlib.sha256(bytes.fromhex(h)).hexdigest()
    except ValueError:
        return ""


def main() -> int:
    candidates = pd.read_csv(BENIGN_CSV)
    candidates = candidates[candidates["bytecode_len"] > 0].copy()
    candidates["runtime_bytecode_sha256"] = candidates["bytecode"].apply(sha256_hex)

    v2 = pd.read_csv(V2_BENCHMARK)
    v2_lookup = v2.set_index(["chain", v2["address"].str.lower()])[
        ["family_id", "family_size", "population", "dataset_subset", "sample_id"]
    ]

    rows = []
    for _, row in candidates.iterrows():
        key = (row["chain"], str(row["address"]).lower())
        v2_match = v2_lookup.loc[key] if key in v2_lookup.index else None
        if v2_match is not None and isinstance(v2_match, pd.DataFrame):
            v2_match = v2_match.iloc[0]
        rows.append({
            "project": row["project"],
            "chain": row["chain"],
            "address": row["address"],
            "runtime_bytecode_sha256": row["runtime_bytecode_sha256"],
            "code_bytes": row["bytecode_len"],
            "documentation_url": row["source_url"],
            "in_v2_primary_benchmark": v2_match is not None,
            "v2_family_id": v2_match["family_id"] if v2_match is not None else None,
            "v2_family_size": v2_match["family_size"] if v2_match is not None else None,
            "v2_population": v2_match["population"] if v2_match is not None else None,
            "v2_sample_id": v2_match["sample_id"] if v2_match is not None else None,
            "audit_evidence": "NOT_AVAILABLE_OFFLINE: no third-party audit report URL is "
                              "recorded in SEED_DELEGATES; only the project's own deployment "
                              "documentation is cited",
            "evidence_of_actual_eip7702_use": "NOT_VERIFIED_ONCHAIN: no authorization-list "
                                              "transaction was observed for this address in "
                                              "this offline pass (requires the temporal "
                                              "collector or an archive-node query)",
            "deployment_date": "NOT_AVAILABLE_OFFLINE",
        })

    df = pd.DataFrame(rows)

    # Deduplicate reporting: how many DISTINCT (project, exact-bytecode) pairs, since the
    # same project deploys byte-identical code on some chains but NOT others (see project
    # groupby below) -- exact-bytecode dedup must be done per project, not globally, or two
    # unrelated projects that happen to differ would be wrongly conflated.
    df["project_bytecode_key"] = df["project"] + ":" + df["runtime_bytecode_sha256"]
    unique_project_bytecodes = df.drop_duplicates("project_bytecode_key")

    df.to_csv(os.path.join(OUT_DIR, "legitimate_candidates_all_deployments.csv"), index=False)
    unique_project_bytecodes.to_csv(os.path.join(OUT_DIR, "legitimate_candidates_unique_bytecode.csv"), index=False)

    per_project_chain_identity = {}
    for project, group in df.groupby("project"):
        n_chains = len(group)
        n_unique_bytecodes = group["runtime_bytecode_sha256"].nunique()
        per_project_chain_identity[project] = {
            "n_chain_deployments": n_chains,
            "n_unique_bytecodes_across_chains": n_unique_bytecodes,
            "byte_identical_across_all_deployed_chains": n_unique_bytecodes == 1,
            "chains": sorted(group["chain"].tolist()),
            "documentation_url": group["documentation_url"].iloc[0],
            "in_v2_primary_benchmark_any_chain": bool(group["in_v2_primary_benchmark"].any()),
        }

    summary = {
        "n_documented_projects": df["project"].nunique(),
        "n_total_chain_deployments": len(df),
        "n_unique_project_bytecode_pairs": len(unique_project_bytecodes),
        "n_distinct_runtime_bytecodes_overall": df["runtime_bytecode_sha256"].nunique(),
        "n_present_in_v2_primary_benchmark": int(df["in_v2_primary_benchmark"].sum()),
        "per_project": per_project_chain_identity,
        "target_range_from_brief": "20-50 distinct legitimate implementations/families if "
                                   "evidence supports that many",
        "actual_evidence_supports": f"{df['project'].nunique()} documented projects "
                                    f"({len(unique_project_bytecodes)} unique project-bytecode "
                                    "pairs across chains) -- see LEGITIMATE_CANDIDATE_REPORT.md "
                                    "for why this is below the target range and is NOT padded "
                                    "with unverified candidates.",
    }
    with open(os.path.join(OUT_DIR, "legitimate_candidates_summary.json"), "w") as f:
        json.dump(summary, f, indent=2, default=str)

    print(json.dumps({k: v for k, v in summary.items() if k != "per_project"}, indent=2, default=str))
    print(f"\nprojects: {df['project'].nunique()}, total chain-deployments: {len(df)}, "
          f"unique project-bytecode pairs: {len(unique_project_bytecodes)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
