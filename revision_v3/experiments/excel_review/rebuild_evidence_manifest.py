"""Rebuilds evidence_manifest.json for a sample set from the already-saved per-item
verification_status.json / decompiled/{functions.json,guard_trace.json} files, without
re-running the network-heavy enrichment pass. Used to recover from the state_mutability
aggregation bug fixed in enrich_gold_set.py without wasting the already-collected evidence.

Usage:
    python3 revision_v3/experiments/excel_review/rebuild_evidence_manifest.py --sample-set gold_dev
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
HUMAN_EVAL_DIR = os.path.join(REPO_ROOT, "revision_v3", "human_eval")

MANIFESTS = {"gold_dev": "gold_dev_manifest.csv", "gold_test": "gold_test_manifest.csv"}
EVIDENCE_DIRS = {"gold_dev": "gold_dev_code_evidence", "gold_test": "gold_test_code_evidence"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-set", required=True, choices=list(MANIFESTS))
    args = parser.parse_args()

    manifest_path = os.path.join(HUMAN_EVAL_DIR, MANIFESTS[args.sample_set])
    evidence_dir = os.path.join(HUMAN_EVAL_DIR, EVIDENCE_DIRS[args.sample_set])

    with open(manifest_path, newline="") as f:
        rows = list(csv.DictReader(f))

    items = {}
    missing = []
    for row in rows:
        item_id, chain, address = row["item_id"], row["chain"], row["address"]
        folder = os.path.join(evidence_dir, item_id.replace(":", "_"))
        if not os.path.isdir(folder):
            missing.append(item_id)
            continue
        with open(os.path.join(folder, "verification_status.json")) as f:
            verification = json.load(f)
        with open(os.path.join(folder, "decompiled", "functions.json")) as f:
            functions = json.load(f)
        with open(os.path.join(folder, "decompiled", "guard_trace.json")) as f:
            guard_trace = json.load(f)
        with open(os.path.join(folder, "decompiled", "storage.json")) as f:
            storage = json.load(f)

        readme_path = os.path.join(folder, "README.md")
        with open(readme_path) as f:
            readme = f.read()
        has_delegatecall = "DELEGATECALL present: True" in readme
        has_selfdestruct = "SELFDESTRUCT present: True" in readme
        has_create = "CREATE/CREATE2 present: True" in readme
        n_bytes = None
        for line in readme.splitlines():
            if line.startswith("Runtime bytecode:"):
                n_bytes = int(line.split(":")[1].strip().split(" ")[0])

        implementation = None
        for line in readme.splitlines():
            if line.startswith("Storage-resolved address"):
                slot_used = line.split("(")[1].split(")")[0]
                addr = line.split(": ")[1].strip()
                implementation = {"slot_used": slot_used, "implementation_address": addr}

        items[item_id] = {
            "chain": chain, "address": address,
            "verification": verification,
            "guard_trace_summary": {
                "overall_status": guard_trace["overall_status"],
                "any_sensitive_open": guard_trace["any_sensitive_open"],
                "any_ambiguous": guard_trace["any_ambiguous"],
                "per_function": [
                    {k: v for k, v in fn.items() if k in
                     ("selector", "resolved_signature", "bytecode_offset", "guard_status",
                      "guard_opcode", "guard_constant", "state_mutability", "arguments")}
                    for fn in guard_trace["per_function"]
                ],
            },
            "structural": {
                "n_dispatched_functions": len(functions["dispatched_functions"]),
                "has_delegatecall": has_delegatecall,
                "has_selfdestruct": has_selfdestruct,
                "has_create": has_create,
                "runtime_bytecode_length_bytes": n_bytes,
            },
            "implementation": implementation,
        }

    shared_dir = os.path.join(evidence_dir, "_shared_implementations")
    shared_impls = {}
    if os.path.isdir(shared_dir):
        for name in os.listdir(shared_dir):
            impl_folder = os.path.join(shared_dir, name)
            if not os.path.isdir(impl_folder):
                continue
            try:
                with open(os.path.join(impl_folder, "verification_status.json")) as f:
                    v = json.load(f)
                shared_impls[name] = {"verified": v["verified"]}
            except FileNotFoundError:
                pass

    out = {"items": items, "shared_implementations": shared_impls}
    out_path = os.path.join(evidence_dir, "evidence_manifest.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2, default=str)

    print(f"Rebuilt {out_path}: {len(items)} items ({len(missing)} missing folders: {missing})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
