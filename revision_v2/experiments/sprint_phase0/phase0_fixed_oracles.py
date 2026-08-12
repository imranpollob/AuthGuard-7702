#!/usr/bin/env python3
"""Phase 0 — restricted fixed-oracle ASR recomputed from stored adversarial scores.

No models are loaded and no search is re-run. The stored attack records hold the
adversarial score of every one of the seven fixed conditions individually, so a
restricted fixed oracle over any SUBSET of them is exactly computable: take the
per-source minimum adversarial score over the subset and apply the unchanged ASR
definition (clean_score >= threshold and adversarial_score < threshold).

Tier membership follows the sprint specification and the existing execution audit,
not code inspection. The available conditions constrain what each tier can contain:

  M1  = metadata rewrite ALONE
  M2  = metadata + address rewrite + flood 20%
  M3  = metadata + address + selector rewrite + flood 20%
  F25/F50/F100/F200 = flooding alone

Address rewrite and selector rewrite were never evaluated in isolation, and neutral
instruction insertion is not a fixed condition at all (it exists only in the adaptive
action space). Tier B-fixed is therefore metadata + flooding only, and is labelled
the "available" Tier-B fixed oracle per the sprint instruction.

Bootstrap procedure and replicate count are imported unchanged from the analyzer that
produced the published numbers.
"""
from __future__ import annotations

import argparse
import glob
import importlib.util
import json
import os
import subprocess
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RV2 = os.path.abspath(os.path.join(HERE, "..", ".."))
RESULTS = os.path.join(RV2, "results", "adaptive_attacks_v2")
OUT = os.path.join(RV2, "results", "sprint_phase0")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


analyzer = _load("analyze_adaptive_v2", os.path.join(
    RV2, "experiments", "adaptive_attacks_v2", "analyze_adaptive_v2.py"))

FLOODS = ["F25", "F50", "F100", "F200"]
TIERS = {
    "A_fixed": FLOODS,                                  # audit-supported: flooding only
    "B_fixed_available": FLOODS + ["M1"],               # + metadata rewrite alone
    "C_fixed": FLOODS + ["M1", "M2", "M3"],             # all seven stored conditions
}
PRIMARY = ["authguard_seq", "emulator_logreg", "flat_cnn", "hist_ngram_xgb"]
KEY = ["seed", "fold", "sid", "target_model"]


def git_commit():
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=RV2, capture_output=True,
                          text=True).stdout.strip()


def load_primary_records():
    """Stored attack records for the four primary targets, 3 seeds each.

    The _ext file is excluded: it carries the augmented and 30K-control targets at a
    single seed, which must never be pooled with the 3-seed primary blocks.
    """
    files = [f for f in sorted(glob.glob(os.path.join(RESULTS, "attack_per_row_seed*.csv.gz")))
             if not f.endswith("_ext.csv.gz")]
    frame = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    return frame[frame.target_model.isin(PRIMARY)].copy(), files


def tier_oracle(frame, conditions):
    """Per-source strongest (minimum) adversarial score over `conditions`.

    Returns one row per (seed, fold, sid, target_model) carrying the oracle score and
    the unchanged clean/threshold fields, so the stock ASR definition applies verbatim.
    """
    sub = frame[frame.method.isin(conditions)]
    got = sub.groupby(KEY).method.nunique()
    missing = got[got != len(conditions)]
    if len(missing):
        raise SystemExit(f"incomplete condition coverage for {len(missing)} keys")
    idx = sub.groupby(KEY).adversarial_score.idxmin()
    best = sub.loc[idx].copy()
    best["attack_success"] = best.clean_detected & (best.adversarial_score < best.threshold)
    best["unconditional_evasion"] = best.adversarial_score < best.threshold
    return best


def summarise(best, target, tier, seed_scope, fold_scope):
    g = best[best.target_model == target]
    eligible = g[g.clean_detected]
    asr = float(eligible.attack_success.mean()) if len(eligible) else np.nan
    lo, hi = analyzer.family_ci(g, f"phase0:{target}:{tier}")
    clean = float(g.drop_duplicates(["seed", "sid"]).clean_detected.mean())
    # Direct robust recall over ALL positive source-seed observations, not a product.
    total = g.drop_duplicates(["seed", "sid"]).shape[0]
    survived = int(((g.clean_detected) & (~g.attack_success)).sum())
    return dict(
        model=target, tier=tier, clean_detection=clean, ASR=asr,
        CI95=[lo, hi], n_eligible=int(len(eligible)),
        n_source_seed_observations=total, n_families=int(g.family_id.nunique()),
        robust_recall_direct=survived / total if total else np.nan,
        robust_recall_product=clean * (1 - asr) if not np.isnan(asr) else np.nan,
        seed_scope=seed_scope, fold_scope=fold_scope,
        provenance="stored_artifact")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--nboot", type=int, default=analyzer.NBOOT)
    args = parser.parse_args()
    analyzer.NBOOT = args.nboot
    os.makedirs(OUT, exist_ok=True)

    frame, files = load_primary_records()
    seeds = sorted(int(s) for s in frame.seed.unique())
    folds = sorted(int(f) for f in frame.fold.unique())
    print(f"[phase0] {len(frame)} rows | targets={sorted(frame.target_model.unique())} "
          f"| seeds={seeds} | folds={folds}", flush=True)

    rows, oracles = [], {}
    for tier, conditions in TIERS.items():
        best = tier_oracle(frame, conditions)
        oracles[tier] = best
        for target in PRIMARY:
            rows.append(summarise(best, target, tier, seeds, folds))
            print(f"  {tier:<20}{target:<20}ASR={rows[-1]['ASR']:.4f} "
                  f"n_elig={rows[-1]['n_eligible']}", flush=True)

    # Correctness gate: Tier C-fixed must equal the stored fixed_oracle_best exactly.
    stored = frame[frame.method == "fixed_oracle_best"].set_index(KEY).sort_index()
    recomputed = oracles["C_fixed"].set_index(KEY).sort_index()
    shared = stored.index.intersection(recomputed.index)
    delta = (stored.loc[shared].adversarial_score.to_numpy()
             - recomputed.loc[shared].adversarial_score.to_numpy())
    mismatch_score = int((np.abs(delta) > 1e-12).sum())
    mismatch_success = int((stored.loc[shared].attack_success.to_numpy()
                            != recomputed.loc[shared].attack_success.to_numpy()).sum())
    gate = dict(n_compared=int(len(shared)),
                score_mismatches=mismatch_score,
                attack_success_mismatches=mismatch_success,
                max_abs_score_delta=float(np.abs(delta).max()) if len(delta) else 0.0,
                passed=bool(mismatch_score == 0 and mismatch_success == 0))
    print(f"\n[phase0] Tier C-fixed vs stored fixed_oracle_best: "
          f"{'PASS' if gate['passed'] else 'FAIL'} "
          f"(n={gate['n_compared']}, score mismatches={mismatch_score}, "
          f"success mismatches={mismatch_success})", flush=True)

    table = pd.DataFrame(rows)
    table.to_csv(os.path.join(OUT, "phase0_fixed_oracle_table.csv"), index=False)
    payload = dict(
        phase="0.2 restricted fixed oracles from stored scores",
        script="revision_v2/experiments/sprint_phase0/phase0_fixed_oracles.py",
        git_commit=git_commit(), input_files=[os.path.basename(f) for f in files],
        nboot=args.nboot, tier_definitions=TIERS,
        condition_semantics={
            "M1": "metadata rewrite alone",
            "M2": "metadata + address rewrite + flood 20%",
            "M3": "metadata + address + selector rewrite + flood 20%",
            "F25/F50/F100/F200": "flooding alone at 25/50/100/200%",
            "neutral insertion": "NOT available as a fixed condition (adaptive action only)",
        },
        tier_c_reproduction_gate=gate, rows=rows)
    with open(os.path.join(OUT, "phase0_fixed_oracles.json"), "w") as handle:
        json.dump(payload, handle, indent=2)
    for tier, best in oracles.items():
        best.to_csv(os.path.join(OUT, f"phase0_oracle_{tier}.csv.gz"),
                    index=False, compression="gzip")
    print(f"[phase0] wrote {OUT}", flush=True)
    return 0 if gate["passed"] else 2


if __name__ == "__main__":
    sys.exit(main())
