"""Resolve proxy implementation targets for U-labelled contracts and attach the implementation's
own reachability analysis to their evidence packages.

Scope: only contracts currently labelled U whose coverage reason is an unresolved proxy target
(or that carry a proxy indicator), per the instruction to re-run only affected U contracts.
Everything is fetched at the delegate's first-observed authorization block so the resolved
implementation matches the dataset's bytecode snapshot.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "dataset_pipeline")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pandas as pd  # noqa: E402

from lib.bytecode_cache import BytecodeCache  # noqa: E402
from lib.config import load_config  # noqa: E402
from lib.proxy_resolver import MAX_DEPTH, resolve_chain  # noqa: E402
from lib.reachability import analyze_reachability  # noqa: E402
from lib.repo_paths import add_revision_v3_src_to_path  # noqa: E402

add_revision_v3_src_to_path()
from temporal.rpc_client import ChainClient  # noqa: E402


def main():
    cfg = load_config()
    run_id = cfg["run_id"]
    reviews = pd.read_csv(os.path.join(cfg["_resolved_paths"]["llm_reviews"], f"{run_id}_review_index_promptv3.csv"))
    index = pd.read_csv(os.path.join(cfg["_resolved_paths"]["evidence_packages"], f"{run_id}_evidence_index.csv"))
    families = pd.read_csv(os.path.join(cfg["_resolved_paths"]["bytecode_families"], f"{run_id}_family_assignment.csv"))
    fam = families.set_index("delegate_address")
    enriched = pd.read_csv(
        os.path.join(cfg["_resolved_paths"]["collected_delegates"], f"{run_id}_ethereum_authorizations_enriched.csv"),
        dtype=str, usecols=["delegate_address", "recovered_authority", "block_number"])
    first_authority = (enriched.sort_values("block_number").groupby("delegate_address")["recovered_authority"].first())

    u_addresses = set(reviews[reviews["proposed_label"] == "U"]["address"])
    targets = []
    for r in index.itertuples(index=False):
        if r.address not in u_addresses:
            continue
        with open(r.evidence_path) as f:
            packet = json.load(f)
        reach = packet.get("reachability", {}) or {}
        proxy = packet["proxy_evidence"]
        looks_proxy = (reach.get("reachable_delegatecall_with_unresolved_target")
                       or proxy["has_delegatecall"] or proxy["is_eip7702_designator"]
                       or proxy["eip1967_implementation_slot_present"] or proxy["eip1967_beacon_slot_present"]
                       or proxy["resembles_minimal_forwarder"])
        if looks_proxy:
            already = packet.get("proxy_resolution")
            targets.append((r.chain, r.address, r.evidence_path, bool(already)))

    done_already = sum(1 for t in targets if t[3])
    print(f"[proxy] {len(u_addresses)} U contracts; {len(targets)} carry a proxy indicator; "
          f"{done_already} already resolved in a previous run (skipped)", flush=True)
    cache = BytecodeCache(cfg["_resolved_paths"]["bytecode_cache"])
    clients = {}
    rows = []
    for i, (chain, address, evidence_path, already_done) in enumerate(targets, start=1):
        if already_done:
            with open(evidence_path) as f:
                prior = json.load(f)
            rec = prior["proxy_resolution"]
            hop0 = (rec.get("hops") or [{}])[0]
            rows.append({
                "chain": chain, "address": address, "resolved": rec["resolved"],
                "implementation_address": rec.get("implementation_address"),
                "method": hop0.get("method"), "scope": hop0.get("scope"),
                "depth_used": rec.get("depth_used"),
                "implementation_bytecode_sha256": rec.get("implementation_bytecode_sha256"),
                "implementation_coverage_status": rec.get("implementation_coverage_status"),
                "unresolved_reason": rec.get("unresolved_reason"),
            })
            continue
        client = clients.setdefault(chain, ChainClient(chain))
        block = int(fam.loc[address, "first_observed_block"])
        block_tag = hex(block)
        code_hex = fam.loc[address, "runtime_bytecode"]
        authority = first_authority.get(address)

        result = resolve_chain(client, address, block_tag, code_hex, authority=authority,
                                max_depth=MAX_DEPTH)

        with open(evidence_path) as f:
            packet = json.load(f)

        record = {
            "resolution_attempted": True,
            "max_depth": MAX_DEPTH,
            "resolved": bool(result.get("resolved") and result.get("final_bytecode")),
            "hops": result.get("hops", []),
            "depth_used": result.get("depth"),
            "unresolved_reason": result.get("unresolved_reason"),
            "proxy_address": address,
            "proxy_bytecode_sha256": fam.loc[address, "bytecode_sha256"],
            "implementation_address": result.get("final_implementation"),
            "resolved_at_block": block,
            "resolved_at_block_tag": block_tag,
            "authorizing_eoa_used": authority,
        }

        impl_code = result.get("final_bytecode")
        if record["resolved"] and impl_code and impl_code != "0x":
            impl_bytes = bytes.fromhex(impl_code[2:])
            record["implementation_bytecode_sha256"] = hashlib.sha256(impl_bytes).hexdigest()
            record["implementation_bytecode_length"] = len(impl_bytes)
            cache.put(chain, record["implementation_address"], block_tag,
                      {"code": impl_code, "error": None})
            try:
                impl_reach = analyze_reachability(impl_code, is_designator=False)
            except Exception as e:  # noqa: BLE001
                impl_reach = {"coverage_status": "PARTIAL",
                              "coverage_reasons": [f"implementation analysis failed: {e}"],
                              "analysis_error": str(e)}
            packet["implementation_reachability"] = impl_reach
            record["implementation_coverage_status"] = impl_reach.get("coverage_status")
        packet["proxy_resolution"] = record
        with open(evidence_path, "w") as f:
            json.dump(packet, f, indent=2, default=str)

        rows.append({
            "chain": chain, "address": address,
            "resolved": record["resolved"],
            "implementation_address": record["implementation_address"],
            "method": result["hops"][0]["method"] if result.get("hops") else None,
            "scope": result["hops"][0].get("scope") if result.get("hops") else None,
            "depth_used": record["depth_used"],
            "implementation_bytecode_sha256": record.get("implementation_bytecode_sha256"),
            "implementation_coverage_status": record.get("implementation_coverage_status"),
            "unresolved_reason": record["unresolved_reason"],
        })
        if i % 10 == 0:
            print(f"[proxy] {i}/{len(targets)}", flush=True)

    cache.save()
    out = pd.DataFrame(rows)
    out_path = os.path.join(cfg["_resolved_paths"]["evidence_packages"], f"{run_id}_proxy_resolution.csv")
    out.to_csv(out_path, index=False)
    summary = {
        "n_u_contracts": len(u_addresses),
        "n_with_proxy_indicator": len(targets),
        "n_resolved": int(out["resolved"].sum()) if len(out) else 0,
        "n_unresolved": int((~out["resolved"]).sum()) if len(out) else 0,
        "methods": out[out["resolved"]]["method"].value_counts().to_dict() if len(out) else {},
        "scopes": out[out["resolved"]]["scope"].value_counts().to_dict() if len(out) else {},
        "implementation_coverage": out["implementation_coverage_status"].value_counts().to_dict() if len(out) else {},
        "output_csv": out_path,
    }
    print(json.dumps(summary, indent=2, default=str))
    with open(os.path.join(cfg["_resolved_paths"]["evidence_packages"], f"{run_id}_proxy_resolution_summary.json"), "w") as f:
        json.dump(summary, f, indent=2, default=str)


if __name__ == "__main__":
    main()
