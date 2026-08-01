"""Part 13: strengthens revision_v3/external_controls/legitimate_candidates_unique_bytecode.csv
(built in Phase 2) with live verified-source checks, on-chain runtime-bytecode retrieval, and
a three-way provenance categorization. Does not modify the Phase 2 input file -- reads it,
writes a new, separate output.

Usage:
    python3 revision_v3/experiments/external_controls/verify_legitimate_controls.py
"""
from __future__ import annotations

import csv
import json
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "revision_v3", "experiments", "excel_review"))
import evidence_pipeline as ep  # noqa: E402

INPUT_CSV = os.path.join(REPO_ROOT, "revision_v3", "external_controls", "legitimate_candidates_unique_bytecode.csv")
OUTPUT_CSV = os.path.join(REPO_ROOT, "revision_v3", "external_controls", "verified_legitimate_controls.csv")
OUTPUT_DIR = os.path.join(REPO_ROOT, "revision_v3", "external_controls", "bytecode_cache")


def categorize(verified: bool, documented: bool, runtime_match: str) -> str:
    if verified and documented and runtime_match == "MATCH":
        return "VERIFIED_LEGITIMATE_CONTROL"
    if documented:
        return "CANDIDATE_LEGITIMATE_CONTROL"
    return "UNRESOLVED_CONTROL"


def main() -> int:
    with open(INPUT_CSV, newline="") as f:
        rows = list(csv.DictReader(f))

    out_rows = []
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for i, row in enumerate(rows):
        project, chain, address = row["project"], row["chain"], row["address"]
        print(f"[{i+1}/{len(rows)}] {project} {chain}:{address}", flush=True)

        sourcify = ep.check_sourcify(chain, address)
        blockscout = ep.check_blockscout(chain, address)
        verified = sourcify["verified"] or blockscout["verified"]
        contract_name = (blockscout.get("raw") or {}).get("name") or ""
        compiler_version = (blockscout.get("raw") or {}).get("compiler_version") or ""

        live_code = ep.get_code(chain, address)
        runtime_match = "NOT_CHECKED"
        if live_code and live_code != "0x":
            live_sha256 = __import__("hashlib").sha256(
                bytes.fromhex(live_code[2:] if live_code.startswith("0x") else live_code)
            ).hexdigest()
            runtime_match = "MATCH" if live_sha256 == row["runtime_bytecode_sha256"] else "MISMATCH"
            with open(os.path.join(OUTPUT_DIR, f"{project}_{chain}_{address}.hex"), "w") as f:
                f.write(live_code)
        else:
            runtime_match = "NO_LIVE_CODE_FOUND"

        # Proxy/implementation resolution for these controls too (many are 7702 delegates
        # that are themselves proxies, e.g. Coinbase_EIP7702Proxy).
        implementation_address = ""
        if live_code and live_code != "0x":
            analysis = ep.analyze_bytecode(live_code)
            if analysis["has_delegatecall"]:
                for slot_name, slot in (("eip1967", ep.EIP1967_IMPL_SLOT), ("slot_0", "0x0")):
                    val = ep.get_storage_at(chain, address, slot)
                    addr = ep.slot_to_address(val)
                    if addr:
                        implementation_address = addr
                        break

        documented = bool(row.get("documentation_url"))
        category = categorize(verified, documented, runtime_match)

        out_rows.append({
            "project": project,
            "official_documentation": row.get("documentation_url", ""),
            "official_deployment_registry": row.get("documentation_url", ""),
            "chain": chain,
            "address": address,
            "runtime_hash_recorded": row["runtime_bytecode_sha256"],
            "runtime_hash_live": live_sha256 if live_code and live_code != "0x" else "",
            "runtime_source_match": runtime_match,
            "implementation_address": implementation_address,
            "verified_source": verified,
            "source_provider": "sourcify" if sourcify["verified"] else ("blockscout" if blockscout["verified"] else ""),
            "contract_name": contract_name,
            "compiler_version": compiler_version,
            "audit_documentation": row.get("audit_evidence", ""),
            "first_observed_eip7702_authorization": row.get("evidence_of_actual_eip7702_use", ""),
            "authorization_count": "",
            "bytecode_family": row.get("v2_family_id", ""),
            "chain_specific_bytecode_variation": (
                "unique_bytecode_this_row -- see legitimate_candidates_summary.json "
                "byte_identical_across_all_deployed_chains for the project-level answer"
            ),
            "provenance_confidence": "HIGH" if category == "VERIFIED_LEGITIMATE_CONTROL" else (
                "MEDIUM" if category == "CANDIDATE_LEGITIMATE_CONTROL" else "LOW"
            ),
            "category": category,
        })

    fieldnames = list(out_rows[0].keys())
    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    from collections import Counter
    dist = Counter(r["category"] for r in out_rows)
    print(f"\nWrote {len(out_rows)} rows -> {OUTPUT_CSV}")
    print("category distribution:", dist)
    print("runtime_source_match distribution:", Counter(r["runtime_source_match"] for r in out_rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
