"""Produce the Opus 5 provisional labels for Pilot / Gold-Dev / Gold-Test.

Writes, per sample set:
  results/llm_provisional_opus5/<set>_labels_opus5.csv
  results/llm_provisional_opus5/<set>_reviews_opus5.json

Every file carries LABEL_SOURCE=LLM_PROVISIONAL_OPUS5, STATIC_ANALYZER_EVIDENCE=VISIBLE,
STATUS=PROVISIONAL_PENDING_HUMAN_REVIEW. `human_final_label` and its companions are emitted
empty and are never written from any other field.
"""

from __future__ import annotations

import csv
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from opus5_label import assess_source_analyzer, decide  # noqa: E402
from overrides import OVERRIDES  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOSS = os.path.join(ROOT, "results", "llm_provisional_opus5", "dossiers")
OUT = os.path.join(ROOT, "results", "llm_provisional_opus5")

BANNER = {
    "LABEL_SOURCE": "LLM_PROVISIONAL_OPUS5",
    "STATIC_ANALYZER_EVIDENCE": "VISIBLE",
    "STATUS": "PROVISIONAL_PENDING_HUMAN_REVIEW",
}

FIELDS = [
    "item_id", "sample_set", "chain", "address",
    "source_rule_label", "source_rule_name", "source_rule_assessment",
    "previous_llm_provisional_label",
    "opus5_provisional_label", "opus5_confidence", "reason_category",
    "unsafe_support_class",
    "contract_purpose", "actual_implementation", "sensitive_entry_points",
    "sensitive_operations", "caller_authorization_analysis", "initialization_analysis",
    "proxy_and_upgrade_analysis", "asset_operation_analysis", "eip7702_specific_analysis",
    "static_analyzer_evidence_summary", "static_analyzer_verdict_assessment",
    "concrete_safe_controls", "concrete_unsafe_paths", "conflicting_evidence",
    "unresolved_questions", "final_rationale", "evidence_references",
    # label-separation fields, kept distinct at all times
    "llm_provisional_label_previous_pass", "human_final_label", "human_final_confidence",
    "human_final_reason", "human_review_status",
    "manual_override_applied", "manual_override_reason",
]


def join(items, sep="; ", empty="none identified"):
    items = [i for i in items if i]
    return sep.join(items) if items else empty


def contract_purpose(d, s) -> str:
    cfg = d["cfg_guard_analysis_opus5"]
    ident = d["identity"]
    names = [f.get("resolved_signature") or f["selector"]
             for f in cfg.get("per_function", [])][:10]
    proj = ident.get("documented_project")
    base = (f"{ident['runtime_size_bytes']}-byte runtime on {ident['chain']} exposing "
            f"{cfg.get('n_functions', 0)} dispatched function(s)"
            + (f": {', '.join(names)}" if names else " (no standard dispatcher recovered)"))
    if proj:
        base += (f". Bytecode matches the documented project {proj.get('project')} "
                 f"({proj.get('category')}, provenance {proj.get('provenance_confidence')}).")
    strings = (d["source_and_code_evidence"].get("strings") or "")
    hints = [w for w in ("Ownable", "ReentrancyGuard", "EntryPoint", "Signed Message",
                         "not owner", "Not owner", "unauthorized", "Unauthorized",
                         "not authorized", "Initializable", "Router", "Executor",
                         "BatchDelegator", "Multicall", "Safe") if w in strings]
    if hints:
        base += f" Embedded strings mention: {', '.join(sorted(set(hints)))}."
    return base


def implementation_text(d) -> str:
    cfg = d["cfg_guard_analysis_opus5"]
    live = d["source_and_code_evidence"].get("live_storage_reads")
    dc = [u for f in cfg.get("per_function", []) for u in f.get("unguarded_sensitive", [])
          if u["op"] == "DELEGATECALL"]
    fbdc = []
    for p in ("receive_path", "fallback_path"):
        fbdc += [c for c in (cfg.get("fallback_receive_paths", {}).get(p, {}).get("calls") or [])
                 if c["op"] == "DELEGATECALL"]
    if not dc and not fbdc:
        return ("No DELEGATECALL was found on any analysed path: this address is the executing "
                "implementation itself, not a forwarding proxy.")
    tgts = sorted({str(c.get("target_const") or ",".join(c.get("target_src") or [])) for c in dc + fbdc})
    txt = (f"DELEGATECALL present; forwarding target(s) resolved by the analyser: {tgts}. ")
    if any(t == "sload" for t in tgts):
        txt += ("At least one target is read from storage. Under EIP-7702 that slot lives in "
                "the AUTHORIZING EOA's storage, which is empty at authorization time, so the "
                "implementation actually executed depends on what (if anything) writes it. ")
    if live:
        txt += f"Live storage read during evidence collection: {json.dumps(live)[:400]}"
    return txt


def initialization_text(d, s) -> str:
    cfg = d["cfg_guard_analysis_opus5"]
    inits = [f for f in cfg.get("per_function", [])
             if any(k in (f.get("resolved_signature") or "").lower()
                    for k in ("initial", "setup", "init"))]
    writes = s["unguarded_authority_write"]
    parts = []
    if inits:
        parts.append("Initializer-shaped function(s): "
                     + ", ".join(f"{f.get('resolved_signature') or f['selector']} "
                                 f"[{f['guard_status']}]" for f in inits))
    if writes:
        parts.append(
            "Unauthenticated write(s) to a low storage slot: "
            + ", ".join(f"{sel} -> slot {slot} (pc {pc})" for sel, pc, slot in writes)
            + ". Because the EOA's storage starts empty under EIP-7702, whichever party calls "
              "first sets that slot")
    if not parts:
        parts.append("No initializer-shaped entry point and no unauthenticated write to a low "
                     "storage slot was found on the analysed paths.")
    parts.append("Note that the delegate's constructor never executes in the EOA's context, so "
                 "any state the design expects from construction is zero unless explicitly set.")
    return " ".join(parts)


def caller_auth_text(d, s) -> str:
    parts = []
    for key, desc in (
        ("self_call_guarded", "self-call check (msg.sender == address(this))"),
        ("signature_guarded", "ecrecover-derived authorization branch"),
        ("storage_authority_guarded", "msg.sender compared against a stored authority"),
        ("entrypoint_guarded", "caller restricted to a recognized ERC-4337 EntryPoint"),
        ("origin_equals_caller_only", "tx.origin == msg.sender (NOT authorization)"),
    ):
        if s[key]:
            parts.append(f"{desc}: {', '.join(sorted(set(s[key]))[:6])}")
    if s["third_party_guarded_asset"]:
        parts.append("caller restricted to a HARDCODED address that cannot be the authorizing "
                     "EOA: " + ", ".join(f"{sel} -> {c}" for sel, c, _ in
                                         s["third_party_guarded_asset"][:4]))
    if s["unresolved_guard_only"]:
        parts.append("caller comparison present but its operand is unresolved for: "
                     + ", ".join(sel for sel, _ in s["unresolved_guard_only"][:4]))
    if s["initializer_unrestricted"]:
        parts.append("initializer-shaped entry point with an unauthenticated storage write: "
                     + ", ".join(f"{sel} (pc {pc})" for sel, pc in
                                 s["initializer_unrestricted"][:4]))
    ung = (len(s["unguarded_arbitrary_call"]) + len(s["unguarded_value_drain"])
           + len(s["unguarded_delegatecall"]) + len(s["unguarded_selfdestruct"])
           + len(s["unguarded_authority_write"]))
    parts.append(f"{ung} sensitive operation(s) remain reachable from the dispatcher when "
                 f"traversal is cut at every authorization-tainted branch (the guard-dominance "
                 f"test).")
    return " | ".join(parts)


def asset_text(d, s) -> str:
    parts = []
    if s["unguarded_arbitrary_call"]:
        parts.append("attacker-chosen call target(s): "
                     + ", ".join(f"{a} pc={b}" for a, b, _ in s["unguarded_arbitrary_call"][:5]))
    if s["unguarded_value_drain"]:
        parts.append("unauthenticated call(s) moving funds the account already holds: "
                     + ", ".join(f"{a} pc={b}->{c} ({d_})"
                                 for a, b, c, d_ in s["unguarded_value_drain"][:5]))
    if s["unguarded_capability_call"]:
        parts.append("unauthenticated call(s) with a fixed/stored destination and a "
                     "memory-assembled payload (capability; exploitability not established): "
                     + ", ".join(f"{a} pc={b}->{c}"
                                 for a, b, c, _d, _e in s["unguarded_capability_call"][:5]))
    if s["unguarded_passthrough_call"]:
        parts.append("pass-through call(s) forwarding only msg.value (caller donates their own "
                     "ETH; not a path to the account's assets): "
                     + ", ".join(f"{a} pc={b}->{c}" for a, b, c in
                                 s["unguarded_passthrough_call"][:4]))
    if not parts:
        parts.append("No unauthenticated path to asset movement or approval was found on the "
                     "analysed paths.")
    return " | ".join(parts)


def eip7702_text(d, s) -> str:
    parts = []
    if s["self_call_guarded"]:
        parts.append("Uses the canonical EIP-7702 self-call pattern (msg.sender == "
                     "address(this)), which under delegation resolves to the authorizing EOA "
                     "itself — appropriate authorization for this context.")
    if s["third_party_guarded_asset"]:
        parts.append("Authorization is anchored on an address hardcoded at delegate-deployment "
                     "time. That address cannot be the authorizing EOA, so this is not a "
                     "protection for the authorizer — it is exclusive third-party access to the "
                     "authorizer's assets, which is the structure of a drainer delegate.")
    if s["origin_equals_caller_only"]:
        parts.append("Relies on tx.origin == msg.sender, which under EIP-7702 does not "
                     "distinguish the account owner from an attacker calling the account "
                     "directly.")
    if s["storage_authority_guarded"] and not s["unguarded_authority_write"]:
        parts.append("Authority is read from storage. In the EOA's own storage that slot is zero "
                     "at authorization time and no unauthenticated write to it was found, so the "
                     "guarded paths are effectively unreachable until an authorized write occurs "
                     "— safe, but also non-functional until initialized.")
    if s["storage_authority_guarded"] and s["unguarded_authority_write"]:
        parts.append("Authority is read from storage AND an unauthenticated write to a low slot "
                     "exists: on a freshly authorized EOA the first caller can install "
                     "themselves as that authority.")
    if not parts:
        parts.append("No EIP-7702-specific authorization pattern (self-call check, tx.origin "
                     "gating, or initializer-established authority) was identified on the "
                     "analysed paths.")
    return " ".join(parts)


def build_record(d, sample_set):
    res = decide(d)
    s = res.get("summary")
    src = d["source_static_analyzer_evidence"]
    cfg = d["cfg_guard_analysis_opus5"]
    verdict, verdict_text = assess_source_analyzer(d, s, cfg) if s else (
        "UNRESOLVED", "No runtime code to compare against the analyzer's verdict.")

    ov = OVERRIDES.get(d["item_id"])
    override_applied, override_reason = "", ""
    if ov:
        override_applied = "YES"
        override_reason = ov["reason_text"]
        res = {**res, **{k: v for k, v in ov.items() if k in
                         ("label", "reason", "confidence", "support")}}

    prev = d["previous_llm_provisional_review"].get("label") or ""
    tuples = src["rule_firing_tuples_for_this_address"]
    fb = cfg.get("fallback_receive_paths") or {}

    ent = [f"{f.get('resolved_signature') or f['selector']} [{f['guard_status']}"
           + (", analysis incomplete" if f.get("analysis_incomplete") else "") + "]"
           for f in cfg.get("per_function", [])]

    sens_ops = []
    for f in cfg.get("per_function", []):
        for u in f.get("unguarded_even_by_storage", f.get("unguarded_sensitive", [])):
            sens_ops.append(f"{f.get('resolved_signature') or f['selector']}: {u['op']} "
                            f"pc={u['pc']} ({u['impact']}) target="
                            f"{u.get('target_const') or ','.join(u.get('target_src') or []) or 'const/unknown'}")
    census = cfg.get("static_opcode_census") or {}

    rec = {
        "item_id": d["item_id"], "sample_set": sample_set,
        "chain": d["identity"]["chain"], "address": d["identity"]["address"],
        "source_rule_label": src["source_rule_label"],
        "source_rule_name": src["source_rule_name"],
        "source_rule_assessment": verdict_text,
        "previous_llm_provisional_label": prev,
        "opus5_provisional_label": res["label"],
        "opus5_confidence": res["confidence"],
        "reason_category": res["reason"],
        "unsafe_support_class": res["support"] if res["label"] == "UNSAFE" else "",
        "contract_purpose": contract_purpose(d, s) if s else "No runtime code.",
        "actual_implementation": implementation_text(d) if s else "No runtime code.",
        "sensitive_entry_points": join(ent),
        "sensitive_operations": join(sens_ops or [
            f"static opcode census: {', '.join(f'{k}={v}' for k, v in sorted(census.items()))}"]),
        "caller_authorization_analysis": caller_auth_text(d, s) if s else "n/a",
        "initialization_analysis": initialization_text(d, s) if s else "n/a",
        "proxy_and_upgrade_analysis": implementation_text(d),
        "asset_operation_analysis": asset_text(d, s) if s else "n/a",
        "eip7702_specific_analysis": eip7702_text(d, s) if s else "n/a",
        "static_analyzer_evidence_summary": (
            f"source_rule_label={src['source_rule_label']}; shipped rule tuples for this "
            f"address: {len(tuples)}"
            + (f" ({'; '.join(t['enclosing_function'] + ' -> ' + t['inferred_callee_signature'] for t in tuples[:4])})" if tuples else "")
            + f". Rule = {src['source_rule_name']}. Rule models authorization: NO. "
            + f"Local re-derivation of the rule's own question: pattern_present="
            + f"{fb.get('source_rule_locally_reproduced')}, "
            + f"unauthenticated_external_call_from_fallback_or_receive="
            + f"{fb.get('unauthenticated_external_call_from_fallback_or_receive')}."),
        "static_analyzer_verdict_assessment": verdict,
        "concrete_safe_controls": join(res.get("safe_controls", [])),
        "concrete_unsafe_paths": join(res.get("unsafe_paths", [])),
        "conflicting_evidence": join(res.get("conflicting", []) +
                                     ([f"the source analyzer's verdict is {verdict} against the "
                                       f"CFG evidence"] if verdict == "CONTRADICTED" else [])),
        "unresolved_questions": join(res.get("unresolved", [])),
        "final_rationale": build_rationale(d, res, verdict, override_reason),
        "evidence_references": (
            f"CFG guard-dominance analysis: results/llm_provisional_opus5/dossiers/"
            f"{sample_set}_dossiers.json#{d['item_id']}; decompiled disassembly and live "
            f"verification: human_eval/{sample_set}_code_evidence/"
            f"{d['identity']['chain']}_{d['identity']['address']}/; source-analyzer facts: "
            f"USENIX EIP-7702 artifact/eoa_detect/detect_result.jsonl"),
        "llm_provisional_label_previous_pass": prev,
        "human_final_label": "", "human_final_confidence": "", "human_final_reason": "",
        "human_review_status": "NOT_REVIEWED",
        "manual_override_applied": override_applied,
        "manual_override_reason": override_reason,
    }
    return rec


def build_rationale(d, res, verdict, override_reason) -> str:
    label = res["label"]
    bits = []
    if label == "UNSAFE":
        bits.append("UNSAFE because a concrete path exists from an externally reachable entry "
                    "point to a sensitive operation that no authorization branch dominates: "
                    + (res["unsafe_paths"][0] if res.get("unsafe_paths") else ""))
        if res["support"] in ("SOURCE_RULE_ONLY_SUPPORT", "INCOMPLETE_GUARD_EVIDENCE"):
            bits.append("Support class is weak, so this would normally be UNCERTAIN; see the "
                        "override note.")
    elif label == "SAFE":
        bits.append("SAFE because positive authorization evidence was found and no "
                    "unauthenticated path to a sensitive operation survived the guard-dominance "
                    "test: " + (res["safe_controls"][0] if res.get("safe_controls")
                                else "every dispatched function analysed to completion with no "
                                     "reachable sensitive operation."))
    else:
        bits.append("UNCERTAIN because the evidence does not establish either direction: "
                    + (res["unresolved"][0] if res.get("unresolved")
                       else "no concrete unauthenticated dangerous path was demonstrated, and "
                            "no positive authorization control was confirmed either."))
    bits.append(f"The source static analyzer's verdict was assessed as {verdict} against this "
                f"CFG evidence; it is treated as evidence, not as an automatic label, because "
                f"the rule contains no authorization predicate.")
    if override_reason:
        bits.append(f"MANUAL REVIEW OVERRIDE: {override_reason}")
    return " ".join(b for b in bits if b)


def main():
    os.makedirs(OUT, exist_ok=True)
    summary = {}
    for ss in ("pilot", "gold_dev", "gold_test"):
        d = json.load(open(os.path.join(DOSS, f"{ss}_dossiers.json")))
        recs = [build_record(x, ss) for x in d["dossiers"]]
        with open(os.path.join(OUT, f"{ss}_reviews_opus5.json"), "w") as f:
            json.dump({**BANNER, "sample_set": ss, "n_items": len(recs),
                       "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                       "records": recs}, f, indent=1)
        with open(os.path.join(OUT, f"{ss}_labels_opus5.csv"), "w", newline="") as f:
            f.write(f"# LABEL_SOURCE={BANNER['LABEL_SOURCE']}\n")
            f.write(f"# STATIC_ANALYZER_EVIDENCE={BANNER['STATIC_ANALYZER_EVIDENCE']}\n")
            f.write(f"# STATUS={BANNER['STATUS']}\n")
            w = csv.DictWriter(
                f,
                fieldnames=FIELDS,
                extrasaction="ignore",
                lineterminator="\n",
            )
            w.writeheader()
            for r in recs:
                w.writerow(r)
        dist = {}
        for r in recs:
            dist[r["opus5_provisional_label"]] = dist.get(r["opus5_provisional_label"], 0) + 1
        summary[ss] = dist
        print(f"{ss}: {len(recs)} items -> {dist}")
    return summary


def emit_pipeline_compatible_labels():
    """Write `<set>_labels.json` in the schema the downstream pipeline scripts already read.

    The Opus 5 records are the source of truth; this is a projection of them onto the field
    names (`llm_provisional_label`, `llm_provisional_confidence`) that `run_gold_dev_baseline`,
    `run_retraining_experiments`, `select_provisional_final_model`, `run_gold_test_evaluation`
    and `run_cascade_evaluation` consume, so the pipeline runs against the new labels without
    duplicating those scripts. It lives under results/llm_provisional_opus5/, so it can never
    overwrite the previous pass's labels.
    """
    for ss in ("pilot", "gold_dev", "gold_test"):
        src = json.load(open(os.path.join(OUT, f"{ss}_reviews_opus5.json")))
        out = []
        for r in src["records"]:
            out.append({
                "item_id": r["item_id"],
                "llm_provisional_label": r["opus5_provisional_label"],
                "llm_provisional_confidence": r["opus5_confidence"].lower(),
                "llm_provisional_reason_category": r["reason_category"],
                "source_rule_label": "1" if r["source_rule_label"] == "positive" else "0",
                "human_final_label": "", "human_final_confidence": "", "human_final_reason": "",
                "human_review_status": "NOT_REVIEWED",
                "chain": r["chain"], "address": r["address"],
                "concrete_finding": r["concrete_unsafe_paths"],
                "evidence_references": r["evidence_references"],
            })
        with open(os.path.join(OUT, f"{ss}_labels.json"), "w") as f:
            json.dump({**BANNER, "PROVENANCE": f"projection of {ss}_reviews_opus5.json",
                       "sample_set": ss, "n_items": len(out), "records": out}, f, indent=1)
    print("wrote pipeline-compatible <set>_labels.json under", OUT)


if __name__ == "__main__":
    main()
    emit_pipeline_compatible_labels()
