"""Task 2/3: add reachability- and guard-aware capability evidence to every evidence package.

Additive: the Stage-4 packages are re-read, a `reachability` block and a top-level
`coverage_status` are added, and the package is rewritten with a bumped generator version. The
Sourcify lookup is not repeated (the Stage-4 result is preserved in-place), so this stage is
offline and re-runnable.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "dataset_pipeline")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pandas as pd  # noqa: E402

from lib.config import load_config  # noqa: E402
from lib.reachability import analyze_reachability  # noqa: E402

GENERATOR_VERSION = "dataset_pipeline.evidence.reachability.v2"


def main():
    cfg = load_config()
    run_id = cfg["run_id"]
    index_path = os.path.join(cfg["_resolved_paths"]["evidence_packages"], f"{run_id}_evidence_index.csv")
    index = pd.read_csv(index_path)
    families = pd.read_csv(os.path.join(cfg["_resolved_paths"]["bytecode_families"], f"{run_id}_family_assignment.csv"))
    bytecode = families.set_index("delegate_address")["runtime_bytecode"].to_dict()

    coverage_rows = []
    for i, r in enumerate(index.itertuples(index=False), start=1):
        with open(r.evidence_path) as f:
            packet = json.load(f)
        is_designator = packet["proxy_evidence"]["is_eip7702_designator"]
        try:
            reach = analyze_reachability(bytecode[r.address], is_designator=is_designator)
        except Exception as e:  # noqa: BLE001
            reach = {
                "coverage_status": "PARTIAL",
                "coverage_reasons": [f"reachability analysis failed: {type(e).__name__}: {e}"],
                "analysis_error": f"{type(e).__name__}: {e}",
            }
        packet["reachability"] = reach
        packet["coverage_status"] = reach["coverage_status"]
        packet["packet_generator_version"] = GENERATOR_VERSION
        with open(r.evidence_path, "w") as f:
            json.dump(packet, f, indent=2, default=str)

        coverage_rows.append({
            "chain": r.chain, "address": r.address,
            "coverage_status": reach["coverage_status"],
            "n_coverage_reasons": len(reach.get("coverage_reasons", [])),
            "has_unguarded_sensitive": bool(reach.get("sensitive_reachable_without_caller_guard")),
            "has_reachable_sensitive": bool(reach.get("sensitive_reachable")),
        })
        if i % 100 == 0:
            print(f"[reach] {i}/{len(index)}", flush=True)

    cov = pd.DataFrame(coverage_rows)
    cov_path = os.path.join(cfg["_resolved_paths"]["evidence_packages"], f"{run_id}_coverage_index.csv")
    cov.to_csv(cov_path, index=False)
    summary = {
        "n_packages": len(cov),
        "coverage_status_counts": cov["coverage_status"].value_counts().to_dict(),
        "n_with_reachable_sensitive": int(cov["has_reachable_sensitive"].sum()),
        "n_with_unguarded_sensitive": int(cov["has_unguarded_sensitive"].sum()),
        "coverage_index_csv": cov_path,
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
