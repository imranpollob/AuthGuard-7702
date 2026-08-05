"""Freeze score-blind external legitimate-project controls before model scoring.

This registry distinguishes three concepts that must not be conflated:

* a project absent from the Revision-v2 benchmark;
* a runtime absent from Revision v2; and
* an implementation lineage absent from Revision v2.

Official deployment evidence establishes that an address belongs to a real project.  It
does not establish that the code is safe.  Likewise, an exact-runtime non-overlap does not
prove an independent architecture.  The output is therefore a bounded-negative control
registry for descriptive warning/defer analysis, never a safety certification.

The script performs no model inference and reads no security labels or model scores.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
V3 = os.path.join(REPO_ROOT, "revision_v3")
sys.path.insert(0, os.path.join(V3, "src"))

from features.disassembler import linear_sweep, normalize_hex  # noqa: E402
from features.hashing import opcode_kgrams  # noqa: E402
OUT_DIR = os.path.join(V3, "external_controls")
BYTECODE_DIR = os.path.join(OUT_DIR, "final_bytecode_cache")
OUTPUT = os.path.join(OUT_DIR, "final_new_legitimate_projects.csv")
REPORT = os.path.join(OUT_DIR, "final_new_legitimate_projects_report.json")

V2 = os.path.join(REPO_ROOT, "revision_v2", "data", "authguardbench_7702_v2.csv.gz")
DEV_MANIFESTS = [
    os.path.join(V3, "human_eval", "gold_dev_manifest.csv"),
    os.path.join(V3, "human_eval", "gold_test_manifest.csv"),
]
PRIMARY = os.path.join(V3, "results", "postcutoff_snapshot", "postcutoff_review_manifest.csv")
RESERVE = os.path.join(V3, "results", "confirmatory_snapshot", "confirmatory_review_manifest.csv")
POSTCUTOFF_CANDIDATES = os.path.join(
    V3, "results", "postcutoff_snapshot", "ethereum_candidates.csv.gz"
)

USER_AGENT = "AuthGuard-7702-score-blind-control-freeze/1.0"


CANDIDATES = [
    {
        "control_id": "LEGIT-NEW-001",
        "project": "Tangem",
        "classification": "NEW_PROJECT_INDEPENDENT_IMPLEMENTATION",
        "chain": "ethereum",
        "chain_id": 1,
        "address": "0xe3014e9ab2739adef234b3829c79128746160178",
        "rpc_urls": ["https://ethereum-rpc.publicnode.com", "https://1rpc.io/eth"],
        "blockscout_host": "https://eth.blockscout.com",
        "expected_contract_name": "Tangem7702GaslessExecutorL1",
        "expected_code_bytes": 7292,
        "expected_runtime_sha256": "87a66ba4ebdefb774b4e67e728971a13e99b351ee15a3fc5b1e46aff975d0c39",
        "official_documentation_url": "https://tangem.com/en/blog/post/smart-gas/",
        "official_deployment_evidence_url": "https://tangem.com/en/blog/post/smart-gas/",
        "audit_url": (
            "https://github.com/pessimistic-io/audits/blob/"
            "955cc19caace617a96b9b2fefa91d7eb9e241f33/"
            "Tangem_Gassless_Transactions_Security_Analysis_by_Pessimistic.pdf"
        ),
        "audit_status": "THIRD_PARTY_AUDIT_REPORT_LINKED_BY_PROJECT",
        "project_overlap_audit": "CONFIRMED_ABSENT_FROM_V2_AND_DEVELOPMENT_REGISTRIES",
        "known_v2_project_addresses": [],
        "known_v2_lineage_addresses": [],
        "implementation_lineage": "TANGEM_CUSTOM",
        "lineage_evidence": (
            "Tangem's official technical description states that it developed a custom, "
            "non-upgradeable implementation instead of adopting an existing solution."
        ),
        "actual_use_requirement": "OBSERVED_POSTCUTOFF_AUTHORIZATIONS",
        "endpoint_eligibility": "NEW_PROJECT_USED_CONTROL",
    },
    {
        "control_id": "LEGIT-NEW-002",
        "project": "Startale",
        "classification": "NEW_PROJECT_OFFICIAL_IMPLEMENTATION",
        "chain": "soneium",
        "chain_id": 1868,
        "address": "0x000000b8f5f723a680d3d7ee624fe0bc84a6e05a",
        "rpc_urls": ["https://rpc.soneium.org", "https://soneium-rpc.publicnode.com"],
        "blockscout_host": "https://soneium.blockscout.com",
        "expected_contract_name": "StartaleSmartAccount",
        "expected_code_bytes": 24399,
        "expected_runtime_sha256": "70646a4d8b12376f5ae66206033b07e9cdeb057a7ee39a84916e19604afe7ca0",
        "official_documentation_url": "https://docs.startale.com/aa-sdk/eip7702",
        "official_deployment_evidence_url": (
            "https://docs.startale.com/aa-sdk/resources/contracts-and-audits"
        ),
        "audit_url": "https://docs.startale.com/aa-sdk/resources/contracts-and-audits",
        "audit_status": "OFFICIAL_DOCUMENTATION_ASSERTS_AUDITED",
        "project_overlap_audit": "CONFIRMED_ABSENT_FROM_V2_AND_DEVELOPMENT_REGISTRIES",
        "known_v2_project_addresses": [],
        "known_v2_lineage_addresses": [],
        "implementation_lineage": "STARTALE_SMART_ACCOUNT",
        "lineage_evidence": (
            "Verified source uses Startale-specific account modules plus public ERC-4337, "
            "ERC-7579, OpenZeppelin, Solady, and utility libraries; no prior benchmark project "
            "identity is asserted."
        ),
        "actual_use_requirement": "OFFICIAL_DEPLOYMENT_ONLY",
        "endpoint_eligibility": "NEW_PROJECT_DEPLOYED_CONTROL",
    },
    {
        "control_id": "LEGIT-NEW-003",
        "project": "Rainbow",
        "classification": "NEW_PROJECT_KNOWN_FRAMEWORK_LINEAGE",
        "chain": "ethereum",
        "chain_id": 1,
        "address": "0x612373d7003d694220f7800eeaf8e3924c0951d3",
        "rpc_urls": ["https://ethereum-rpc.publicnode.com", "https://1rpc.io/eth"],
        "blockscout_host": "https://eth.blockscout.com",
        "expected_contract_name": "CaliburEntry",
        "expected_code_bytes": 24504,
        "expected_runtime_sha256": "56926d3a19c73d00c503d036de685b104193f90188b6d5ad952f991acd0ec682",
        "official_documentation_url": "https://www.npmjs.com/package/@rainbow-me/delegation/v/0.3.2",
        "official_deployment_evidence_url": (
            "https://registry.npmjs.org/@rainbow-me/delegation/0.3.2"
        ),
        "audit_url": "",
        "audit_status": "NO_PROJECT_SPECIFIC_AUDIT_LOCATED",
        "project_overlap_audit": "CONFIRMED_ABSENT_FROM_V2_AND_DEVELOPMENT_REGISTRIES",
        "known_v2_project_addresses": [],
        "known_v2_lineage_addresses": ["0x000000005c84f8fd50b21cac312528a64437030e"],
        "implementation_lineage": "CALIBUR",
        "lineage_evidence": (
            "The official Rainbow package exposes the address, names CaliburEntry ABI, and the "
            "verified onchain contract is CaliburEntry. Project generalization is distinct from "
            "implementation-lineage generalization."
        ),
        "actual_use_requirement": "OBSERVED_POSTCUTOFF_AUTHORIZATIONS",
        "endpoint_eligibility": "NEW_PROJECT_USED_KNOWN_LINEAGE_CONTROL",
    },
    {
        "control_id": "LEGIT-LINEAGE-001",
        "project": "Porto",
        "classification": "NEW_IMPLEMENTATION_KNOWN_PROJECT",
        "chain": "ethereum",
        "chain_id": 1,
        "address": "0x7c27e3aecbf42879b64d76f604dc3430f4886462",
        "rpc_urls": ["https://ethereum-rpc.publicnode.com", "https://1rpc.io/eth"],
        "blockscout_host": "https://eth.blockscout.com",
        "expected_contract_name": "EIP7702Proxy",
        "expected_code_bytes": 496,
        "expected_runtime_sha256": "9599631be8c05b3f3daf45b2ae5e1dd6946c23108e5000a2905b5db589841417",
        "official_documentation_url": "https://porto.sh/contracts/address-book",
        "official_deployment_evidence_url": "https://github.com/ithacaxyz/account",
        "audit_url": "",
        "audit_status": "NOT_USED_AS_NEW_PROJECT_CONTROL",
        "project_overlap_audit": "KNOWN_PROJECT_PRESENT_IN_V2",
        "known_v2_project_addresses": ["0x664ab8c20b629422f5398e58ff8989e68b26a4e6"],
        "known_v2_lineage_addresses": [],
        "implementation_lineage": "PORTO_ACCOUNT",
        "lineage_evidence": "A prior Porto deployment is identified in the v2 benchmark.",
        "actual_use_requirement": "OBSERVED_POSTCUTOFF_AUTHORIZATIONS",
        "endpoint_eligibility": "EXCLUDED_NEW_PROJECT_ENDPOINT",
    },
    {
        "control_id": "LEGIT-LINEAGE-002",
        "project": "Rhinestone Nexus",
        "classification": "KNOWN_LINEAGE_NEW_DEPLOYMENT",
        "chain": "ethereum",
        "chain_id": 1,
        "address": "0x000000000032ddc454c3bdcba80484ad5a798705",
        "rpc_urls": ["https://ethereum-rpc.publicnode.com", "https://1rpc.io/eth"],
        "blockscout_host": "https://eth.blockscout.com",
        "expected_contract_name": "Nexus",
        "expected_code_bytes": 23413,
        "expected_runtime_sha256": "02f8dc9549d1b2797b8d7ed416498221ddf8f62ecc280ed4633b52beffcb09ea",
        "official_documentation_url": "https://docs.rhinestone.wtf/smart-wallet",
        "official_deployment_evidence_url": "https://docs.rhinestone.wtf/smart-wallet/account/address-book",
        "audit_url": "",
        "audit_status": "NOT_USED_AS_NEW_PROJECT_CONTROL",
        "project_overlap_audit": "KNOWN_BICONOMY_NEXUS_LINEAGE_PRESENT_IN_V2",
        "known_v2_project_addresses": [],
        "known_v2_lineage_addresses": ["0x0000000020fe2f30453074ad916edeb653ec7e9d"],
        "implementation_lineage": "BICONOMY_NEXUS",
        "lineage_evidence": "Nexus lineage is represented by a Biconomy Nexus deployment in v2.",
        "actual_use_requirement": "OBSERVED_POSTCUTOFF_AUTHORIZATIONS",
        "endpoint_eligibility": "EXCLUDED_NEW_PROJECT_ENDPOINT",
    },
]


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _request_json(url: str, *, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode()
    headers = {"User-Agent": USER_AGENT}
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def fetch_runtime(address: str, rpc_urls: list[str]) -> tuple[str, str]:
    errors = []
    for rpc_url in rpc_urls:
        try:
            response = _request_json(
                rpc_url,
                payload={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "eth_getCode",
                    "params": [address, "latest"],
                },
            )
            if response.get("error"):
                raise RuntimeError(str(response["error"]))
            runtime = str(response.get("result", ""))
            if not runtime.startswith("0x") or len(runtime) <= 2:
                raise ValueError("empty or malformed runtime")
            return runtime.lower(), rpc_url
        except Exception as error:  # fail over, then report all provider errors
            errors.append(f"{rpc_url}: {type(error).__name__}: {error}")
    raise RuntimeError("all RPC endpoints failed: " + " | ".join(errors))


def fetch_verification(host: str, address: str) -> dict:
    response = _request_json(f"{host}/api/v2/smart-contracts/{address}")
    return {
        "contract_name": str(response.get("name") or ""),
        "verified_source": bool(response.get("is_verified")),
        "fully_verified": bool(response.get("is_fully_verified")),
        "compiler_version": str(response.get("compiler_version") or ""),
        "source_file": str(response.get("file_path") or ""),
        "source_provider_url": f"{host}/api/v2/smart-contracts/{address}",
    }


def classification_gate(record: dict) -> tuple[bool, str]:
    """Fail closed when deciding new-project endpoint eligibility."""
    eligible_classifications = {
        "NEW_PROJECT_INDEPENDENT_IMPLEMENTATION",
        "NEW_PROJECT_OFFICIAL_IMPLEMENTATION",
        "NEW_PROJECT_KNOWN_FRAMEWORK_LINEAGE",
    }
    if record["classification"] not in eligible_classifications:
        return False, "classification is not a new project"
    if record["project_overlap_audit"] != "CONFIRMED_ABSENT_FROM_V2_AND_DEVELOPMENT_REGISTRIES":
        return False, "project-level non-overlap was not confirmed"
    overlap_fields = [
        "v2_address_overlap", "v2_runtime_overlap", "development_address_overlap",
        "development_runtime_overlap", "primary_manifest_overlap", "reserve_manifest_overlap",
    ]
    if any(bool(record[field]) for field in overlap_fields):
        return False, "exact address or runtime overlaps a protected population"
    if not record["verified_source"] or record["contract_name"] != record["expected_contract_name"]:
        return False, "onchain source identity is not verified as expected"
    if record["runtime_bytecode_sha256"] != record["expected_runtime_sha256"]:
        return False, "live runtime differs from the pre-audited candidate"
    if record["actual_use_requirement"] == "OBSERVED_POSTCUTOFF_AUTHORIZATIONS":
        if int(record["authorization_count"]) <= 0:
            return False, "required post-cutoff authorization evidence is absent"
        if not record["historical_runtime_matches_live"]:
            return False, "runtime changed after first observed authorization"
    return True, "eligible for its declared descriptive new-project stratum"


def _address_set(frame: pd.DataFrame) -> set[str]:
    return set(frame["address"].astype(str).str.lower())


def _jaccard(left: set, right: set) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def build_canonical_similarity_index(v2: pd.DataFrame) -> list[tuple[str, str, set]]:
    """Index every unique v2 runtime, matching the frozen post-cutoff leakage audit."""
    unique = v2.sort_values(["family_id", "bytecode_sha256"]).drop_duplicates(
        "bytecode_sha256", keep="first"
    )
    index = []
    for row in unique.itertuples(index=False):
        tokens, _, _ = linear_sweep(normalize_hex(row.runtime_bytecode))
        index.append((str(row.family_id), str(row.bytecode_sha256), opcode_kgrams(tokens, k=4)))
    return index


def best_canonical_similarity(runtime: str, index: list[tuple[str, str, set]]) -> tuple[str, float]:
    tokens, _, _ = linear_sweep(normalize_hex(runtime))
    grams = opcode_kgrams(tokens, k=4)
    best_family, best_similarity = "", -1.0
    for family_id, _, historical_grams in index:
        similarity = _jaccard(grams, historical_grams)
        if similarity > best_similarity:
            best_family, best_similarity = family_id, similarity
    return best_family, best_similarity


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="replace an existing registry only during an explicitly documented pre-score refreeze",
    )
    args = parser.parse_args()
    if (os.path.exists(OUTPUT) or os.path.exists(REPORT)) and not args.overwrite:
        raise FileExistsError(
            "external legitimate-project registry is already frozen; use --overwrite only "
            "before any model scoring and document the refreeze"
        )
    os.makedirs(BYTECODE_DIR, exist_ok=True)
    v2 = pd.read_csv(V2)
    development = pd.concat([pd.read_csv(path) for path in DEV_MANIFESTS], ignore_index=True)
    primary = pd.read_csv(PRIMARY)
    reserve = pd.read_csv(RESERVE)
    postcutoff = pd.read_csv(POSTCUTOFF_CANDIDATES)
    postcutoff["delegate_address"] = postcutoff["delegate_address"].astype(str).str.lower()
    canonical_similarity_index = build_canonical_similarity_index(v2)

    v2_addresses = _address_set(v2)
    v2_hashes = set(v2["bytecode_sha256"].astype(str))
    development_addresses = _address_set(development)
    development_hashes = set(development["bytecode_sha256"].astype(str))
    primary_addresses, reserve_addresses = _address_set(primary), _address_set(reserve)
    primary_hashes = set(primary["bytecode_sha256"].astype(str))
    reserve_hashes = set(reserve["bytecode_sha256"].astype(str))

    rows = []
    for candidate in CANDIDATES:
        row = dict(candidate)
        address = row["address"].lower()
        runtime, rpc_url_used = fetch_runtime(address, row.pop("rpc_urls"))
        runtime_bytes = bytes.fromhex(runtime[2:])
        runtime_hash = hashlib.sha256(runtime_bytes).hexdigest()
        best_family, best_similarity = best_canonical_similarity(
            runtime, canonical_similarity_index
        )
        verification = fetch_verification(row["blockscout_host"], address)
        row.update(verification)
        row.update({
            "address": address,
            "rpc_url_used": rpc_url_used,
            "runtime_bytecode_sha256": runtime_hash,
            "code_bytes": len(runtime_bytes),
            "canonical_best_opcode4gram_family": best_family,
            "canonical_best_opcode4gram_similarity": best_similarity,
            "canonical_unseen_at_0_85": runtime_hash not in v2_hashes and best_similarity < 0.85,
            "v2_address_overlap": address in v2_addresses,
            "v2_runtime_overlap": runtime_hash in v2_hashes,
            "development_address_overlap": address in development_addresses,
            "development_runtime_overlap": runtime_hash in development_hashes,
            "primary_manifest_overlap": address in primary_addresses or runtime_hash in primary_hashes,
            "reserve_manifest_overlap": address in reserve_addresses or runtime_hash in reserve_hashes,
            "declared_v2_project_addresses_present": bool(row["known_v2_project_addresses"])
            and all(known.lower() in v2_addresses for known in row["known_v2_project_addresses"]),
            "declared_v2_lineage_addresses_present": bool(row["known_v2_lineage_addresses"])
            and all(known.lower() in v2_addresses for known in row["known_v2_lineage_addresses"]),
        })
        if len(runtime_bytes) != int(row["expected_code_bytes"]) or runtime_hash != row["expected_runtime_sha256"]:
            raise ValueError(f"{row['control_id']} live runtime differs from the audited candidate")
        if verification["contract_name"] != row["expected_contract_name"] or not verification["verified_source"]:
            raise ValueError(f"{row['control_id']} does not have the expected verified source identity")
        if row["known_v2_project_addresses"] and not row["declared_v2_project_addresses_present"]:
            raise ValueError(f"{row['control_id']} known-project overlap evidence is absent from v2")
        if row["known_v2_lineage_addresses"] and not row["declared_v2_lineage_addresses_present"]:
            raise ValueError(f"{row['control_id']} known-lineage evidence is absent from v2")

        observed = postcutoff.loc[postcutoff["delegate_address"].eq(address)]
        if len(observed) > 1:
            raise ValueError(f"duplicate post-cutoff candidate rows for {address}")
        if observed.empty:
            row.update({
                "authorization_count": 0,
                "first_observed_timestamp_unix": "",
                "historical_runtime_sha256": "",
                "historical_runtime_matches_live": False,
                "actual_use_status": "OFFICIAL_DEPLOYMENT_AUTHORIZATION_COUNT_NOT_COLLECTED",
                "postcutoff_candidate_unseen_family": "",
                "matched_historical_family": "",
                "best_historical_family_similarity": "",
                "postcutoff_exact_runtime_family": "",
            })
        else:
            observed_row = observed.iloc[0]
            historical_hash = str(observed_row["historical_bytecode_sha256"])
            row.update({
                "authorization_count": int(observed_row["authorization_count"]),
                "first_observed_timestamp_unix": int(observed_row["first_timestamp_unix"]),
                "historical_runtime_sha256": historical_hash,
                "historical_runtime_matches_live": historical_hash == runtime_hash,
                "actual_use_status": "OBSERVED_IN_POSTCUTOFF_AUTHORIZATION_WINDOW",
                "postcutoff_candidate_unseen_family": bool(
                    observed_row["is_candidate_unseen_family"]
                ),
                "matched_historical_family": str(observed_row["matched_historical_family"]),
                "best_historical_family_similarity": float(
                    observed_row["best_historical_family_similarity"]
                ),
                "postcutoff_exact_runtime_family": str(
                    observed_row["postcutoff_exact_runtime_family"]
                ),
            })
        eligible, reason = classification_gate(row)
        row["new_project_endpoint_eligible"] = eligible
        row["eligibility_reason"] = reason
        row["independent_lineage_endpoint_eligible"] = bool(
            eligible
            and row["classification"] == "NEW_PROJECT_INDEPENDENT_IMPLEMENTATION"
            and row["canonical_unseen_at_0_85"]
        )
        row["known_v2_project_addresses"] = ";".join(row["known_v2_project_addresses"])
        row["known_v2_lineage_addresses"] = ";".join(row["known_v2_lineage_addresses"])
        row["claim_boundary"] = (
            "Documented legitimate deployment is a bounded-negative control, not proof that the "
            "runtime is safe, audited without residual findings, or suitable to authorize."
        )

        bytecode_path = os.path.join(BYTECODE_DIR, f"{row['control_id'].lower()}.hex")
        with open(bytecode_path, "w") as handle:
            handle.write(runtime + "\n")
        row["frozen_bytecode_path"] = os.path.relpath(bytecode_path, REPO_ROOT)
        row["frozen_bytecode_file_sha256"] = sha256_file(bytecode_path)
        rows.append(row)

    output = pd.DataFrame(rows).sort_values("control_id", kind="mergesort")
    output.to_csv(OUTPUT, index=False, lineterminator="\n")
    eligible = output.loc[output["new_project_endpoint_eligible"].eq(True)]  # noqa: E712
    report = {
        "status": "FROZEN_SCORE_BLIND_EXTERNAL_LEGITIMATE_PROJECT_REGISTRY",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "n_candidates_audited": len(output),
        "n_new_project_controls": len(eligible),
        "n_new_project_used_controls": int(
            eligible["actual_use_status"].eq("OBSERVED_IN_POSTCUTOFF_AUTHORIZATION_WINDOW").sum()
        ),
        "n_new_project_deployment_only_controls": int(
            eligible["actual_use_status"].eq(
                "OFFICIAL_DEPLOYMENT_AUTHORIZATION_COUNT_NOT_COLLECTED"
            ).sum()
        ),
        "n_independent_lineage_controls": int(
            eligible["independent_lineage_endpoint_eligible"].sum()
        ),
        "n_canonical_unseen_new_project_controls": int(
            eligible["canonical_unseen_at_0_85"].sum()
        ),
        "eligible_projects": eligible["project"].tolist(),
        "used_new_project_controls": eligible.loc[
            eligible["actual_use_status"].eq("OBSERVED_IN_POSTCUTOFF_AUTHORIZATION_WINDOW"),
            "project",
        ].tolist(),
        "canonical_unseen_new_project_controls": eligible.loc[
            eligible["canonical_unseen_at_0_85"].eq(True), "project"  # noqa: E712
        ].tolist(),
        "classification_counts": {
            key: int(value)
            for key, value in output["classification"].value_counts().sort_index().items()
        },
        "input_locks": {
            os.path.relpath(path, REPO_ROOT): sha256_file(path)
            for path in [V2, *DEV_MANIFESTS, PRIMARY, RESERVE, POSTCUTOFF_CANDIDATES]
        },
        "registry_sha256": sha256_file(OUTPUT),
        "builder_sha256": sha256_file(__file__),
        "claim_boundary": (
            "The registry supports descriptive warning/defer analysis on official legitimate "
            "deployments. It does not establish safety. Project, runtime, and implementation-"
            "lineage generalization are reported separately."
        ),
    }
    with open(REPORT, "w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
