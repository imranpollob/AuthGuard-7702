#!/usr/bin/env python3
"""Phase 4 analysis — tier table, central paired comparison, Tier-C-only evasions.

All inputs come from the regenerated-checkpoint run. Nothing here is mixed with the
historical stored-artifact numbers; those live in their own block of frozen_numbers.json.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import importlib.util
import json
import os
import subprocess
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RV2 = os.path.abspath(os.path.join(HERE, "..", ".."))
IN = os.path.join(RV2, "results", "sprint_phase4")
OUT = IN

spec = importlib.util.spec_from_file_location("phase0", os.path.join(
    RV2, "experiments", "sprint_phase0", "phase0_fixed_oracles.py"))
_p0 = importlib.util.module_from_spec(spec)
sys.modules["phase0"] = _p0
spec.loader.exec_module(_p0)
NBOOT = _p0.analyzer.NBOOT

ORDER = ["authguard_seq", "emulator_logreg", "flat_cnn", "hist_ngram_xgb"]
KEY = ["seed", "fold", "sid"]


def family_ci(group, seed_material, nboot):
    eligible = group[group.clean_detected]
    if not len(eligible):
        return (np.nan, np.nan)
    fams = eligible.family_id.to_numpy()
    uniq = np.asarray(sorted(pd.unique(fams)))
    idx = {f: i for i, f in enumerate(uniq)}
    rf = np.asarray([idx[f] for f in fams])
    s = eligible.attack_success.to_numpy(float)
    rng = np.random.default_rng(int.from_bytes(hashlib.blake2b(
        seed_material.encode(), digest_size=8).digest(), "little"))
    draws = np.empty(nboot)
    for r in range(nboot):
        c = np.bincount(rng.integers(0, len(uniq), len(uniq)), minlength=len(uniq))
        w = c[rf]
        t = w.sum()
        draws[r] = (w * s).sum() / t if t else np.nan
    draws = draws[np.isfinite(draws)]
    return (float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5)))


def best_of(frame, target, tier):
    """Per-observation strongest attack within a tier (lowest adversarial score)."""
    g = frame[(frame.target_model == target) & (frame.tier == tier)]
    if not len(g):
        return None
    idx = g.groupby(KEY).adversarial_score.idxmin()
    best = g.loc[idx].copy()
    best["attack_success"] = best.clean_detected & (best.adversarial_score < best.threshold)
    return best


def asr(g):
    e = g[g.clean_detected]
    return float(e.attack_success.mean()) if len(e) else np.nan


def paired(frame, left, right, tier, nboot):
    a, b = best_of(frame, left, tier), best_of(frame, right, tier)
    if a is None or b is None:
        return None
    a = a.set_index(KEY).sort_index()
    b = b.set_index(KEY).sort_index()
    shared = a.index.intersection(b.index)
    a, b = a.loc[shared], b.loc[shared]
    elig = a.clean_detected.to_numpy(bool) & b.clean_detected.to_numpy(bool)
    if not elig.any():
        return None
    fams = a.family_id.to_numpy()
    uniq = np.asarray(sorted(pd.unique(fams)))
    idx = {f: i for i, f in enumerate(uniq)}
    rf = np.asarray([idx[f] for f in fams])
    sa, sb = a.attack_success.to_numpy(float), b.attack_success.to_numpy(float)
    rng = np.random.default_rng(int.from_bytes(hashlib.blake2b(
        f"phase4:{left}:{right}:{tier}".encode(), digest_size=8).digest(), "little"))
    draws = np.empty(nboot)
    for r in range(nboot):
        c = np.bincount(rng.integers(0, len(uniq), len(uniq)), minlength=len(uniq))
        w = c[rf] * elig
        t = w.sum()
        draws[r] = ((w * (sa - sb)).sum() / t) if t else np.nan
    draws = draws[np.isfinite(draws)]
    ci = [float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))]
    return dict(tier=tier, left=left, right=right,
                left_ASR=float(sa[elig].mean()), right_ASR=float(sb[elig].mean()),
                difference=float((sa[elig] - sb[elig]).mean()), CI95=ci,
                excludes_zero=bool(ci[0] > 0 or ci[1] < 0),
                n_paired_eligible=int(elig.sum()), n_families=int(len(uniq)),
                seed_scope=sorted({int(s) for s, _, _ in shared}),
                provenance="regenerated_experiment")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--nboot", type=int, default=NBOOT)
    parser.add_argument("--glob", default="tiered_attack_rows_s*.csv.gz")
    args = parser.parse_args()
    files = sorted(glob.glob(os.path.join(IN, args.glob)))
    if not files:
        raise SystemExit(f"no Phase 4 outputs matching {args.glob}")
    frame = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    seeds = sorted(int(s) for s in frame.seed.unique())
    folds = sorted(int(f) for f in frame.fold.unique())
    print(f"[phase4-an] {len(frame)} rows | seeds={seeds} folds={folds} "
          f"tiers={sorted(frame.tier.unique())}\n", flush=True)

    rows = []
    for target in [t for t in ORDER if t in set(frame.target_model)]:
        for tier in ["A", "B", "C"]:
            g = frame[(frame.target_model == target) & (frame.tier == tier)]
            if not len(g):
                continue
            best = best_of(frame, target, tier)
            lo, hi = family_ci(best, f"phase4:{target}:{tier}", args.nboot)
            clean = float(best.clean_detected.mean())
            total = int(best.shape[0])
            survived = int((best.clean_detected & ~best.attack_success).sum())
            per_method = {}
            for m in sorted(g.method.unique()):
                per_method[m] = asr(g[g.method == m])
            rows.append(dict(
                model=target, tier=tier, clean_detection=clean,
                **{f"ASR_{m}": v for m, v in per_method.items()},
                ASR_best_of=asr(best), CI95=[lo, hi],
                n_eligible=int(best.clean_detected.sum()),
                n_observations=total, n_families=int(best.family_id.nunique()),
                robust_recall_direct=survived / total if total else np.nan,
                robust_recall_product=clean * (1 - asr(best)),
                # Per-model scope: models were not all run on the same seeds, so a global
                # scope label would misdescribe the single-seed rows.
                seed_scope=sorted(int(s) for s in g.seed.unique()),
                fold_scope=sorted(int(f) for f in g.fold.unique()),
                provenance="regenerated_experiment"))
            print(f"  {target:<20}Tier {tier}  clean={clean:.4f} "
                  f"best-of ASR={asr(best):.4f} [{lo:.4f},{hi:.4f}] "
                  f"RR={survived / total:.4f} n={best.clean_detected.sum()}")

    contrasts = []
    print("\n[phase4-an] central paired comparison (emulator - AuthGuard-Seq):")
    for tier in ["A", "B", "C"]:
        c = paired(frame, "emulator_logreg", "authguard_seq", tier, args.nboot)
        if c:
            contrasts.append(c)
            print(f"   Tier {tier}: emu={c['left_ASR']:.4f} ag={c['right_ASR']:.4f} "
                  f"diff={c['difference']:+.4f} CI=[{c['CI95'][0]:+.4f},{c['CI95'][1]:+.4f}] "
                  f"excl0={c['excludes_zero']} n={c['n_paired_eligible']} "
                  f"fam={c['n_families']}")
    for other in ["flat_cnn", "hist_ngram_xgb"]:
        for tier in ["A", "B", "C"]:
            c = paired(frame, other, "authguard_seq", tier, args.nboot)
            if c:
                contrasts.append(c)

    # Tier-C-only evasions within the evaluated 64-query budget.
    tier_only = []
    for target in [t for t in ORDER if t in set(frame.target_model)]:
        b = best_of(frame, target, "B")
        c = best_of(frame, target, "C")
        if b is None or c is None:
            continue
        b = b.set_index(KEY).sort_index()
        c = c.set_index(KEY).sort_index()
        shared = b.index.intersection(c.index)
        b, c = b.loc[shared], c.loc[shared]
        c_success = c.attack_success.to_numpy(bool) & c.clean_detected.to_numpy(bool)
        b_success = b.attack_success.to_numpy(bool)
        only_c = int((c_success & ~b_success).sum())
        tier_only.append(dict(
            model=target, n_tierC_successes=int(c_success.sum()),
            n_tierC_only=only_c,
            fraction_tierC_only=only_c / int(c_success.sum()) if c_success.sum() else np.nan,
            interpretation=("fraction of Tier-C successes not achieved by Tier B within "
                            "the same 64-query budget; not a claim of logical necessity")))
    print("\n[phase4-an] Tier-C-only evasions within the evaluated budget:")
    for t in tier_only:
        print(f"   {t['model']:<20}{t['n_tierC_only']}/{t['n_tierC_successes']} = "
              f"{t['fraction_tierC_only']:.4f}")

    table = pd.DataFrame(rows)
    table.to_csv(os.path.join(OUT, "phase4_tier_table.csv"), index=False)
    payload = dict(
        phase="4 tiered attack analysis (regenerated checkpoints)",
        script="revision_v2/experiments/sprint_phase4/analyze_tiered.py",
        git_commit=subprocess.run(["git", "rev-parse", "HEAD"], cwd=RV2,
                                  capture_output=True, text=True).stdout.strip(),
        provenance="regenerated_experiment", nboot=args.nboot,
        seed_scope=seeds, fold_scope=folds,
        tier_table=rows, paired_contrasts=contrasts, tier_c_only=tier_only)
    with open(os.path.join(OUT, "phase4_analysis.json"), "w") as fh:
        json.dump(payload, fh, indent=2, default=str)
    print(f"\n[phase4-an] wrote {OUT}")


if __name__ == "__main__":
    main()
