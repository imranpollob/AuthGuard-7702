#!/usr/bin/env python3
"""Phase 0.4 — action composition of stored Tier-C adaptive WINNERS.

These are winner-composition statistics, not restricted-search results. The stored
records keep only the selected best candidate per (source, target, seed, fold, method),
so a winner that happens to contain address rewrite does NOT establish that no
Tier-A/B-only attack existed for that source. Tier-A/B-only winner fractions are
therefore reported as LOWER BOUNDS on what a properly rerun restricted search would find.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import importlib.util

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RV2 = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(RV2, "results", "sprint_phase0")

spec = importlib.util.spec_from_file_location(
    "phase0", os.path.join(HERE, "phase0_fixed_oracles.py"))
_mod = importlib.util.module_from_spec(spec)
sys.modules["phase0"] = _mod
spec.loader.exec_module(_mod)

FLOOD_ACTIONS = {"flood25", "flood50", "flood100", "flood200"}
TIER_A_ACTIONS = FLOOD_ACTIONS
TIER_B_ACTIONS = FLOOD_ACTIONS | {"metadata", "neutral25"}
WEAK = {"address", "selector"}


def actions_of(sequence):
    return set(str(sequence).split("+")) if sequence and sequence != "clean_noop" else set()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--methods", nargs="+", default=["random_search", "beam_search"])
    args = parser.parse_args()
    os.makedirs(OUT, exist_ok=True)
    frame, files = _mod.load_primary_records()

    adaptive = frame[frame.method.isin(args.methods)].copy()
    wins = adaptive[adaptive.attack_success].copy()
    wins["actions"] = wins.sequence.map(actions_of)

    rows, combos_out = [], {}
    for target in _mod.PRIMARY:
        g = wins[wins.target_model == target]
        n = len(g)
        if not n:
            continue
        has = lambda a: g.actions.map(lambda s: a in s)  # noqa: E731
        only_a = g.actions.map(lambda s: bool(s) and s <= TIER_A_ACTIONS)
        only_b = g.actions.map(lambda s: bool(s) and s <= TIER_B_ACTIONS)
        rows.append(dict(
            model=target, n_successful_winners=int(n),
            pct_only_tierA_actions=float(only_a.mean()),
            pct_only_tierB_actions=float(only_b.mean()),
            pct_contains_address=float(has("address").mean()),
            pct_contains_selector=float(has("selector").mean()),
            pct_contains_address_or_selector=float(
                g.actions.map(lambda s: bool(s & WEAK)).mean()),
            pct_contains_flooding=float(
                g.actions.map(lambda s: bool(s & FLOOD_ACTIONS)).mean()),
            pct_contains_metadata=float(has("metadata").mean()),
            pct_contains_neutral25=float(has("neutral25").mean()),
            seed_scope=[7702, 7703, 7704], fold_scope=[0, 1, 2, 3, 4],
            provenance="stored_artifact", interpretation="winner composition; lower bound"))
        combos = g.sequence.value_counts().head(5)
        combos_out[target] = [{"composition": k, "count": int(v)} for k, v in combos.items()]
        print(f"\n{target}  (n successful winners = {n})")
        print(f"  only Tier-A actions        {rows[-1]['pct_only_tierA_actions']:.3f}")
        print(f"  only Tier-B actions        {rows[-1]['pct_only_tierB_actions']:.3f}")
        print(f"  contains address           {rows[-1]['pct_contains_address']:.3f}")
        print(f"  contains selector          {rows[-1]['pct_contains_selector']:.3f}")
        print(f"  contains address|selector  {rows[-1]['pct_contains_address_or_selector']:.3f}")
        print(f"  contains flooding          {rows[-1]['pct_contains_flooding']:.3f}")
        print(f"  contains metadata          {rows[-1]['pct_contains_metadata']:.3f}")
        print(f"  contains neutral25         {rows[-1]['pct_contains_neutral25']:.3f}")
        print("  top-5 winning compositions:")
        for c in combos_out[target]:
            print(f"     {c['count']:>5}  {c['composition']}")

    payload = dict(
        phase="0.4 winner-composition statistics (Tier-C adaptive winners)",
        script="revision_v2/experiments/sprint_phase0/phase0_winner_composition.py",
        git_commit=_mod.git_commit(), input_files=[os.path.basename(f) for f in files],
        methods=args.methods, provenance="stored_artifact",
        caveat=("Winner-only records. A winner containing a weak-preservation primitive "
                "does not prove no Tier-A/B attack existed for that source; Tier-A/B-only "
                "fractions are lower bounds on restricted-search ASR."),
        per_model=rows, top_compositions=combos_out)
    with open(os.path.join(OUT, "phase0_winner_composition.json"), "w") as h:
        json.dump(payload, h, indent=2)
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "phase0_winner_composition.csv"), index=False)
    print(f"\n[phase0.4] wrote {OUT}")


if __name__ == "__main__":
    main()
