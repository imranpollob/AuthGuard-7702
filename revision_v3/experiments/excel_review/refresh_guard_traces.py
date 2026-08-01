"""Re-runs analyze_bytecode + trace_guards LOCALLY (no network calls beyond the already-warm
4byte.directory cache) for every already-enriched item in a sample set, overwriting only
decompiled/guard_trace.json. Used to apply a guard-tracer bugfix (evidence_pipeline.py) to
already-collected evidence without repeating the network-heavy verified-source/RPC calls.

Usage:
    python3 revision_v3/experiments/excel_review/refresh_guard_traces.py --sample-set gold_dev
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
MANIFESTS = {"gold_dev": "gold_dev_manifest.csv", "gold_test": "gold_test_manifest.csv",
             "pilot": "pilot_manifest.csv"}
EVIDENCE_DIRS = {"gold_dev": "gold_dev_code_evidence", "gold_test": "gold_test_code_evidence",
                  "pilot": "pilot_code_evidence"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-set", required=True, choices=list(MANIFESTS))
    args = parser.parse_args()

    manifest_path = os.path.join(HUMAN_EVAL_DIR, MANIFESTS[args.sample_set])
    evidence_dir = os.path.join(HUMAN_EVAL_DIR, EVIDENCE_DIRS[args.sample_set])
    ep.init_selector_cache(os.path.join(evidence_dir, "_selector_cache.json"))

    with open(manifest_path, newline="") as f:
        rows = list(csv.DictReader(f))

    n_done, n_skipped = 0, 0
    for row in rows:
        item_id = row["item_id"]
        folder = os.path.join(evidence_dir, item_id.replace(":", "_"))
        guard_path = os.path.join(folder, "decompiled", "guard_trace.json")
        if not os.path.exists(guard_path):
            n_skipped += 1
            continue
        analysis = ep.analyze_bytecode(row["runtime_bytecode"])
        guard_trace = ep.trace_guards(analysis)
        with open(guard_path, "w") as f:
            json.dump(guard_trace, f, indent=2)
        n_done += 1
    ep.save_selector_cache()

    # Also refresh any shared-implementation guard traces (those need the implementation's own
    # bytecode; recomputing requires re-reading its already-stored disassembly rather than
    # re-fetching on-chain code, since evmole's disassembly text is deterministic from the
    # already-known runtime bytecode we saved). Re-derive from the saved disassembly.txt by
    # reconstructing raw hex is not straightforward, so instead re-fetch via eth_getCode
    # (cheap, single RPC call, no source/decompile-provider cost) for shared implementations.
    shared_dir = os.path.join(evidence_dir, "_shared_implementations")
    n_shared = 0
    if os.path.isdir(shared_dir):
        # chain is not stored standalone; infer from evidence_manifest.json's shared_implementations
        manifest_json_path = os.path.join(evidence_dir, "evidence_manifest.json")
        chain_by_addr = {}
        if os.path.exists(manifest_json_path):
            with open(manifest_json_path) as f:
                mj = json.load(f)
            for addr, info in mj.get("shared_implementations", {}).items():
                if "chain" in info:
                    chain_by_addr[addr] = info["chain"]
        for name in os.listdir(shared_dir):
            impl_folder = os.path.join(shared_dir, name)
            guard_path = os.path.join(impl_folder, "decompiled", "guard_trace.json")
            if not os.path.isdir(impl_folder) or not os.path.exists(guard_path):
                continue
            chain = chain_by_addr.get(name)
            if not chain:
                continue
            code = ep.get_code(chain, name)
            if not code or code == "0x":
                continue
            analysis = ep.analyze_bytecode(code)
            guard_trace = ep.trace_guards(analysis)
            with open(guard_path, "w") as f:
                json.dump(guard_trace, f, indent=2)
            n_shared += 1

    print(f"[{args.sample_set}] refreshed {n_done} item guard traces "
          f"({n_skipped} skipped, no existing evidence), {n_shared} shared implementations")
    return 0


if __name__ == "__main__":
    sys.exit(main())
