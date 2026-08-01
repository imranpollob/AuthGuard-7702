"""Applies the shared evidence pipeline (evidence_pipeline.py) to all items in the Gold-Dev
or Gold-Test frozen manifest. Read-only with respect to the manifests themselves -- writes
only under revision_v3/human_eval/{gold_dev,gold_test}_code_evidence/.

Usage:
    python3 revision_v3/experiments/excel_review/enrich_gold_set.py --sample-set gold_dev
    python3 revision_v3/experiments/excel_review/enrich_gold_set.py --sample-set gold_test
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evidence_pipeline as ep  # noqa: E402

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
HUMAN_EVAL_DIR = os.path.join(REPO_ROOT, "revision_v3", "human_eval")

MANIFESTS = {
    "gold_dev": "gold_dev_manifest.csv",
    "gold_test": "gold_test_manifest.csv",
}
EXPECTED_N = {"gold_dev": 60, "gold_test": 150}

# Columns that must NEVER be read from the manifest when building LLM-facing evidence.
FORBIDDEN_MANIFEST_COLUMNS = {
    "source_label", "gold_dev_stratum", "ref_model_mean_score", "gold_test_sampling_metadata",
    "pilot_reason",
}


def safe_folder_name(item_id: str) -> str:
    return item_id.replace(":", "_")


def write_item_folder(out_dir: str, item_id: str, chain: str, address: str, result: dict) -> dict:
    folder = os.path.join(out_dir, safe_folder_name(item_id))
    decompiled = os.path.join(folder, "decompiled")
    os.makedirs(decompiled, exist_ok=True)

    with open(os.path.join(folder, "verification_status.json"), "w") as f:
        json.dump(result["verification"], f, indent=2, default=str)

    analysis = result["analysis"]
    with open(os.path.join(decompiled, "disassembly.txt"), "w") as f:
        f.write("\n".join(analysis["disassembly"]))
    with open(os.path.join(decompiled, "functions.json"), "w") as f:
        json.dump({"dispatched_functions": analysis["functions"],
                   "fallback_selector_candidates": analysis["fallback_selector_candidates"]}, f, indent=2)
    with open(os.path.join(decompiled, "storage.json"), "w") as f:
        json.dump(analysis["storage"], f, indent=2)
    with open(os.path.join(decompiled, "constants.json"), "w") as f:
        json.dump(analysis["address_constants"], f, indent=2)
    with open(os.path.join(decompiled, "strings.txt"), "w") as f:
        f.write("\n".join(analysis["ascii_strings"]))
    with open(os.path.join(decompiled, "guard_trace.json"), "w") as f:
        json.dump(result["guard_trace"], f, indent=2)

    readme = [
        f"# Code evidence for {chain}:{address}",
        "",
        f"Verified source: {'YES' if result['verification'].get('verified') else 'NO'} "
        "(checked Sourcify v2 + Blockscout v2, both keyless, both queried live).",
        f"Runtime bytecode: {analysis['runtime_bytecode_length_bytes']} bytes, "
        f"{analysis['opcode_count']} decoded instructions.",
        f"Dispatched function selectors: {len(analysis['functions'])}.",
        f"Guard tracer overall status: {result['guard_trace']['overall_status']}.",
        f"DELEGATECALL present: {analysis['has_delegatecall']}. "
        f"SELFDESTRUCT present: {analysis['has_selfdestruct']}. "
        f"CREATE/CREATE2 present: {analysis['has_create']}.",
    ]
    if result.get("implementation"):
        readme.append(f"Storage-resolved address ({result['implementation']['slot_used']}): "
                       f"{result['implementation']['implementation_address']}")
    with open(os.path.join(folder, "README.md"), "w") as f:
        f.write("\n".join(readme) + "\n")

    return {
        "item_id": item_id, "chain": chain, "address": address,
        "verified": result["verification"]["verified"],
        "source_provider": (
            "sourcify" if result["verification"]["sourcify"]["verified"]
            else "blockscout" if result["verification"]["blockscout"]["verified"] else ""
        ),
        "contract_name": (result["verification"]["blockscout"].get("raw") or {}).get("name") or "",
        "compiler_version": (result["verification"]["blockscout"].get("raw") or {}).get("compiler_version") or "",
        "runtime_bytecode_length_bytes": analysis["runtime_bytecode_length_bytes"],
        "n_dispatched_functions": len(analysis["functions"]),
        "has_delegatecall": analysis["has_delegatecall"],
        "has_selfdestruct": analysis["has_selfdestruct"],
        "has_create": analysis["has_create"],
        "implementation_resolved": bool(result.get("implementation")),
        "implementation_address": (result.get("implementation") or {}).get("implementation_address", ""),
        "guard_trace_overall_status": result["guard_trace"]["overall_status"],
        "any_sensitive_open": result["guard_trace"]["any_sensitive_open"],
        "any_ambiguous": result["guard_trace"]["any_ambiguous"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-set", required=True, choices=list(MANIFESTS))
    parser.add_argument("--limit", type=int, default=None, help="debug: process only first N rows")
    args = parser.parse_args()

    manifest_path = os.path.join(HUMAN_EVAL_DIR, MANIFESTS[args.sample_set])
    out_dir = os.path.join(HUMAN_EVAL_DIR, f"{args.sample_set}_code_evidence")
    os.makedirs(out_dir, exist_ok=True)

    ep.init_selector_cache(os.path.join(out_dir, "_selector_cache.json"))

    with open(manifest_path, newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == EXPECTED_N[args.sample_set], (
        f"expected {EXPECTED_N[args.sample_set]} {args.sample_set} items, found {len(rows)}"
    )
    if args.limit:
        rows = rows[: args.limit]

    inventory = []
    manifest_out = {"items": {}, "shared_implementations": {}}
    implementation_cache: dict[str, dict] = {}

    for i, row in enumerate(rows):
        item_id, chain, address = row["item_id"], row["chain"], row["address"]
        print(f"[{i+1}/{len(rows)}] {item_id}", flush=True)
        bytecode_hex = row["runtime_bytecode"]

        result = ep.enrich_item(chain, address, bytecode_hex)
        inv_row = write_item_folder(out_dir, item_id, chain, address, result)
        inventory.append(inv_row)
        manifest_out["items"][item_id] = {
            "chain": chain, "address": address,
            "verification": result["verification"],
            "guard_trace_summary": {
                "overall_status": result["guard_trace"]["overall_status"],
                "any_sensitive_open": result["guard_trace"]["any_sensitive_open"],
                "any_ambiguous": result["guard_trace"]["any_ambiguous"],
                "per_function": [
                    {k: v for k, v in fn.items() if k in
                     ("selector", "resolved_signature", "bytecode_offset", "guard_status",
                      "guard_opcode", "guard_constant", "state_mutability", "arguments")}
                    for fn in result["guard_trace"]["per_function"]
                ],
            },
            "structural": {
                "n_dispatched_functions": len(result["analysis"]["functions"]),
                "has_delegatecall": result["analysis"]["has_delegatecall"],
                "has_selfdestruct": result["analysis"]["has_selfdestruct"],
                "has_create": result["analysis"]["has_create"],
                "runtime_bytecode_length_bytes": result["analysis"]["runtime_bytecode_length_bytes"],
            },
            "implementation": result.get("implementation"),
        }

        impl = result.get("implementation")
        if impl and impl["implementation_address"] not in implementation_cache:
            impl_addr = impl["implementation_address"]
            print(f"    resolving implementation {impl_addr} on {chain}", flush=True)
            impl_code = ep.get_code(chain, impl_addr)
            if impl_code and impl_code != "0x":
                impl_verification = {
                    "sourcify": ep.check_sourcify(chain, impl_addr),
                    "blockscout": ep.check_blockscout(chain, impl_addr),
                }
                impl_verification["verified"] = (
                    impl_verification["sourcify"]["verified"] or impl_verification["blockscout"]["verified"]
                )
                impl_analysis = ep.analyze_bytecode(impl_code)
                impl_guard_trace = ep.trace_guards(impl_analysis)
                impl_result = {"verification": impl_verification, "analysis": impl_analysis,
                                "guard_trace": impl_guard_trace, "implementation": None}
                shared_dir = os.path.join(out_dir, "_shared_implementations")
                write_item_folder(shared_dir, impl_addr, chain, impl_addr, impl_result)
                implementation_cache[impl_addr] = {
                    "chain": chain, "verified": impl_verification["verified"],
                    "code_bytes": (len(impl_code) - 2) // 2,
                    "n_dispatched_functions": len(impl_analysis["functions"]),
                }
            else:
                implementation_cache[impl_addr] = {"chain": chain, "code_bytes": 0}
        ep.save_selector_cache()

    manifest_out["shared_implementations"] = implementation_cache

    with open(os.path.join(out_dir, "evidence_manifest.json"), "w") as f:
        json.dump(manifest_out, f, indent=2, default=str)

    inv_columns = ["item_id", "chain", "address", "verified", "source_provider", "contract_name",
                   "compiler_version", "runtime_bytecode_length_bytes", "n_dispatched_functions",
                   "has_delegatecall", "has_selfdestruct", "has_create", "implementation_resolved",
                   "implementation_address", "guard_trace_overall_status", "any_sensitive_open",
                   "any_ambiguous"]
    with open(os.path.join(out_dir, "source_inventory.csv"), "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=inv_columns)
        writer.writeheader()
        for row in inventory:
            writer.writerow(row)

    print(f"\nDone. {len(inventory)} items -> {out_dir}")
    print(f"verified: {sum(1 for r in inventory if r['verified'])}/{len(inventory)}")
    print(f"guard_trace overall_status distribution:")
    from collections import Counter
    print(" ", Counter(r["guard_trace_overall_status"] for r in inventory))
    return 0


if __name__ == "__main__":
    sys.exit(main())
