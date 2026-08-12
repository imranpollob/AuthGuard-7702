#!/usr/bin/env python3
"""Consistency audit for the TPS manuscript.

Guards against the specific factual and statistical-framing errors identified during the
sprint. Table checks extract the whole table environment, because the caption precedes the
label and a forward slice from the label would miss it.
"""
import re, sys

TEX = "revision_v2/paper_final/AuthGuard_7702_tps2026.tex"
tex = open(TEX).read()
flat = re.sub(r"\s+", " ", tex)
checks, fails = [], []

def check(name, ok, detail=""):
    checks.append((name, bool(ok), detail))
    if not ok:
        fails.append(name)

def table_env(label):
    """Full \\begin{table}...\\end{table} block containing the given label."""
    for m in re.finditer(r"\\begin\{table\*?\}.*?\\end\{table\*?\}", tex, re.S):
        if f"\\label{{{label}}}" in m.group(0):
            return re.sub(r"\s+", " ", m.group(0))
    return ""

# --- factual corrections -------------------------------------------------------------
check("no live/752 'family-disjoint' claim",
      not re.findall(r"family-disjoint[^.]{0,80}(?:752|live|temporal)"
                     r"|(?:752|live|temporal)[^.]{0,60}family-disjoint", flat, re.I))
check("live population described as family-overlap audited",
      "explicit family-overlap auditing" in flat)
check("benchmark qualitative controls = 5",
      "Qualitative production control & 5 &" in flat)
check("no '8 audited implementations' inside the benchmark",
      not re.findall(r"(?:eight|8) audited implementations", flat, re.I))
check("registry kept separate from the 3,082 total",
      "not part of the 3,082 benchmark observations" in flat)
# banned wording is "edits are capped at 2x"; "appended content is capped at 2x" is correct
check("no ambiguous 'edits capped at 2x' wording",
      not re.findall(r"[Ee]dits are capped at \$?2\\times", flat))
check("byte budget states appended<=2x and final~3x",
      "Appended content is capped at $2\\times$" in flat
      and "at most approximately $3\\times$ the original size" in flat)
check("no 'fixed transformations cannot rank' claim",
      not re.findall(r"[Ff]ixed transformations?[^.]{0,60}cannot (?:rank|distinguish|separate)", flat))
check("uses 'materially underestimates' framing",
      "materially underestimates the robustness gap" in flat)
check("no anonymity leak",
      not re.findall(r"earlier version of this work|previous version of this paper", flat, re.I))
check("no 'deployed model' phrasing", not re.findall(r"deployed model", flat, re.I))
check("no 'length-invariant' phrasing", not re.findall(r"length-invariant", flat, re.I))
check("no formal semantic-equivalence claim",
      "do not claim formal semantic equivalence" in flat.lower())

# --- seed scope ----------------------------------------------------------------------
check("tier table caption flags differing seed scope",
      "Seed scope differs by model" in table_env("tab:tiers"))
check("limitations state single-seed models",
      "seed 7702 only in the tier analysis" in flat)
check("no claim that all four models are three-seed",
      not re.findall(r"all four models[^.]{0,40}three seeds", flat, re.I))

# --- paired vs marginal --------------------------------------------------------------
central, tiers = table_env("tab:central"), table_env("tab:tiers")
check("central table exists", bool(central))
check("tier table exists", bool(tiers))
check("paired .1670/.5369 appear only in the paired table",
      ".1670" in central and ".5369" in central
      and ".1670" not in tiers and ".5369" not in tiers)
check("marginal .1970/.5417 appear only in the marginal table",
      ".1970" in tiers and ".5417" in tiers
      and ".1970" not in central and ".5417" not in central)
check("central caption marks statistics as paired, not marginal",
      "Paired statistics over the shared clean-detected population" in central
      and "not the marginal values" in central)
check("tier caption marks statistics as marginal",
      "Marginal attack success" in tiers)
check("headline identifies population (3 seeds / 1,503 / 209 families)",
      "1,503 paired observations" in flat and "209 bytecode families" in flat)
check("methods define marginal vs paired",
      "Marginal versus paired statistics" in flat)
check("no .181-.062 subtraction presented as the contrast",
      not re.findall(r"0?\.181\s*[-\u2013]\s*0?\.062", flat))
check("augmentation contrast names its shared population",
      "not by subtracting the marginal values" in flat)

# --- headline integrity ---------------------------------------------------------------
check("Tier B headline numbers present",
      "+.3699" in flat.replace("$\\mathbf{+.3699}$", "+.3699") or "0.370" in flat)
check("robust recall headline present",
      "0.6786" in flat and "0.3783" in flat)
check("preservation totals present",
      "3{,}464" in flat and "5,196" in flat and "120 distinct bytecode families" in flat)

width = max(len(n) for n, _, _ in checks) + 2
print(f"{'CHECK':<{width}}RESULT")
for n, ok, d in checks:
    print(f"  {n:<{width}}{'PASS' if ok else 'FAIL'}{('  ' + d) if (d and not ok) else ''}")
print(f"\n{len(checks) - len(fails)}/{len(checks)} passed")
sys.exit(1 if fails else 0)
