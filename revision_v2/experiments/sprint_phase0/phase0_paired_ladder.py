#!/usr/bin/env python3
"""Phase 0.3 — AuthGuard-Seq vs emulator paired ladder over restricted fixed oracles.

Paired family-clustered bootstrap, procedure and replicate count imported unchanged
from the analyzer that produced the published contrasts. Pairing is over the
intersection of source-seed observations cleanly detected by BOTH models.
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
RESULTS = os.path.join(RV2, "results", "adaptive_attacks_v2")
OUT = os.path.join(RV2, "results", "sprint_phase0")
sys.path.insert(0, HERE)

phase0 = importlib.util.spec_from_file_location(
    "phase0", os.path.join(HERE, "phase0_fixed_oracles.py"))
_mod = importlib.util.module_from_spec(phase0)
sys.modules["phase0"] = _mod
phase0.loader.exec_module(_mod)

LEFT, RIGHT = "emulator_logreg", "authguard_seq"


def paired_contrast(best, nboot, label):
    """emulator - AuthGuard ASR, paired on (seed, sid), family-clustered."""
    a = best[best.target_model == LEFT].set_index(["seed", "sid"]).sort_index()
    b = best[best.target_model == RIGHT].set_index(["seed", "sid"]).sort_index()
    shared = a.index.intersection(b.index)
    a, b = a.loc[shared], b.loc[shared]
    eligible = a.clean_detected.to_numpy(bool) & b.clean_detected.to_numpy(bool)
    if not eligible.any():
        return None
    families = a.family_id.to_numpy()
    unique = np.asarray(sorted(pd.unique(families)))
    index = {f: i for i, f in enumerate(unique)}
    row_family = np.asarray([index[f] for f in families])
    sa = a.attack_success.to_numpy(float)
    sb = b.attack_success.to_numpy(float)
    rng = np.random.default_rng(int.from_bytes(hashlib.blake2b(
        f"7702:paired:{LEFT}:{RIGHT}:{label}".encode(), digest_size=8).digest(), "little"))
    draws = np.empty(nboot)
    for r in range(nboot):
        counts = np.bincount(rng.integers(0, len(unique), len(unique)), minlength=len(unique))
        w = counts[row_family] * eligible
        total = w.sum()
        draws[r] = ((w * (sa - sb)).sum() / total) if total else np.nan
    draws = draws[np.isfinite(draws)]
    ci = [float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))]
    return dict(
        condition=label,
        emulator_ASR=float(sa[eligible].mean()),
        authguard_ASR=float(sb[eligible].mean()),
        difference=float((sa[eligible] - sb[eligible]).mean()),
        CI95=ci, excludes_zero=bool(ci[0] > 0 or ci[1] < 0),
        n_paired_eligible=int(eligible.sum()),
        n_paired_shared_keys=int(len(shared)),
        n_families=int(len(unique)),
        n_distinct_sources=int(a.reset_index().sid.nunique()),
        replicates=int(len(draws)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--nboot", type=int, default=_mod.analyzer.NBOOT)
    args = parser.parse_args()
    os.makedirs(OUT, exist_ok=True)
    frame, files = _mod.load_primary_records()

    conditions = {
        "Flood-200 only": ["F200"],
        "Tier A fixed oracle (flooding)": _mod.FLOODS,
        "Tier B fixed oracle (flooding + metadata)": _mod.FLOODS + ["M1"],
        "Tier C fixed oracle (all seven)": _mod.FLOODS + ["M1", "M2", "M3"],
    }
    out = []
    for label, conds in conditions.items():
        best = _mod.tier_oracle(frame, conds)
        r = paired_contrast(best, args.nboot, label)
        out.append(r)
        print(f"  {label:<44} emu={r['emulator_ASR']:.4f} ag={r['authguard_ASR']:.4f} "
              f"diff={r['difference']:+.4f} CI=[{r['CI95'][0]:+.4f},{r['CI95'][1]:+.4f}] "
              f"excl0={r['excludes_zero']} n={r['n_paired_eligible']}", flush=True)

    # Derivation of the published 1,512 figure, verified from data.
    beam = frame[frame.method == "beam_search"]
    a = beam[beam.target_model == LEFT].set_index(["seed", "sid"]).sort_index()
    b = beam[beam.target_model == RIGHT].set_index(["seed", "sid"]).sort_index()
    shared = a.index.intersection(b.index)
    a2, b2 = a.loc[shared], b.loc[shared]
    both = int((a2.clean_detected.to_numpy(bool) & b2.clean_detected.to_numpy(bool)).sum())
    derivation = dict(
        distinct_source_contracts=int(a2.reset_index().sid.nunique()),
        seeds=sorted(int(s) for s in a2.reset_index().seed.unique()),
        source_seed_observations=int(len(shared)),
        cleanly_detected_by_both=both,
        note=("The published 'eligible sources' figure counts source-seed observations, "
              "not distinct contracts: 727 contracts x 3 seeds = 2181 observations, of "
              "which this many are cleanly detected by both models."))
    print(f"\n  1,512 derivation -> {derivation['distinct_source_contracts']} sources x "
          f"{len(derivation['seeds'])} seeds = {derivation['source_seed_observations']} "
          f"observations; both-detected = {both}")

    payload = dict(
        phase="0.3 paired fixed-oracle ladder",
        script="revision_v2/experiments/sprint_phase0/phase0_paired_ladder.py",
        git_commit=_mod.git_commit(), input_files=[os.path.basename(f) for f in files],
        nboot=args.nboot, seed_scope=[7702, 7703, 7704], fold_scope=[0, 1, 2, 3, 4],
        provenance="stored_artifact", ladder=out,
        eligible_population_derivation=derivation)
    with open(os.path.join(OUT, "phase0_paired_ladder.json"), "w") as handle:
        json.dump(payload, handle, indent=2)
    pd.DataFrame(out).to_csv(os.path.join(OUT, "phase0_paired_ladder.csv"), index=False)
    print(f"[phase0.3] wrote {OUT}")


if __name__ == "__main__":
    main()
