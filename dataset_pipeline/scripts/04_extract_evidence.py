"""Stage 4: build one structured evidence package per screenable contract, reusing
revision_v3's offline evidence-packet builder (disassembly, proxy/guard detection, structural
counts, selector analysis) and adding a best-effort live Sourcify verified-source lookup.
Evidence packets never contain labels, model scores, or split assignment -- only bytecode-
derived facts and neutral authorization provenance (address/block/tx, not a judgment).
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "dataset_pipeline")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pandas as pd  # noqa: E402

from lib.config import load_config  # noqa: E402
from lib.sourcify import SourcifyCache, check_verified_source  # noqa: E402
from lib.repo_paths import add_revision_v3_src_to_path  # noqa: E402

add_revision_v3_src_to_path()
from evidence.packet_builder import build_evidence_packet  # noqa: E402


def main():
    cfg = load_config()
    run_id = cfg["run_id"]
    fam_path = os.path.join(cfg["_resolved_paths"]["bytecode_families"], f"{run_id}_family_assignment.csv")
    enriched_dir = cfg["_resolved_paths"]["collected_delegates"]
    out_dir = os.path.join(cfg["_resolved_paths"]["evidence_packages"], run_id)
    os.makedirs(out_dir, exist_ok=True)

    families = pd.read_csv(fam_path)
    screenable = families[families["retrieval_status"] == "OK"].copy()

    sourcify_cache = SourcifyCache(cfg["_resolved_paths"]["sourcify_cache"])

    index_rows = []
    for _, r in screenable.iterrows():
        chain = r["chain"]
        address = r["delegate_address"]
        row = {
            "sample_id": address,
            "chain": chain,
            "address": address,
            "runtime_bytecode": r["runtime_bytecode"],
            "code_bytes": r["bytecode_length"],
            "authority_address": None,  # multiple distinct authorities can point to one delegate; see authorization_summary below instead
            "first_block": r["first_observed_block"],
            "first_tx_hash": r["first_observed_tx_hash"],
            "authorization_count": r["authorization_frequency"],
        }
        packet = build_evidence_packet(row)

        # Enrich with neutral, multi-authority authorization summary (packet_builder's single
        # authority_address field doesn't fit the many-signers-per-delegate reality observed
        # in Stage 2 -- see distinct_recovered_authorities in the population table).
        packet["authorization_history"] = {
            "status": "AVAILABLE_FROM_FROZEN_COLLECTOR",
            "delegate_address": address,
            "first_observed_block": int(r["first_observed_block"]),
            "first_observed_transaction": r["first_observed_tx_hash"],
            "observed_authorization_count": int(r["authorization_frequency"]),
            "distinct_recovered_authorities": int(r["distinct_recovered_authorities"]),
            "distinct_tx_senders": int(r["distinct_tx_senders"]),
            "provenance_note": (
                "Authorizing EOAs are recovered from EIP-7702 authorization-tuple signatures "
                "(not assumed from tx.from). These are observation counts, not a security label."
            ),
        }
        packet["exact_bytecode_id"] = r["exact_bytecode_id"]
        packet["bytecode_family_id"] = r["bytecode_family_id"]
        packet["bytecode_family_size"] = int(r["family_size"]) if pd.notna(r["family_size"]) else None

        packet["verified_source_code_availability"] = check_verified_source(chain, address, cache=sourcify_cache)

        out_path = os.path.join(out_dir, f"{chain}_{address}.json")
        with open(out_path, "w") as f:
            json.dump(packet, f, indent=2, default=str)

        index_rows.append({
            "chain": chain, "address": address, "exact_bytecode_id": r["exact_bytecode_id"],
            "bytecode_family_id": r["bytecode_family_id"], "evidence_path": out_path,
            "verified_source_status": packet["verified_source_code_availability"]["status"],
        })

    sourcify_cache.save()

    index_df = pd.DataFrame(index_rows)
    index_path = os.path.join(cfg["_resolved_paths"]["evidence_packages"], f"{run_id}_evidence_index.csv")
    index_df.to_csv(index_path, index=False)

    summary = {
        "n_evidence_packages": len(index_rows),
        "n_verified_source": int((index_df["verified_source_status"] == "VERIFIED").sum()) if len(index_df) else 0,
        "out_dir": out_dir,
        "index_csv": index_path,
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
