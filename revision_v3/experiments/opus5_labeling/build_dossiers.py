"""Assemble one complete security-evidence dossier per Pilot/Gold-Dev/Gold-Test item.

Each dossier merges every evidence source the labeling instruction asks for:

  A. contract identity   -- chain, address, runtime hash/size, chains sharing the bytecode,
                            documented-project match (from the verified legitimate-control set)
  B. source & code       -- verified-source status (Sourcify/Blockscout, collected live in the
                            previous pass), resolved selectors, embedded address constants,
                            strings, storage layout
  C. proxy/implementation-- DELEGATECALL presence, storage-slot-resolved implementation address
  D. guard evidence      -- the NEW CFG guard-dominance analysis (`evm_cfg.py`), plus the OLD
                            linear-window tracer's verdict for comparison
  E. static-analyzer     -- the source rule label AND its supporting facts: which USENIX
                            `eoa_detect` tuples fired for this address (enclosing function,
                            call statement, inferred callee signature), plus a local
                            reproduction of the rule's reachability question
  F. on-chain            -- storage values read live in the previous pass
  G. prior analysis      -- the previous provisional LLM label (as context to reassess, not copy)

AuthGuard model scores/predictions are deliberately NOT included: `ref_model_mean_score` and
`gold_dev_stratum` are dropped from the manifest read, and no results file is consulted.
"""

from __future__ import annotations

import csv
import json
import os
import sys

import evmole

V3_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
sys.path.insert(0, V3_SRC)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analysis.delegation_context import build_delegation_context_graph  # noqa: E402
from evm_cfg import (SENSITIVE, analyze_fallback, analyze_function,  # noqa: E402
                     static_opcode_census)

csv.field_size_limit(10 ** 9)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO = os.path.dirname(ROOT)
HUMAN_EVAL = os.path.join(ROOT, "human_eval")
OUT_DIR = os.path.join(ROOT, "results", "llm_provisional_opus5", "dossiers")

# Fields that must never reach the labeling step (model outputs, not security evidence).
FORBIDDEN_MANIFEST_FIELDS = {"ref_model_mean_score", "gold_dev_stratum", "pilot_reason"}

SAMPLE_SETS = {
    "pilot": ("pilot_manifest.csv", "pilot_code_evidence"),
    "gold_dev": ("gold_dev_manifest.csv", "gold_dev_code_evidence"),
    "gold_test": ("gold_test_manifest.csv", "gold_test_code_evidence"),
}


def load_source_rule_facts() -> dict:
    """Per-address firing tuples of the USENIX eoa_detect Datalog rule."""
    path = os.path.join(REPO, "USENIX EIP-7702 artifact", "eoa_detect", "detect_result.jsonl")
    facts = {}
    if not os.path.exists(path):
        return facts
    with open(path) as f:
        for line in f:
            line = line.strip().rstrip(",")
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            facts[d["address"].lower()] = d.get("result", [])
    return facts


def load_legitimate_controls() -> dict:
    path = os.path.join(ROOT, "external_controls", "verified_legitimate_controls.csv")
    out = {}
    if not os.path.exists(path):
        return out
    with open(path) as f:
        for r in csv.DictReader(f):
            key = f"{r.get('chain','')}:{r.get('address','').lower()}"
            out[key] = r
            for h in (r.get("runtime_hash_recorded"), r.get("runtime_hash_live")):
                if h:
                    out.setdefault(h.lower().replace("0x", ""), r)
    return out


def load_prev_labels(sample_set: str) -> dict:
    path = os.path.join(ROOT, "results", "llm_provisional", f"{sample_set}_labels.json")
    if not os.path.exists(path):
        return {}
    d = json.load(open(path))
    return {r["item_id"]: r for r in d.get("records", [])}


def read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def read_text(path, limit=4000):
    try:
        with open(path) as f:
            return f.read()[:limit]
    except OSError:
        return None


def cfg_analysis(bytecode_hex: str) -> dict:
    code = bytes.fromhex(bytecode_hex[2:] if bytecode_hex.startswith("0x") else bytecode_hex)
    if not code:
        return {"error": "no runtime code (empty bytecode / delegation designator or revoked)"}
    info = evmole.contract_info(code, selectors=True, arguments=True,
                                state_mutability=True, storage=True)
    funcs = info.functions or []
    selectors = {int(f.selector, 16) for f in funcs}
    per_fn = []
    reached_pcs = set()

    def record(entry_label, entry_pc, r, **extra):
        for h in r["reachable_sensitive"]:
            reached_pcs.add(h["pc"])
        per_fn.append({
            "selector": entry_label,
            "entry_pc": entry_pc,
            "guard_status": r["status"],
            "analysis_incomplete": r["analysis_incomplete"],
            "unresolved_dynamic_jumps": r["unresolved_dynamic_jumps"],
            "stack_underflows": r["stack_underflows"],
            "hit_exploration_cap": r["hit_state_cap"] or r["hit_per_pc_cap"],
            "reaches_ecrecover": r["reaches_ecrecover"],
            "guards": r["guards"][:6],
            "unguarded_sensitive": r["unguarded_sensitive"][:8],
            "unguarded_even_by_storage": r["unguarded_even_by_storage"][:8],
            "n_reachable_sensitive": len(r["reachable_sensitive"]),
            **extra,
        })

    for f in funcs:
        r = analyze_function(code, f.bytecode_offset, selector=int(f.selector, 16))
        record("0x" + f.selector, f.bytecode_offset, r,
               arguments=getattr(f, "arguments", None),
               state_mutability=getattr(f, "state_mutability", None))
    fb = analyze_fallback(code, selectors)
    if not funcs:
        record("<no dispatcher recovered; analysed from pc=0>", 0,
               analyze_function(code, 0))

    # Soundness backstop: sensitive opcodes present in the code that no traversal reached.
    census = static_opcode_census(code)
    for path in ("receive_path", "fallback_path"):
        for c in fb.get(path, {}).get("calls", []):
            reached_pcs.add(c["pc"])
    unreached = {op: [pc for pc in pcs if pc not in reached_pcs]
                 for op, pcs in census["sites"].items() if op in SENSITIVE}
    unreached = {op: pcs for op, pcs in unreached.items() if pcs and op != "SSTORE"}
    storage = []
    for s in (info.storage or []):
        storage.append({"slot": getattr(s, "slot", None), "offset": getattr(s, "offset", None),
                        "type": getattr(s, "type", None), "reads": getattr(s, "reads", None),
                        "writes": getattr(s, "writes", None)})
    return {"n_functions": len(funcs), "per_function": per_fn, "fallback_receive_paths": fb,
            "storage_layout": storage[:20],
            "static_opcode_census": census["counts"],
            "sensitive_opcodes_never_reached_by_analysis": unreached,
            "coverage_warning": (
                "Sensitive opcodes exist in this bytecode that no traversal reached; the "
                "per-function results below are a LOWER BOUND on capability and must not be "
                "read as 'no sensitive operation'." if unreached else None
            )}


def resolve_selector_names(cache: dict, selectors: list) -> dict:
    """Map selectors to signatures using the 4byte cache collected in the previous pass."""
    return {s: cache.get(s) for s in selectors if cache.get(s)}


def build(sample_set: str, selector_cache: dict, rule_facts: dict,
          legit: dict, verbose: bool = True) -> list:
    manifest_name, evidence_dir = SAMPLE_SETS[sample_set]
    manifest_path = os.path.join(HUMAN_EVAL, manifest_name)
    ev_root = os.path.join(HUMAN_EVAL, evidence_dir)
    prev = load_prev_labels(sample_set)

    dossiers = []
    with open(manifest_path) as f:
        rows = list(csv.DictReader(f))

    for i, row in enumerate(rows):
        item_id = row["item_id"]
        chain, address = row["chain"], row["address"].lower()
        key = f"{chain}_{address}"
        item_ev = os.path.join(ev_root, key)

        verification = read_json(os.path.join(item_ev, "verification_status.json"))
        old_trace = read_json(os.path.join(item_ev, "decompiled", "guard_trace.json"))
        constants = read_json(os.path.join(item_ev, "decompiled", "constants.json"))
        storage_live = read_json(os.path.join(item_ev, "decompiled", "storage.json"))
        strings = read_text(os.path.join(item_ev, "decompiled", "strings.txt"), 1500)
        old_functions = read_json(os.path.join(item_ev, "decompiled", "functions.json"))

        cfg = cfg_analysis(row["runtime_bytecode"])
        # The manifest address is the delegate implementation, not necessarily the EOA whose
        # authority is delegated.  Leave authority unknown rather than asserting a false match.
        dcrg = build_delegation_context_graph(cfg)

        # Attach resolved signatures from the previously-collected 4byte cache.
        if "per_function" in cfg:
            for fn in cfg["per_function"]:
                sel = fn.get("selector", "")
                fn["resolved_signature"] = selector_cache.get(sel) or selector_cache.get(sel[2:])

        facts = rule_facts.get(address, [])
        bh = (row.get("bytecode_sha256") or "").lower().replace("0x", "")
        legit_hit = legit.get(f"{chain}:{address}") or legit.get(bh)

        prev_rec = prev.get(item_id, {})
        dossier = {
            "item_id": item_id,
            "sample_set": sample_set,
            "identity": {
                "chain": chain,
                "address": address,
                "runtime_bytecode_sha256": row.get("bytecode_sha256"),
                "runtime_size_bytes": int(row.get("code_bytes") or 0),
                "family_id": row.get("family_id"),
                "chains_sharing_this_exact_bytecode": row.get("all_chains_with_this_bytecode"),
                "explorer": f"https://blockscout.com/ (chain={chain}) address {address}",
                "documented_project": (
                    {k: legit_hit.get(k) for k in
                     ("project", "official_documentation", "official_deployment_registry",
                      "provenance_confidence", "category", "runtime_source_match",
                      "verified_source", "contract_name", "audit_documentation",
                      "authorization_count", "first_observed_eip7702_authorization")
                     if k in legit_hit}
                    if legit_hit else None
                ),
            },
            "source_and_code_evidence": {
                "verified_source": (verification or {}).get("verified"),
                "verification_detail": verification,
                "embedded_address_constants": (
                    constants if isinstance(constants, list)
                    else (constants or {}).get("address_constants")
                ),
                "strings": strings,
                "evmole_storage_layout": cfg.get("storage_layout"),
                "live_storage_reads": storage_live,
            },
            "proxy_and_implementation": {
                "has_delegatecall": any(
                    s.get("op") == "DELEGATECALL"
                    for fn in cfg.get("per_function", [])
                    for s in fn.get("unguarded_sensitive", [])
                ),
                "storage_resolved_implementation": (storage_live or {}),
            },
            "cfg_guard_analysis_opus5": cfg,
            "delegation_context_risk_graph": dcrg.to_dict(),
            "previous_linear_window_guard_tracer": {
                "overall_status": (old_trace or {}).get("overall_status"),
                "note": (old_trace or {}).get("note"),
                "per_function": [
                    {k: v for k, v in fn.items()
                     if k in ("selector", "resolved_signature", "guard_status",
                              "guard_opcode", "guard_constant", "state_mutability")}
                    for fn in (old_trace or {}).get("per_function", [])
                ],
                "known_limitation": (
                    "Linear byte-window scan between dispatch offsets; cannot follow jumps, so "
                    "guards in shared internal helpers, signature checks, and storage-based "
                    "permission checks are invisible to it. Its OPEN means 'no guard pattern in "
                    "the window', not 'no access control'."
                ),
            },
            "source_static_analyzer_evidence": {
                "source_rule_label": "positive" if row.get("source_label") == "1" else "unflagged",
                "source_rule_name": "USENIX eoa_detect AM_Analysis_ExternalCallInfo "
                                    "(Gigahorse/Soufflé): external CALL/DELEGATECALL reachable "
                                    "from a public function; in practice every shipped tuple's "
                                    "enclosing function is receive() or fallback()",
                "rule_firing_tuples_for_this_address": [
                    {"gigahorse_function_id": t[0], "enclosing_function": t[1],
                     "call_statement_id": t[2], "inferred_callee_signature": t[3]}
                    for t in facts
                ],
                "n_rule_tuples": len(facts),
                "rule_models_authorization": False,
                "rule_limitation": (
                    "The rule has no guard/authorization predicate at all. A positive means "
                    "'an external call is reachable from an unauthenticated entry point in the "
                    "decompiled CFG'; it does NOT mean a caller check is absent. Conversely an "
                    "unflagged result only means this particular reachability pattern did not "
                    "fire (or the address was outside the analysed pool / decompilation failed)."
                ),
                "local_reproduction_of_the_rules_question": cfg.get("fallback_receive_paths"),
            },
            "previous_llm_provisional_review": {
                "label": prev_rec.get("llm_provisional_label"),
                "reason_category": prev_rec.get("llm_provisional_reason_category"),
                "confidence": prev_rec.get("llm_provisional_confidence"),
                "concrete_finding": prev_rec.get("concrete_finding"),
                "note": "Generated WITHOUT static-analyzer evidence and from the linear-window "
                        "tracer above. Provided as context to reassess, never to copy.",
            },
        }
        dossiers.append(dossier)
        if verbose and (i + 1) % 25 == 0:
            print(f"  {sample_set}: {i + 1}/{len(rows)}", flush=True)
    return dossiers


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    selector_cache = {}
    for _, ev_dir in SAMPLE_SETS.values():
        p = os.path.join(HUMAN_EVAL, ev_dir, "_selector_cache.json")
        selector_cache.update(read_json(p) or {})
    rule_facts = load_source_rule_facts()
    legit = load_legitimate_controls()
    print(f"source-rule fact addresses: {len(rule_facts)}; legit controls: {len(legit)}; "
          f"selector cache: {len(selector_cache)}")

    for ss in ("pilot", "gold_dev", "gold_test"):
        print(f"building {ss} dossiers ...", flush=True)
        d = build(ss, selector_cache, rule_facts, legit)
        out = os.path.join(OUT_DIR, f"{ss}_dossiers.json")
        with open(out, "w") as f:
            json.dump({"LABEL_SOURCE": "LLM_PROVISIONAL_OPUS5",
                       "STATIC_ANALYZER_EVIDENCE": "VISIBLE",
                       "STATUS": "PROVISIONAL_PENDING_HUMAN_REVIEW",
                       "sample_set": ss, "n_items": len(d), "dossiers": d}, f, indent=1)
        print(f"  wrote {out} ({len(d)} items)")


if __name__ == "__main__":
    main()
