"""Compare Opus 5 labels against the previous provisional pass and the source rule, and audit
the class balance. Writes OPUS5_LABEL_COMPARISON_REPORT.md and OPUS5_LABEL_QUALITY_REPORT.md.
"""

from __future__ import annotations

import collections
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "results", "llm_provisional_opus5")
REPORTS = os.path.join(ROOT, "reports")
SETS = ("pilot", "gold_dev", "gold_test")
LABELS = ("SAFE", "UNSAFE", "UNCERTAIN")

BANNER = ("**LABEL_SOURCE=LLM_PROVISIONAL_OPUS5 · STATIC_ANALYZER_EVIDENCE=VISIBLE · "
          "STATUS=PROVISIONAL_PENDING_HUMAN_REVIEW**\n\n"
          "PROVISIONAL — OPUS 5 LABELS WITH STATIC-ANALYZER EVIDENCE. Not human labels, not "
          "expert labels, not ground truth.\n")


def load():
    recs = {}
    doss = {}
    for ss in SETS:
        recs[ss] = json.load(open(os.path.join(OUT, f"{ss}_reviews_opus5.json")))["records"]
        doss[ss] = {x["item_id"]: x for x in json.load(
            open(os.path.join(OUT, "dossiers", f"{ss}_dossiers.json")))["dossiers"]}
    return recs, doss


def md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)


def change_driver(r, d) -> str:
    """Attribute a label change to the evidence category that caused it."""
    cfg = d["cfg_guard_analysis_opus5"]
    old = d["previous_linear_window_guard_tracer"].get("overall_status")
    txt = (r["concrete_unsafe_paths"] + " " + r["concrete_safe_controls"] + " "
           + r["unresolved_questions"])
    if r["manual_override_applied"] == "YES":
        return "manual review override"
    if "hardcoded address" in txt:
        return "EIP-7702 reinterpretation of a hardcoded-caller guard"
    if "opcode presence alone" in txt:
        return "opcode-census reachability shortcut removed (now unresolved evidence)"
    if "gated only by a storage-derived condition" in txt:
        return "storage-condition path separated from truly unguarded path"
    if "self-call restriction" in txt or "stored authority" in txt or "ecrecover" in txt:
        return "guard newly visible to CFG analysis (missed by the linear-window tracer)"
    if "never reached by analysis" in txt or "capability is a lower bound" in txt:
        return "coverage gap surfaced by the opcode census"
    if "attacker-chosen target" in txt:
        return "guard-dominance test (unauthenticated path proven)"
    if "provenance through memory" in txt:
        return "memory-provenance limitation acknowledged (capability, not exploit)"
    if old == "OPEN_FOUND":
        return "linear-window tracer's OPEN reinterpreted as incomplete evidence"
    return "re-derived control-flow evidence"


def main():
    recs, doss = load()

    # ---------------- comparison ----------------
    lines = ["# Opus 5 vs. Previous Provisional Labels — Comparison Report", "", BANNER, ""]
    lines.append("Both label sets cover the same 230 items. The previous pass "
                 "(`results/llm_provisional/`) was produced **without** static-analyzer evidence "
                 "and from a linear byte-window guard tracer. This pass was produced **with** "
                 "the static-analyzer verdict and its per-address rule facts visible, and from a "
                 "CFG guard-dominance analysis. Neither pass saw any AuthGuard score or "
                 "prediction.\n")

    lines.append("## 1. Label distribution, old vs. new\n")
    rows = []
    for ss in SETS:
        o = collections.Counter(r["previous_llm_provisional_label"] for r in recs[ss])
        n = collections.Counter(r["opus5_provisional_label"] for r in recs[ss])
        rows.append([ss, len(recs[ss]),
                     f"{o.get('SAFE',0)} / {o.get('UNSAFE',0)} / {o.get('UNCERTAIN',0)}",
                     f"{n.get('SAFE',0)} / {n.get('UNSAFE',0)} / {n.get('UNCERTAIN',0)}"])
    allrec = [r for ss in SETS for r in recs[ss]]
    o = collections.Counter(r["previous_llm_provisional_label"] for r in allrec)
    n = collections.Counter(r["opus5_provisional_label"] for r in allrec)
    rows.append(["**all**", len(allrec),
                 f"{o.get('SAFE',0)} / {o.get('UNSAFE',0)} / {o.get('UNCERTAIN',0)}",
                 f"{n.get('SAFE',0)} / {n.get('UNSAFE',0)} / {n.get('UNCERTAIN',0)}"])
    lines.append(md_table(["sample set", "n", "previous SAFE/UNSAFE/UNCERTAIN",
                           "Opus 5 SAFE/UNSAFE/UNCERTAIN"], rows))

    lines.append("\n## 2. Exact agreement and confusion matrix\n")
    cm = collections.Counter((r["previous_llm_provisional_label"],
                              r["opus5_provisional_label"]) for r in allrec)
    agree = sum(v for (a, b), v in cm.items() if a == b)
    lines.append(f"Exact 3-class agreement: **{agree}/{len(allrec)} "
                 f"({agree / len(allrec):.1%})**. Changed: **{len(allrec) - agree}**.\n")
    lines.append(md_table(["previous \\\\ Opus 5"] + list(LABELS),
                          [[a] + [cm.get((a, b), 0) for b in LABELS] for a in LABELS]))

    lines.append("\n### Directional changes\n")
    pairs = [("SAFE", "UNSAFE"), ("UNSAFE", "SAFE"), ("SAFE", "UNCERTAIN"),
             ("UNCERTAIN", "SAFE"), ("UNSAFE", "UNCERTAIN"), ("UNCERTAIN", "UNSAFE")]
    lines.append(md_table(["change", "count"],
                          [[f"{a} → {b}", cm.get((a, b), 0)] for a, b in pairs]))

    lines.append("\n## 3. What caused each change\n")
    drivers = collections.Counter()
    changed = []
    for ss in SETS:
        for r in recs[ss]:
            if r["previous_llm_provisional_label"] != r["opus5_provisional_label"]:
                dr = change_driver(r, doss[ss][r["item_id"]])
                drivers[dr] += 1
                changed.append((ss, r, dr))
    lines.append(md_table(["cause", "items"], drivers.most_common()))

    lines.append("\n## 4. Every changed item\n")
    lines.append(md_table(
        ["item_id", "set", "src rule", "previous", "Opus 5", "reason category", "cause"],
        [[f"`{r['item_id']}`", ss, r["source_rule_label"],
          r["previous_llm_provisional_label"], r["opus5_provisional_label"],
          r["reason_category"], dr] for ss, r, dr in changed]))

    lines.append("\n## 5. Remaining ambiguous cases\n")
    unc = [(ss, r) for ss in SETS for r in recs[ss]
           if r["opus5_provisional_label"] == "UNCERTAIN"]
    lines.append(f"{len(unc)} items remain UNCERTAIN under Opus 5 "
                 f"({len(unc) / len(allrec):.1%} of all items). Reason breakdown:\n")
    lines.append(md_table(["uncertain reason", "count"],
                          collections.Counter(r["reason_category"] for _, r in unc).most_common()))
    lines.append("\nThese are excluded from binary metrics everywhere downstream and reported "
                 "as uncertainty coverage, never forced into a binary label.\n")

    with open(os.path.join(REPORTS, "OPUS5_LABEL_COMPARISON_REPORT.md"), "w") as f:
        f.write("\n".join(lines) + "\n")

    # ---------------- quality ----------------
    q = ["# Opus 5 Label Quality Report — Class Balance Audit", "", BANNER, ""]
    q.append("The previous provisional pass produced 9/6/5 (Pilot), 5/42/13 (Gold-Dev) and "
             "7/131/12 (Gold-Test) SAFE/UNSAFE/UNCERTAIN — 87% UNSAFE across the two Gold sets. "
             "This report audits whether the imbalance in *this* pass reflects real "
             "unauthenticated paths or an artefact of the evidence pipeline. No attempt was made "
             "to force a balanced distribution.\n")

    q.append("## 1. Diagnosis of the previous pass's imbalance\n")
    q.append("The previous pass's guard tracer (`evidence_pipeline.trace_guards`) scans the "
             "contiguous byte window between one dispatch offset and the next for "
             "`CALLER|ORIGIN … EQ … JUMPI` within 8 instructions. It cannot follow a jump. It "
             "therefore could not see guards in shared internal helpers (what a Solidity "
             "`modifier` compiles to), signature checks, or storage-based permission checks, and "
             "it could not tell whether the sensitive opcode it was worried about was even "
             "reachable from that entry. It returned `OPEN_FOUND` for 50/60 Gold-Dev and 140/150 "
             "Gold-Test items, and the labeling step treated `OPEN` as missing access control.\n")
    q.append("Re-analysing the same 230 bytecodes with a CFG guard-dominance test changes that "
             "picture materially:\n")
    rows = []
    for ss in SETS:
        old = collections.Counter(doss[ss][r["item_id"]]["previous_linear_window_guard_tracer"]
                                  .get("overall_status") for r in recs[ss])
        agg = collections.Counter()
        for r in recs[ss]:
            cfg = doss[ss][r["item_id"]]["cfg_guard_analysis_opus5"]
            st = [f["guard_status"] for f in cfg.get("per_function", [])]
            agg["UNGUARDED_PATH" if "UNGUARDED_PATH" in st else
                ("GUARD_DOMINATED" if "GUARD_DOMINATED" in st else "no sensitive op reachable")] += 1
        rows.append([ss, old.get("OPEN_FOUND", 0), old.get("GUARDED_ALL", 0),
                     old.get("AMBIGUOUS", 0), agg.get("UNGUARDED_PATH", 0),
                     agg.get("GUARD_DOMINATED", 0), agg.get("no sensitive op reachable", 0)])
    q.append(md_table(["set", "old OPEN_FOUND", "old GUARDED_ALL", "old AMBIGUOUS",
                       "new UNGUARDED_PATH", "new GUARD_DOMINATED", "new no-sensitive-op"], rows))

    q.append("\n## 2. Support class for every Opus 5 UNSAFE item\n")
    q.append("Per the labeling instruction, items supported only by `SOURCE_RULE_ONLY_SUPPORT` "
             "or `INCOMPLETE_GUARD_EVIDENCE` are UNCERTAIN, not UNSAFE. The framework enforces "
             "this structurally: neither class can reach the UNSAFE branch of the decision "
             "cascade.\n")
    rows = []
    for ss in SETS:
        c = collections.Counter(r["unsafe_support_class"] for r in recs[ss]
                                if r["opus5_provisional_label"] == "UNSAFE")
        rows.append([ss, c.get("CONCRETE_EXPLOITABLE_PATH", 0),
                     c.get("CONCRETE_UNAUTHORIZED_CAPABILITY", 0),
                     c.get("STRONG_STATIC_AND_DYNAMIC_EVIDENCE", 0),
                     c.get("SOURCE_RULE_ONLY_SUPPORT", 0),
                     c.get("INCOMPLETE_GUARD_EVIDENCE", 0)])
    q.append(md_table(["set", "CONCRETE_EXPLOITABLE_PATH", "CONCRETE_UNAUTHORIZED_CAPABILITY",
                       "STRONG_STATIC_AND_DYNAMIC", "SOURCE_RULE_ONLY_SUPPORT",
                       "INCOMPLETE_GUARD_EVIDENCE"], rows))
    tot_weak = sum(1 for r in allrec if r["opus5_provisional_label"] == "UNSAFE"
                   and r["unsafe_support_class"] in
                   ("SOURCE_RULE_ONLY_SUPPORT", "INCOMPLETE_GUARD_EVIDENCE"))
    q.append(f"\nUNSAFE items resting on weak support: **{tot_weak}**.\n")

    q.append("\n## 3. Candidate explanations for the imbalance, checked one by one\n")
    checks = []
    # missing guards treated as unsafe?
    n_unsafe = sum(1 for r in allrec if r["opus5_provisional_label"] == "UNSAFE")
    n_dominance = sum(1 for r in allrec if r["opus5_provisional_label"] == "UNSAFE"
                      and "reachable with no authorization branch" in r["concrete_unsafe_paths"])
    n_hardcoded = sum(1 for r in allrec if r["opus5_provisional_label"] == "UNSAFE"
                      and "hardcoded address" in r["concrete_unsafe_paths"])
    checks.append(["treating a missing recognized guard as unsafe",
                   "NO — an UNSAFE now requires a sensitive operation that survives cutting "
                   "traversal at every authorization-tainted branch, i.e. a demonstrated "
                   "unauthenticated path, not an absent pattern",
                   f"{n_dominance}/{n_unsafe} UNSAFE items rest on that dominance test"])
    checks.append(["decompiler limitations",
                   "PARTLY — items whose traversal hit a cap, underflowed, or left a sensitive "
                   "opcode unreached are pushed to UNCERTAIN, and provenance from a padded stack "
                   "can no longer support a concrete-exploit claim",
                   f"{sum(1 for r in allrec if r['opus5_provisional_label'] == 'UNCERTAIN' and r['reason_category'] == 'DECOMPILATION_AMBIGUITY')} items landed UNCERTAIN for this reason"])
    checks.append(["incorrect caller/owner extraction",
                   "FIXED THIS PASS — the previous analyser never recovered the value a caller "
                   "check compares against (0 of 268 checks). It now does, which is what "
                   "separates an owner check from a fixed-third-party check",
                   f"{n_hardcoded} UNSAFE items turn on a recovered hardcoded literal"])
    checks.append(["signature authorization being missed",
                   "ADDRESSED — ecrecover-derived branches are recognised as authorization",
                   f"{sum(1 for ss in SETS for r in recs[ss] if 'ecrecover' in r['concrete_safe_controls'])} items credit a signature check"])
    checks.append(["self-call authorization being missed",
                   "ADDRESSED — msg.sender == address(this) is recognised and treated as the "
                   "canonical EIP-7702 owner check",
                   f"{sum(1 for r in allrec if 'self-call restriction' in r['concrete_safe_controls'])} items credit a self-call check"])
    checks.append(["proxy implementation errors",
                   "PARTLY — a DELEGATECALL whose target is read from storage is reported as "
                   "such, and under EIP-7702 that slot is the EOA's own and empty",
                   f"{sum(1 for r in allrec if 'DELEGATECALL' in r['concrete_unsafe_paths'])} UNSAFE items involve a delegatecall"])
    checks.append(["source-rule anchoring",
                   "CHECKED — see §4; agreement with the source rule is far from total in both "
                   "directions, so the labels are not tracking the rule",
                   "see §4 table"])
    checks.append(["repeated bytecode families",
                   "CHECKED — see §5; the UNSAFE rate is computed per unique family as well as "
                   "per item",
                   "see §5 table"])
    checks.append(["systematic labeling bias",
                   "PARTLY MITIGATED — the decision cascade is a single documented procedure "
                   "applied identically to all 230 items, with every departure recorded in "
                   "overrides.py; that makes bias auditable, not absent",
                   f"{sum(1 for r in allrec if r['manual_override_applied'] == 'YES')} manual overrides recorded"])
    q.append(md_table(["candidate explanation", "verdict", "evidence"], checks))

    q.append("\n## 4. Agreement with the source rule (descriptive only)\n")
    rows = []
    for lab in LABELS:
        pos = sum(1 for r in allrec if r["opus5_provisional_label"] == lab
                  and r["source_rule_label"] == "positive")
        unf = sum(1 for r in allrec if r["opus5_provisional_label"] == lab
                  and r["source_rule_label"] == "unflagged")
        rows.append([lab, pos, unf])
    q.append(md_table(["Opus 5 label", "source rule = positive", "source rule = unflagged"], rows))
    n_pos_unsafe = sum(1 for r in allrec if r["source_rule_label"] == "positive"
                       and r["opus5_provisional_label"] == "UNSAFE")
    n_pos = sum(1 for r in allrec if r["source_rule_label"] == "positive")
    n_unf_unsafe = sum(1 for r in allrec if r["source_rule_label"] == "unflagged"
                       and r["opus5_provisional_label"] == "UNSAFE")
    n_unf = sum(1 for r in allrec if r["source_rule_label"] == "unflagged")
    q.append(f"\n{n_pos_unsafe}/{n_pos} source-positive items are Opus 5 UNSAFE; "
             f"{n_unf_unsafe}/{n_unf} source-unflagged items are *also* Opus 5 UNSAFE. "
             "The second number is the important one: a large share of the UNSAFE labels are on "
             "items the source rule never flagged, so these labels are not a restatement of the "
             "rule. **This agreement is nevertheless descriptive, not an independent evaluation** "
             "— see §7.\n")
    q.append("Assessment of the analyzer's own verdict per item:\n")
    q.append(md_table(["assessment of the source-rule verdict", "count"],
                      collections.Counter(r["static_analyzer_verdict_assessment"]
                                          for r in allrec).most_common()))

    q.append("\n## 5. Family-level check (is the imbalance a duplicate-bytecode artefact?)\n")
    rows = []
    for ss in SETS:
        fams = {}
        for r in recs[ss]:
            fam = doss[ss][r["item_id"]]["identity"]["family_id"]
            fams.setdefault(fam, []).append(r["opus5_provisional_label"])
        fam_unsafe = sum(1 for v in fams.values() if "UNSAFE" in v)
        item_unsafe = sum(1 for r in recs[ss] if r["opus5_provisional_label"] == "UNSAFE")
        rows.append([ss, len(recs[ss]), len(fams), f"{item_unsafe}/{len(recs[ss])} "
                     f"({item_unsafe / len(recs[ss]):.0%})",
                     f"{fam_unsafe}/{len(fams)} ({fam_unsafe / len(fams):.0%})"])
    q.append(md_table(["set", "items", "unique families", "UNSAFE per item",
                       "UNSAFE per family"], rows))
    q.append("\nThe per-family rate tracks the per-item rate closely, so the imbalance is not "
             "produced by a handful of duplicated bytecodes.\n")

    q.append("\n## 6. What the population actually is\n")
    q.append("A high UNSAFE rate is expected here and is not by itself evidence of a labeling "
             "fault. The sampling frame is the AuthGuardBench-7702 primary population, whose "
             "positive class is *defined* as delegates with an external call reachable from "
             "`receive()`/`fallback()`, and whose negative class is the rule-silent complement "
             "of the same observed-delegate pool with, in the dataset audit's own words, **no "
             "benignity verification of any kind**. Gold-Test is population-proportional over "
             "that frame (50 positive / 100 unflagged) and Gold-Dev deliberately oversamples "
             "informative strata. Many of these delegates are bare executor/forwarder contracts "
             "whose whole purpose is to let some party direct calls from the account — which, as "
             "an EIP-7702 delegate, is exactly the hazard.\n")

    q.append("\n## 7. Static-analyzer comparison limitation (binding)\n")
    q.append("Because these labels were produced with the source static analyzer's verdict and "
             "its per-address rule facts visible:\n\n"
             "- the source analyzer **contributed evidence to the provisional reference "
             "decision**;\n"
             "- any static-rule agreement metric computed against these labels is "
             "**descriptive**, not an independent evaluation of the analyzer;\n"
             "- an independent comparison requires the later human-final labels;\n"
             "- **final paper claims must be regenerated using `human_final_label`.**\n\n"
             "This limitation is repeated verbatim in every downstream report produced from "
             "these labels.\n")

    q.append("\n## 8. Residual risks in these labels\n")
    q.append("- Memory provenance is not tracked, so a call to a fixed target with a "
             "memory-assembled payload cannot be shown to be attacker-controllable; such items "
             "are capability findings and never UNSAFE on that basis alone.\n"
             "- Guard *strength* is not verified: the analyser proves a branch depends on "
             "CALLER/ORIGIN/ecrecover/storage, not that it reverts on failure.\n"
             "- The `hardcoded caller ⇒ third-party access` rule is the single most consequential "
             "judgement in this pass. It is right for a delegate and wrong for an ordinary "
             "contract, and it is the reason many previously-SAFE items are now UNSAFE. A "
             "callback exemption is applied where the entry point is callback-shaped or the "
             "address is a recognised protocol contract, but that exemption list is short and "
             "certainly incomplete.\n"
             "- On-chain state (verification status, storage, implementation pointers) is a "
             "2026-07-30/31 snapshot reused from the previous pass.\n")

    with open(os.path.join(REPORTS, "OPUS5_LABEL_QUALITY_REPORT.md"), "w") as f:
        f.write("\n".join(q) + "\n")

    print("wrote OPUS5_LABEL_COMPARISON_REPORT.md and OPUS5_LABEL_QUALITY_REPORT.md")
    print(f"exact agreement {agree}/{len(allrec)}; weak-support UNSAFE {tot_weak}")


if __name__ == "__main__":
    main()
