"""Two remaining evaluations under the Opus 5 label source.

1. Legitimate-control evaluation, per provenance category. Part 13 of the previous pass
   verified the 30 documented deployments but never evaluated model predictions separately per
   category — a gap that report itself recorded as a follow-up. Closed here.

2. Temporal sample re-labeled with the Opus 5 framework, from the bytecode already collected
   in the previous pass's temporal code-evidence directory (no new network calls).

Both write only under results/llm_provisional_opus5/.
"""

from __future__ import annotations

import csv
import glob
import json
import os
import sys

import numpy as np
import torch

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
V3 = os.path.join(REPO_ROOT, "revision_v3")
sys.path.insert(0, os.path.join(V3, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import evmole  # noqa: E402

from analysis.delegation_context import build_delegation_context_graph  # noqa: E402
from evaluation.model_runtime import score_dataset_provenance_aware  # noqa: E402
from evm_cfg import analyze_fallback, analyze_function, static_opcode_census  # noqa: E402
from opus5_label import decide  # noqa: E402

csv.field_size_limit(10 ** 9)
OUT = os.path.join(V3, "results", "llm_provisional_opus5")
BANNER = {"LABEL_SOURCE": "LLM_PROVISIONAL_OPUS5",
          "STATIC_ANALYZER_EVIDENCE": "VISIBLE",
          "STATUS": "PROVISIONAL_PENDING_HUMAN_REVIEW",
          "WATERMARK": "PROVISIONAL — OPUS 5 LABELS WITH STATIC-ANALYZER EVIDENCE"}


def cfg_for(bytecode_hex: str) -> dict:
    code = bytes.fromhex(bytecode_hex[2:] if bytecode_hex.startswith("0x") else bytecode_hex)
    if not code:
        return {"error": "no runtime code"}
    info = evmole.contract_info(code, selectors=True, arguments=True, state_mutability=True)
    funcs = info.functions or []
    per_fn, reached = [], set()
    for f in funcs:
        r = analyze_function(code, f.bytecode_offset, selector=int(f.selector, 16))
        reached |= {h["pc"] for h in r["reachable_sensitive"]}
        per_fn.append({"selector": "0x" + f.selector, "entry_pc": f.bytecode_offset,
                       "arguments": getattr(f, "arguments", None),
                       "state_mutability": getattr(f, "state_mutability", None),
                       "resolved_signature": None,
                       "guard_status": r["status"],
                       "analysis_incomplete": r["analysis_incomplete"],
                       "unresolved_dynamic_jumps": r["unresolved_dynamic_jumps"],
                       "stack_underflows": r["stack_underflows"],
                       "reaches_ecrecover": r["reaches_ecrecover"],
                       "guards": r["guards"][:6],
                       "unguarded_sensitive": r["unguarded_sensitive"][:8],
                       "unguarded_even_by_storage": r["unguarded_even_by_storage"][:8],
                       "n_reachable_sensitive": len(r["reachable_sensitive"])})
    fb = analyze_fallback(code, {int(f.selector, 16) for f in funcs})
    if not funcs:
        r = analyze_function(code, 0)
        reached |= {h["pc"] for h in r["reachable_sensitive"]}
        per_fn.append({"selector": "<no dispatcher recovered>", "entry_pc": 0,
                       "resolved_signature": None, "guard_status": r["status"],
                       "analysis_incomplete": r["analysis_incomplete"],
                       "unresolved_dynamic_jumps": r["unresolved_dynamic_jumps"],
                       "stack_underflows": r["stack_underflows"],
                       "reaches_ecrecover": r["reaches_ecrecover"],
                       "guards": r["guards"][:6],
                       "unguarded_sensitive": r["unguarded_sensitive"][:8],
                       "unguarded_even_by_storage": r["unguarded_even_by_storage"][:8],
                       "n_reachable_sensitive": len(r["reachable_sensitive"])})
    census = static_opcode_census(code)
    for p in ("receive_path", "fallback_path"):
        reached |= {c["pc"] for c in fb.get(p, {}).get("calls", [])}
    unreached = {op: [pc for pc in pcs if pc not in reached]
                 for op, pcs in census["sites"].items()
                 if op in ("CALL", "DELEGATECALL", "CREATE", "CREATE2", "SELFDESTRUCT")}
    unreached = {k: v for k, v in unreached.items() if v}
    return {"n_functions": len(funcs), "per_function": per_fn,
            "fallback_receive_paths": fb, "static_opcode_census": census["counts"],
            "sensitive_opcodes_never_reached_by_analysis": unreached}


def make_dossier(item_id, chain, address, bytecode_hex, extra_identity=None) -> dict:
    cfg = cfg_for(bytecode_hex)
    return {
        "item_id": item_id,
        "identity": {"chain": chain, "address": address, "family_id": None,
                     "runtime_size_bytes": len(bytecode_hex) // 2,
                     "documented_project": extra_identity},
        "source_and_code_evidence": {"verified_source": None, "strings": "",
                                     "live_storage_reads": None},
        "cfg_guard_analysis_opus5": cfg,
        # ``address`` is the delegate contract, not the authorizing EOA.
        "delegation_context_risk_graph": build_delegation_context_graph(cfg).to_dict(),
        "source_static_analyzer_evidence": {
            "source_rule_label": "unflagged", "n_rule_tuples": 0,
            "rule_firing_tuples_for_this_address": [],
            "source_rule_name": "not evaluated for this item (outside the USENIX analysed pool)",
            "local_reproduction_of_the_rules_question": None},
        "previous_llm_provisional_review": {"label": None},
        "previous_linear_window_guard_tracer": {"overall_status": None},
    }


# ---------------------------------------------------------------- controls ---------------

def evaluate_legitimate_controls() -> dict:
    path = os.path.join(V3, "external_controls", "verified_legitimate_controls.csv")
    with open(path) as f:
        rows = list(csv.DictReader(f))
    cache = {}
    for p in glob.glob(os.path.join(V3, "external_controls", "bytecode_cache", "*.hex")):
        key = os.path.basename(p).rsplit(".", 1)[0].lower()
        cache[key] = open(p).read().strip()

    items, missing = [], []
    for r in rows:
        addr = r["address"].lower()
        hexs = next((v for k, v in cache.items() if addr[2:] in k), None)
        if not hexs:
            missing.append(r["address"])
            continue
        items.append((r, hexs))
    if not items:
        return {"error": "no cached bytecode for any control", "n_rows": len(rows)}

    bytecodes = [h if h.startswith("0x") else "0x" + h for _, h in items]
    family_ids = [r.get("bytecode_family") or None for r, _ in items]
    scored = score_dataset_provenance_aware(
        "authguard_sequence_dense", bytecodes, family_ids
    )
    per_seed = scored["scores_by_seed"]
    probs = np.mean(np.stack([per_seed[s] for s in sorted(per_seed)]), axis=0)

    by_cat = {}
    per_item = []
    for i, ((r, _), p) in enumerate(zip(items, probs)):
        cat = (f'{r.get("category") or "UNCATEGORIZED"} '
               f'(provenance {r.get("provenance_confidence") or "?"})')
        flagged = bool(scored["decision_fraction"][i] >= 0.5)
        by_cat.setdefault(cat, {"n": 0, "flagged": 0, "projects": set()})
        by_cat[cat]["n"] += 1
        by_cat[cat]["flagged"] += int(flagged)
        by_cat[cat]["projects"].add(r.get("project"))
        per_item.append({"project": r.get("project"), "chain": r.get("chain"),
                         "address": r.get("address"), "category": cat,
                         "authguard_probability": float(p),
                         "checkpoint_positive_fraction": float(scored["decision_fraction"][i]),
                         "score_provenance": scored["score_source_by_item"][i],
                         "flagged_at_frozen_threshold": flagged,
                         "runtime_source_match": r.get("runtime_source_match"),
                         "verified_source": r.get("verified_source")})
    for c in by_cat.values():
        c["projects"] = sorted(x for x in c["projects"] if x)
        c["false_positive_rate_on_this_category"] = c["flagged"] / c["n"] if c["n"] else None
    return {**BANNER,
            "operating_decision": "flagged when >=50% of eligible checkpoints are positive",
            "checkpoint_decision_rule": scored["decision_rule"],
            "n_canonical_family_items": scored["n_canonical_family_items"],
            "n_canonical_non_primary_items": scored["n_canonical_non_primary_items"],
            "n_verified_external_items": scored["n_verified_external_items"],
            "threshold_provenance": "each checkpoint's own validation-derived 5%-FPR "
                                    "threshold; never re-fit on the control set",
            "n_controls_scored": len(items),
            "n_controls_without_cached_bytecode": len(missing),
            "addresses_without_cached_bytecode": missing,
            "per_category": by_cat, "per_item": per_item,
            "interpretation": (
                "These are documented, real-world EIP-7702 delegate deployments. Any item "
                "flagged here is a false positive with respect to its documentation status — "
                "but note the categories differ in evidence strength, which is exactly why they "
                "are reported separately rather than pooled.")}


# ---------------------------------------------------------------- temporal ---------------

def relabel_temporal() -> dict:
    ev_root = os.path.join(V3, "results", "llm_provisional", "temporal", "code_evidence")
    prev_path = os.path.join(V3, "results", "llm_provisional", "temporal", "temporal_labels.json")
    prev = {}
    if os.path.exists(prev_path):
        prev = {r["item_id"]: r for r in json.load(open(prev_path))["records"]}

    records, no_bytecode = [], []
    for d in sorted(glob.glob(os.path.join(ev_root, "*"))):
        if not os.path.isdir(d):
            continue
        name = os.path.basename(d)
        if name.startswith("_"):
            continue
        chain, _, address = name.partition("_")
        bc_path = os.path.join(d, "runtime_bytecode.hex")
        hexs = None
        if os.path.exists(bc_path):
            hexs = open(bc_path).read().strip()
        else:
            dis = os.path.join(d, "decompiled", "bytecode.hex")
            if os.path.exists(dis):
                hexs = open(dis).read().strip()
        if not hexs:
            no_bytecode.append(f"{chain}:{address}")
            continue
        item_id = f"{chain}:{address}"
        doss = make_dossier(item_id, chain, address, hexs)
        res = decide(doss)
        records.append({
            "item_id": item_id, "chain": chain, "address": address,
            "opus5_provisional_label": res["label"],
            "reason_category": res["reason"], "opus5_confidence": res["confidence"],
            "unsafe_support_class": res["support"] if res["label"] == "UNSAFE" else "",
            "concrete_unsafe_paths": "; ".join(res.get("unsafe_paths", [])) or "none identified",
            "concrete_safe_controls": "; ".join(res.get("safe_controls", [])) or "none identified",
            "unresolved_questions": "; ".join(res.get("unresolved", [])) or "none identified",
            "previous_llm_provisional_label": prev.get(item_id, {}).get("llm_provisional_label", ""),
            "human_final_label": "", "human_review_status": "NOT_REVIEWED",
        })
    dist = {}
    for r in records:
        dist[r["opus5_provisional_label"]] = dist.get(r["opus5_provisional_label"], 0) + 1
    status = "RELABELED_UNDER_OPUS5" if records else "NOT_REGENERATED_NO_LOCAL_BYTECODE"
    return {**BANNER, "status": status, "n_items": len(records),
            "n_items_without_locally_cached_bytecode": len(no_bytecode),
            "items_without_locally_cached_bytecode": no_bytecode[:50],
            "label_distribution": dist, "records": records,
            "caveat": (
                "Temporal collection is itself incomplete (see "
                "TEMPORAL_COLLECTION_FINAL_STATUS.md) and the sample is single-class "
                "dominated, so no AUPRC/AUROC is computed from it. "
                + ("The previous pass's temporal code-evidence directories retain only derived "
                   "artifacts (functions.json, guard_trace.json) and not the raw runtime "
                   "bytecode, so the temporal items could NOT be re-labeled under the Opus 5 "
                   "framework without re-fetching from chain. They are therefore left at the "
                   "previous pass's labels, which were produced WITHOUT static-analyzer "
                   "evidence and from the superseded linear-window tracer, and must not be "
                   "mixed with the Opus 5 label set."
                   if not records else ""))}


def main() -> int:
    os.makedirs(os.path.join(OUT, "legitimate_controls"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "temporal"), exist_ok=True)

    print("[controls] evaluating documented legitimate controls per provenance category...")
    c = evaluate_legitimate_controls()
    with open(os.path.join(OUT, "legitimate_controls", "control_evaluation.json"), "w") as f:
        json.dump(c, f, indent=1)
    if "per_category" in c:
        for cat, v in c["per_category"].items():
            print(f"  {cat}: {v['flagged']}/{v['n']} flagged "
                  f"(FPR {v['false_positive_rate_on_this_category']:.1%})")

    print("[temporal] re-labeling temporal sample with the Opus 5 framework...")
    t = relabel_temporal()
    with open(os.path.join(OUT, "temporal", "temporal_labels_opus5.json"), "w") as f:
        json.dump(t, f, indent=1)
    print(f"  {t['n_items']} items -> {t['label_distribution']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
