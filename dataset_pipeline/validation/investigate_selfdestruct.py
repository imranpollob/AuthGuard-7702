"""Task 2: determine what the apparent SELFDESTRUCT bytes in the R1-flagged contracts actually
are -- executable + reachable code, executable but unreachable, Solidity CBOR metadata, PUSH
immediate data, or a linear-sweep artifact.

Method (all local, no network):
  1. Validated Solidity CBOR metadata trailer (revision_v3/src/analysis/solidity_metadata.py)
     -- strict: a suffix is only treated as metadata when it decodes as a Solidity metadata map
     AND does not contain executable JUMPDESTs / fallthrough.
  2. Correct instruction-boundary disassembly of the executable region: any 0xFF byte that is
     not at an instruction boundary is PUSH immediate data, not an opcode.
  3. Reachability: the symbolic-stack CFG traversal (revision_v3/experiments/opus5_labeling/
     evm_cfg.py Analyzer) from pc=0 -- does any explored state actually arrive at that pc?
  4. Guard dominance: if reachable, is it reachable on a path that never passes a caller/
     signature guard (`unguarded`), which is what "insufficiently protected" would require.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pandas as pd  # noqa: E402

from lib.config import load_config  # noqa: E402
from lib.repo_paths import REPO_ROOT, add_revision_v3_src_to_path  # noqa: E402

add_revision_v3_src_to_path()
sys.path.insert(0, os.path.join(REPO_ROOT, "revision_v3", "experiments", "opus5_labeling"))

from analysis.solidity_metadata import validated_solidity_metadata_start  # noqa: E402
from evm_cfg import Analyzer, disassemble, static_opcode_census  # noqa: E402


def classify_selfdestruct(runtime_hex: str) -> dict:
    code = bytes.fromhex(runtime_hex.lower().removeprefix("0x"))
    total_ff = code.count(0xFF)

    metadata_start = validated_solidity_metadata_start(code)
    census = static_opcode_census(code)
    executable_end = census["executable_bytes"]

    # every 0xFF that sits at a real instruction boundary in the whole code
    all_instructions = disassemble(code)
    boundary_pcs = {pc for pc, name, _ in all_instructions if name == "SELFDESTRUCT"}
    # ... and those within the executable (non-metadata) region
    exec_boundary_pcs = {pc for pc in boundary_pcs if pc < executable_end}
    in_metadata = {pc for pc in boundary_pcs if pc >= metadata_start}

    reachable_pcs, unguarded_pcs = set(), set()
    traversal_incomplete = None
    if exec_boundary_pcs:
        analyzer = Analyzer(code)
        full = analyzer.traverse(0, stop_at_guard_kinds=set())
        no_strong = analyzer.traverse(0, stop_at_guard_kinds={"strong"})
        reachable_pcs = {pc for pc, hit in full.sensitive.items() if hit.op == "SELFDESTRUCT"}
        unguarded_pcs = {pc for pc, hit in no_strong.sensitive.items() if hit.op == "SELFDESTRUCT"}
        traversal_incomplete = bool(
            full.hit_state_cap or full.hit_per_pc_cap
            or full.unresolved_jumps > 0 or full.stack_underflows > 0
        )

    if reachable_pcs and unguarded_pcs:
        verdict = "REACHABLE_UNGUARDED"
    elif reachable_pcs:
        verdict = "REACHABLE_GUARD_DOMINATED"
    elif exec_boundary_pcs:
        verdict = "EXECUTABLE_REGION_BUT_UNREACHABLE"
    elif in_metadata:
        verdict = "SOLIDITY_CBOR_METADATA"
    elif boundary_pcs:
        verdict = "NON_EXECUTABLE_TRAILING_DATA"
    else:
        verdict = "PUSH_IMMEDIATE_DATA_NOT_AN_OPCODE"

    return {
        "code_bytes": len(code),
        "n_raw_0xff_bytes": total_ff,
        "n_selfdestruct_at_instruction_boundary": len(boundary_pcs),
        "n_selfdestruct_in_executable_region": len(exec_boundary_pcs),
        "n_selfdestruct_in_validated_metadata": len(in_metadata),
        "n_selfdestruct_reachable": len(reachable_pcs),
        "n_selfdestruct_reachable_without_caller_guard": len(unguarded_pcs),
        "metadata_recognized": census["metadata_recognized"],
        "metadata_bytes": census["metadata_bytes"],
        "metadata_rejection_reason": census["metadata_rejection_reason"],
        "traversal_incomplete": traversal_incomplete,
        "verdict": verdict,
    }


def main():
    cfg = load_config()
    run_id = cfg["run_id"]
    reviews = pd.read_csv(os.path.join(cfg["_resolved_paths"]["llm_reviews"], f"{run_id}_review_index.csv"))
    r1 = reviews[reviews["proposed_label"] == "R1"]
    families = pd.read_csv(os.path.join(cfg["_resolved_paths"]["bytecode_families"], f"{run_id}_family_assignment.csv"))
    lookup = families.set_index("delegate_address")["runtime_bytecode"].to_dict()

    rows = []
    for _, r in r1.iterrows():
        addr = r["address"]
        result = classify_selfdestruct(lookup[addr])
        result["address"] = addr
        rows.append(result)
        print(f"{addr}  {result['verdict']:<38} "
              f"boundary={result['n_selfdestruct_at_instruction_boundary']} "
              f"exec={result['n_selfdestruct_in_executable_region']} "
              f"reach={result['n_selfdestruct_reachable']} "
              f"unguarded={result['n_selfdestruct_reachable_without_caller_guard']}", flush=True)

    out = pd.DataFrame(rows)
    out_csv = os.path.join(REPO_ROOT, "reports", f"selfdestruct_investigation_{run_id}.csv")
    out.to_csv(out_csv, index=False)
    summary = {
        "n_r1_investigated": len(out),
        "verdict_counts": out["verdict"].value_counts().to_dict(),
        "n_with_any_reachable_selfdestruct": int((out["n_selfdestruct_reachable"] > 0).sum()),
        "n_with_unguarded_reachable_selfdestruct": int((out["n_selfdestruct_reachable_without_caller_guard"] > 0).sum()),
        "output_csv": out_csv,
    }
    print("\n" + json.dumps(summary, indent=2))
    with open(os.path.join(REPO_ROOT, "reports", f"selfdestruct_investigation_{run_id}.json"), "w") as f:
        json.dump(summary, f, indent=2)


if __name__ == "__main__":
    main()
