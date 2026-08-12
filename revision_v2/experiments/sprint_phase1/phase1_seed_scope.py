#!/usr/bin/env python3
"""Phase 1.1 — seed-scope repair and reconciliation of the published contrasts.

The manuscript reports a -0.133 augmentation contrast and a -0.129 matched-attention
contrast, while the displayed table values give 0.181 - 0.062 = 0.119 and 0.181 - 0.075
= 0.106. This determines exactly which populations produce each figure and whether the
published contrasts are correct.

Three things differ between the displayed subtraction and the paired contrast:
  1. Seed scope. The clean AuthGuard-Seq row pools 3 seeds; the augmented and 30K rows
     are seed 7702 only. Subtracting them is a cross-seed-scope operation.
  2. Eligible population. A paired contrast is computed only over observations that BOTH
     models detect cleanly, not over each model's own eligible set.
  3. Aggregation. The paired statistic is the mean of per-observation differences on the
     shared population, which is not the difference of the two marginal means.
"""
from __future__ import annotations

import glob
import hashlib
import importlib.util
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RV2 = os.path.abspath(os.path.join(HERE, "..", ".."))
RESULTS = os.path.join(RV2, "results", "adaptive_attacks_v2")
OUT = os.path.join(RV2, "results", "sprint_phase1")

spec = importlib.util.spec_from_file_location("phase0", os.path.join(
    RV2, "experiments", "sprint_phase0", "phase0_fixed_oracles.py"))
_p0 = importlib.util.module_from_spec(spec)
sys.modules["phase0"] = _p0
spec.loader.exec_module(_p0)
NBOOT = _p0.analyzer.NBOOT

METHODS = ["F200", "fixed_oracle_best", "beam_search", "random_search"]


def load_all():
    frames = {}
    for f in sorted(glob.glob(os.path.join(RESULTS, "attack_per_row_seed*.csv.gz"))):
        frames[os.path.basename(f)] = pd.read_csv(f)
    return frames


def asr(g):
    e = g[g.clean_detected]
    return float(e.attack_success.mean()) if len(e) else np.nan


def paired(frame, left, right, method, label):
    a = frame[(frame.target_model == left) & (frame.method == method)]
    b = frame[(frame.target_model == right) & (frame.method == method)]
    a = a.set_index(["seed", "sid"]).sort_index()
    b = b.set_index(["seed", "sid"]).sort_index()
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
        f"7702:paired:{left}:{right}:{method}".encode(), digest_size=8).digest(), "little"))
    draws = np.empty(NBOOT)
    for r in range(NBOOT):
        c = np.bincount(rng.integers(0, len(uniq), len(uniq)), minlength=len(uniq))
        w = c[rf] * elig
        t = w.sum()
        draws[r] = ((w * (sa - sb)).sum() / t) if t else np.nan
    draws = draws[np.isfinite(draws)]
    ci = [float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))]
    return dict(label=label, left=left, right=right, method=method,
                left_ASR_on_shared=float(sa[elig].mean()),
                right_ASR_on_shared=float(sb[elig].mean()),
                paired_difference=float((sa[elig] - sb[elig]).mean()),
                CI95=ci, excludes_zero=bool(ci[0] > 0 or ci[1] < 0),
                n_paired_eligible=int(elig.sum()),
                seeds=sorted(int(s) for s in a.reset_index().seed.unique()))


def main():
    os.makedirs(OUT, exist_ok=True)
    frames = load_all()
    main3 = pd.concat([v for k, v in frames.items()
                       if not k.endswith("_ext.csv.gz")], ignore_index=True)
    ext = frames["attack_per_row_seed7702_ext.csv.gz"]

    report = {}

    # 1.1a seed-7702-only clean-trained AuthGuard-Seq
    ag = main3[(main3.target_model == "authguard_seq") & (main3.seed == 7702)]
    single = {m: asr(ag[ag.method == m]) for m in METHODS}
    single["clean_detection"] = float(
        ag.drop_duplicates(["seed", "sid"]).clean_detected.mean())
    single["n_eligible"] = int(ag[ag.method == "random_search"].clean_detected.sum())
    report["authguard_seq_seed7702_only"] = dict(
        **single, seed_scope=[7702], fold_scope=[0, 1, 2, 3, 4],
        provenance="stored_artifact")
    print("[1.1a] AuthGuard-Seq, seed 7702 only, 5 folds:")
    for k in METHODS:
        print(f"        {k:<20}{single[k]:.4f}")
    print(f"        clean_detection     {single['clean_detection']:.4f}"
          f"  n_elig={single['n_eligible']}")

    # 1.1b which baseline produced -0.133? Test both candidate populations.
    combined = pd.concat([main3, ext], ignore_index=True)
    variants = {}
    for method in ["random_search", "beam_search"]:
        # (i) against the 3-seed clean AuthGuard row as stored (what the analyzer did)
        variants[f"3seed_clean_vs_aug::{method}"] = paired(
            combined, "authguard_seq_aug", "authguard_seq", method,
            "aug (seed7702) vs clean AuthGuard (all seeds present in file)")
        # (ii) like-for-like: restrict the clean model to seed 7702
        like = combined[combined.seed == 7702]
        variants[f"seed7702_like_for_like::{method}"] = paired(
            like, "authguard_seq_aug", "authguard_seq", method,
            "aug vs clean AuthGuard, both seed 7702 only")
        variants[f"seed7702_30K_like_for_like::{method}"] = paired(
            like, "chunk_attention_16384", "authguard_seq", method,
            "30K matched attention vs clean AuthGuard, both seed 7702 only")
    report["contrast_variants"] = {k: v for k, v in variants.items() if v}
    print("\n[1.1b] contrast reconciliation:")
    for k, v in variants.items():
        if v:
            print(f"   {k:<46} diff={v['paired_difference']:+.4f} "
                  f"CI=[{v['CI95'][0]:+.4f},{v['CI95'][1]:+.4f}] n={v['n_paired_eligible']} "
                  f"seeds={v['seeds']}")

    # 1.1c marginal ASR of each row as displayed in the paper table
    marg = {}
    for target, src in [("authguard_seq", main3), ("authguard_seq_aug", ext),
                        ("chunk_attention_16384", ext)]:
        g = src[src.target_model == target]
        marg[target] = dict(
            random_search=asr(g[g.method == "random_search"]),
            beam_search=asr(g[g.method == "beam_search"]),
            clean_detection=float(g.drop_duplicates(["seed", "sid"]).clean_detected.mean()),
            seeds=sorted(int(s) for s in g.seed.unique()),
            n_eligible_random=int(g[g.method == "random_search"].clean_detected.sum()))
    report["marginal_table_values"] = marg
    print("\n[1.1c] marginal (table) values and their seed scope:")
    for k, v in marg.items():
        print(f"   {k:<24} random={v['random_search']:.4f} clean={v['clean_detection']:.4f} "
              f"seeds={v['seeds']} n_elig={v['n_eligible_random']}")

    # 1.1d explicit row -> seed/fold scope map
    scope = []
    for name, src in [("main_3seed", main3), ("ext_seed7702", ext)]:
        for target in sorted(src.target_model.unique()):
            g = src[src.target_model == target]
            scope.append(dict(
                table_row=target, file_group=name,
                seed_scope=sorted(int(s) for s in g.seed.unique()),
                fold_scope=sorted(int(f) for f in g.fold.unique()),
                n_source_seed_observations=int(g.drop_duplicates(["seed", "sid"]).shape[0]),
                n_distinct_sources=int(g.sid.nunique())))
    report["row_to_seed_scope_map"] = scope
    print("\n[1.1d] row -> seed scope map:")
    for s in scope:
        print(f"   {s['table_row']:<24} seeds={s['seed_scope']} folds={s['fold_scope']} "
              f"obs={s['n_source_seed_observations']}")

    report["provenance"] = "stored_artifact"
    report["script"] = "revision_v2/experiments/sprint_phase1/phase1_seed_scope.py"
    report["git_commit"] = _p0.git_commit()
    with open(os.path.join(OUT, "phase1_seed_scope.json"), "w") as fh:
        json.dump(report, fh, indent=2, default=str)
    print(f"\n[1.1] wrote {OUT}/phase1_seed_scope.json")


if __name__ == "__main__":
    main()
