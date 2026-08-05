"""Render each dossier as a compact, complete labeling brief (the text actually reviewed).

The brief is lossy only in volume, never in kind: every evidence category present in the
dossier appears here. Nothing model-derived is rendered (there is nothing model-derived in the
dossier to render).
"""

from __future__ import annotations

import argparse
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOSS = os.path.join(ROOT, "results", "llm_provisional_opus5", "dossiers")


def short(s, n=110):
    if s is None:
        return "-"
    s = str(s).replace("\n", " ").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def render(d: dict) -> str:
    ident = d["identity"]
    src = d["source_static_analyzer_evidence"]
    code = d["source_and_code_evidence"]
    cfg = d["cfg_guard_analysis_opus5"]
    prev = d["previous_llm_provisional_review"]
    old = d["previous_linear_window_guard_tracer"]

    L = []
    L.append(f"### {d['item_id']}  [{ident['chain']}] {ident['runtime_size_bytes']}B "
             f"fam={ident['family_id']} chains={short(ident['chains_sharing_this_exact_bytecode'], 60)}")

    proj = ident.get("documented_project")
    if proj:
        L.append(f"PROJECT: {proj.get('project')} | {proj.get('category')} | "
                 f"conf={proj.get('provenance_confidence')} | src_match={proj.get('runtime_source_match')} "
                 f"| auth_count={proj.get('authorization_count')} | doc={short(proj.get('official_documentation'), 60)}")

    tup = src["rule_firing_tuples_for_this_address"]
    tup_s = "; ".join(f"{t['enclosing_function']}->{t['inferred_callee_signature']}" for t in tup[:5])
    L.append(f"SOURCE_RULE: {src['source_rule_label']}  ({src['n_tuples'] if 'n_tuples' in src else src['n_rule_tuples']} shipped tuples) "
             f"{tup_s if tup_s else '(no shipped per-address facts)'}")

    rep = src.get("local_reproduction_of_the_rules_question") or {}
    if rep:
        rp, fp = rep.get("receive_path", {}), rep.get("fallback_path", {})
        L.append(f"LOCAL_RULE_REPRO: rule_pattern_present={rep.get('source_rule_locally_reproduced')} "
                 f"| unauth_extcall_from_fallback/receive={rep.get('unauthenticated_external_call_from_fallback_or_receive')} "
                 f"| receive: call={rp.get('external_call_reachable')}/unguarded={rp.get('external_call_reachable_without_passing_a_caller_guard')}"
                 f" | fallback: call={fp.get('external_call_reachable')}/unguarded={fp.get('external_call_reachable_without_passing_a_caller_guard')}")
        for nm, pth in (("recv", rp), ("fbck", fp)):
            for g in (pth.get("guards_on_path") or [])[:2]:
                L.append(f"   [{nm}] guard pc={g['pc']} {g['kind']}: {g['semantics']}"
                         + (f" const={g['compared_address_constant']}" if g.get("compared_address_constant") else ""))
            for c in (pth.get("calls") or [])[:3]:
                L.append(f"   [{nm}] call pc={c['pc']} {c['op']} tgt={c.get('target_const') or c.get('target_src')} "
                         f"val={c.get('value_const') if c.get('value_const') is not None else c.get('value_src')}")

    L.append(f"VERIFIED_SOURCE: {code['verified_source']}")

    live = code.get("live_storage_reads")
    if live:
        L.append(f"ON_CHAIN_STORAGE: {short(json.dumps(live), 220)}")

    consts = code.get("embedded_address_constants")
    if consts:
        L.append(f"ADDR_CONSTANTS: {short(json.dumps(consts), 260)}")

    strs = code.get("strings")
    if strs and strs.strip():
        L.append(f"STRINGS: {short(strs, 260)}")

    fns = cfg.get("per_function", [])
    if "error" in cfg:
        L.append(f"CFG: ERROR {cfg['error']}")
    else:
        cen = cfg.get("static_opcode_census") or {}
        L.append(f"OPCODE_CENSUS: {', '.join(f'{k}={v}' for k, v in sorted(cen.items()))}")
        unr = cfg.get("sensitive_opcodes_never_reached_by_analysis") or {}
        if unr:
            L.append(f"!! COVERAGE_GAP: sensitive opcodes never reached by analysis: "
                     f"{ {k: v[:6] for k, v in unr.items()} } -> capability is a LOWER BOUND")
        L.append(f"FUNCTIONS ({cfg.get('n_functions', 0)} dispatched):")
    for f in fns:
        sig = f.get("resolved_signature") or ""
        head = (f"  {f['selector']:<12}{('(' + str(f.get('arguments')) + ')') if f.get('arguments') else '':<28}"
                f"{str(f.get('state_mutability') or '-'):<11}{f['guard_status']:<28}")
        extra = []
        if f.get("analysis_incomplete"):
            extra.append(f"INCOMPLETE(dynjmp={f['unresolved_dynamic_jumps']},"
                         f"uf={f.get('stack_underflows', 0)},"
                         f"cap={'Y' if f.get('hit_exploration_cap') else 'N'})")
        if f.get("reaches_ecrecover"):
            extra.append("ECRECOVER")
        L.append(head + (" ".join(extra)) + (f"  {sig}" if sig else ""))
        for g in f.get("guards", [])[:3]:
            L.append(f"      G pc={g['pc']} {g['kind']}: {g['semantics']}"
                     + (f" const={g['compared_address_constant']}" if g.get("compared_address_constant") else ""))
        for u in f.get("unguarded_sensitive", [])[:4]:
            L.append(f"      U pc={u['pc']} {u['op']}({u['impact']}) tgt={u.get('target_const') or u.get('target_src')}"
                     f" val={u.get('value_const') if u.get('value_const') is not None else u.get('value_src')}"
                     + (f" slot={u['storage_slot']}" if u.get("storage_slot") else ""))

    L.append(f"OLD_LINEAR_TRACER: {old.get('overall_status')} "
             f"(unreliable: byte-window scan, cannot follow jumps)")
    L.append(f"PREV_LLM: {prev.get('label')}/{prev.get('reason_category')} ({prev.get('confidence')}) "
             f"— {short(prev.get('concrete_finding'), 150)}")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample-set", required=True)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--end", type=int, default=10 ** 6)
    a = ap.parse_args()
    d = json.load(open(os.path.join(DOSS, f"{a.sample_set}_dossiers.json")))
    items = d["dossiers"][a.start:a.end]
    for i, it in enumerate(items, start=a.start):
        print(f"\n{'=' * 100}\n[{i}] ", end="")
        print(render(it))


if __name__ == "__main__":
    main()
