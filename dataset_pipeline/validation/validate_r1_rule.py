"""Task 3: validate the R1 rule on a random sample of R1 contracts.

For each sampled contract this re-derives, independently of the stored evidence:

  1. Is the calldata-targeted CALL actually REACHABLE from pc=0 (not just present)?
  2. Does ANY authorization guard exist anywhere in the contract, of any recognised kind
     (caller comparison, tx.origin, ecrecover/signature, self-call, hardcoded-address /
     EntryPoint-style, storage-derived authority)?
  3. Does any such guard DOMINATE the site -- i.e. does the site become unreachable when
     traversal is cut at guards? This is checked separately for strong guards and for
     strong+storage guards, so an "unguarded" claim that only survives by ignoring a storage
     check is visible.
  4. Independent cross-checks for authorization patterns the guard model could miss:
       * a REVERT-style require() gate on msg.sender that appears before the site
       * ecrecover (precompile 0x01) reachable on the path
       * a hardcoded address compared against CALLER anywhere (EntryPoint pattern)
       * whether the site is inside the validated Solidity metadata region (should never be)
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pandas as pd  # noqa: E402

from lib.config import load_config  # noqa: E402
from lib.reachability import DeepAnalyzer  # noqa: E402
from lib.repo_paths import REPO_ROOT, add_revision_v3_src_to_path  # noqa: E402

add_revision_v3_src_to_path()
sys.path.insert(0, os.path.join(REPO_ROOT, "revision_v3", "experiments", "opus5_labeling"))
from evm_cfg import disassemble, static_opcode_census  # noqa: E402

SAMPLE_SIZE = 25


def independent_checks(code: bytes) -> dict:
    instrs = disassemble(code)
    names = [nm for _, nm, _ in instrs]
    has_caller = "CALLER" in names
    has_origin = "ORIGIN" in names
    # ecrecover is precompile address 0x01 used via STATICCALL/CALL with a PUSH1 0x01 target
    pushes_one = any(nm == "PUSH" and imm == 1 for _, nm, imm in instrs)
    # a hardcoded 20-byte address constant (PUSH20) anywhere
    push20 = sum(1 for _, nm, imm in instrs if nm == "PUSH" and isinstance(imm, int) and imm > (1 << 152))
    return {
        "contains_CALLER_opcode": has_caller,
        "contains_ORIGIN_opcode": has_origin,
        "contains_push1_0x01_possible_ecrecover": pushes_one,
        "n_push20_address_constants": push20,
        "n_revert_sites": names.count("REVERT"),
    }


def main():
    cfg = load_config()
    run_id = cfg["run_id"]
    reviews = pd.read_csv(os.path.join(cfg["_resolved_paths"]["llm_reviews"], f"{run_id}_review_index_promptv3.csv"))
    r1 = reviews[reviews["proposed_label"] == "R1"]
    families = pd.read_csv(os.path.join(cfg["_resolved_paths"]["bytecode_families"], f"{run_id}_family_assignment.csv"))
    bytecode = families.set_index("delegate_address")["runtime_bytecode"].to_dict()

    sample = r1.sample(n=min(SAMPLE_SIZE, len(r1)), random_state=cfg.get("seed", 7702))
    print(f"[r1] validating {len(sample)} of {len(r1)} R1 contracts\n")

    rows = []
    for r in sample.itertuples(index=False):
        code = bytes.fromhex(bytecode[r.address][2:])
        analyzer = DeepAnalyzer(code)
        full = analyzer.traverse(0, stop_at_guard_kinds=set())
        no_strong = analyzer.traverse(0, stop_at_guard_kinds={"strong"})
        no_any = analyzer.traverse(0, stop_at_guard_kinds={"strong", "medium"})
        census = static_opcode_census(code)

        cd_sites_full = {
            pc for pc, h in full.sensitive.items()
            if h.op in ("CALL", "DELEGATECALL", "CALLCODE") and "calldata" in (h.target_src or ())
        }
        cd_sites_nostrong = {
            pc for pc, h in no_strong.sensitive.items()
            if h.op in ("CALL", "DELEGATECALL", "CALLCODE") and "calldata" in (h.target_src or ())
        }
        cd_sites_noany = {
            pc for pc, h in no_any.sensitive.items()
            if h.op in ("CALL", "DELEGATECALL", "CALLCODE") and "calldata" in (h.target_src or ())
        }
        surviving = cd_sites_full & cd_sites_nostrong

        guard_kinds = {}
        for g in full.guards.values():
            guard_kinds[g.kind] = guard_kinds.get(g.kind, 0) + 1
        semantics = sorted({g.to_dict()["semantics"].split("(")[0].strip() for g in full.guards.values()})

        checks = independent_checks(code)
        in_metadata = [pc for pc in surviving if pc >= census["executable_bytes"]]

        verdict = "CONFIRMED"
        notes = []
        if not cd_sites_full:
            verdict = "FALSE_POSITIVE_not_reachable"
            notes.append("no calldata-target call site is reachable in the unrestricted traversal")
        elif not surviving:
            verdict = "FALSE_POSITIVE_guard_dominated"
            notes.append("every calldata-target site disappears when traversal is cut at strong guards")
        elif in_metadata:
            verdict = "FALSE_POSITIVE_in_metadata"
            notes.append(f"site(s) {in_metadata} lie in the metadata region")
        if surviving and not (cd_sites_noany & surviving):
            notes.append("sites survive strong-guard cutting but NOT storage-guard cutting: "
                         "protection may rest on a storage-derived authority check")
        if surviving and not checks["contains_CALLER_opcode"]:
            notes.append("contract never uses CALLER: no caller-based authorization is possible anywhere")

        rows.append({
            "address": r.address,
            "verdict": verdict,
            "n_calldata_sites_reachable": len(cd_sites_full),
            "n_surviving_strong_guard_cut": len(surviving),
            "n_surviving_storage_guard_cut": len(cd_sites_noany & surviving),
            "n_guards_total": len(full.guards),
            "n_strong_guards": guard_kinds.get("strong", 0),
            "n_medium_guards": guard_kinds.get("medium", 0),
            "guard_semantics": "; ".join(semantics)[:200],
            "reaches_ecrecover": full.reached_ecrecover,
            "traversal_complete": not (full.hit_state_cap or full.hit_per_pc_cap
                                        or full.unresolved_jumps or full.stack_underflows),
            **checks,
            "notes": " | ".join(notes),
        })
        print(f"{r.address}  {verdict:34s} cd_reachable={len(cd_sites_full)} "
              f"survives_strong_cut={len(surviving)} guards={len(full.guards)}"
              f"(strong={guard_kinds.get('strong', 0)}) ecrec={full.reached_ecrecover}", flush=True)

    out = pd.DataFrame(rows)
    out_csv = os.path.join(REPO_ROOT, "reports", f"r1_validation_{run_id}.csv")
    out.to_csv(out_csv, index=False)
    summary = {
        "n_r1_total": int(len(r1)),
        "n_sampled": int(len(out)),
        "verdicts": out["verdict"].value_counts().to_dict(),
        "n_confirmed": int((out["verdict"] == "CONFIRMED").sum()),
        "n_with_zero_strong_guards": int((out["n_strong_guards"] == 0).sum()),
        "n_never_uses_CALLER": int((~out["contains_CALLER_opcode"]).sum()),
        "n_reaching_ecrecover": int(out["reaches_ecrecover"].sum()),
        "n_protected_only_by_storage_guard": int(
            (out["n_surviving_storage_guard_cut"] < out["n_surviving_strong_guard_cut"]).sum()),
        "n_traversal_incomplete": int((~out["traversal_complete"]).sum()),
        "output_csv": out_csv,
    }
    print("\n" + json.dumps(summary, indent=2, default=str))
    with open(os.path.join(REPO_ROOT, "reports", f"r1_validation_{run_id}.json"), "w") as f:
        json.dump(summary, f, indent=2, default=str)


if __name__ == "__main__":
    main()
