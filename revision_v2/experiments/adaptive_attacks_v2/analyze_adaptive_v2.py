#!/usr/bin/env python3
"""Render the RQ2 adaptive-robustness tables from adaptive_attacks_v2 per-row output.

Reports, per target architecture: clean detection at the nominal 5% FPR operating point,
attack-success rate under each attack strategy with family-clustered CIs, byte overhead,
and cross-model transfer. Aggregation is fold-mean then seed-mean, matching the rest of
the paper, with pooled values shown alongside because the two differ on this corpus.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RV2 = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(RV2, "results", "adaptive_attacks_v2")
NBOOT = 10_000
ORDER = ["authguard_seq", "emulator_logreg", "flat_cnn", "hist_ngram_xgb"]
LABELS = {"authguard_seq": "AuthGuard-Seq", "emulator_logreg": "15-feature emulator (logreg)",
          "flat_cnn": "Flat CNN", "hist_ngram_xgb": "Hist.+4-gram XGBoost"}
METHOD_LABELS = {"F200": "Flood-200% (fixed)", "fixed_oracle_best": "Best fixed transform",
                 "random_search": "Random search", "beam_search": "Beam search (adaptive)"}


def load(tag_glob):
    frames = [pd.read_csv(path) for path in sorted(glob.glob(
        os.path.join(OUT, f"attack_per_row{tag_glob}.csv.gz")))]
    if not frames:
        raise SystemExit(f"no attack_per_row{tag_glob}.csv.gz under {OUT}")
    return pd.concat(frames, ignore_index=True)


def asr(group):
    eligible = group[group["clean_detected"]]
    return float(eligible["attack_success"].mean()) if len(eligible) else np.nan


def fold_then_seed(group):
    """Fold-mean then seed-mean ASR, matching the paper's aggregation."""
    per_fold = group.groupby(["seed", "fold"]).apply(asr, include_groups=False)
    per_seed = per_fold.groupby("seed").mean()
    return float(per_seed.mean()), float(per_seed.std(ddof=0)), int(per_seed.size)


def zero_event_upper_bound(group):
    """Rule-of-three 95% upper bound when no attack succeeded.

    A percentile bootstrap over an all-zeros vector returns a degenerate [0, 0] interval,
    which asserts far more certainty than the data supports. With zero successes the
    standard bound is 3/n, and the independent unit here is the bytecode family, not the
    row, because rows inside a family are near-duplicates.
    """
    eligible = group[group["clean_detected"]]
    if not len(eligible) or eligible["attack_success"].any():
        return None
    n_families = int(pd.Series(eligible["family_id"]).nunique())
    return 3.0 / n_families if n_families else None


def family_ci(group, seed_material):
    eligible = group[group["clean_detected"]]
    if not len(eligible):
        return (np.nan, np.nan)
    families = eligible["family_id"].to_numpy()
    unique = np.asarray(sorted(pd.unique(families)))
    index = {family: i for i, family in enumerate(unique)}
    row_family = np.asarray([index[f] for f in families])
    success = eligible["attack_success"].to_numpy(dtype=float)
    rng = np.random.default_rng(int.from_bytes(hashlib.blake2b(
        seed_material.encode(), digest_size=8).digest(), "little"))
    draws = np.empty(NBOOT)
    for replicate in range(NBOOT):
        counts = np.bincount(rng.integers(0, len(unique), len(unique)), minlength=len(unique))
        weights = counts[row_family]
        total = weights.sum()
        draws[replicate] = (weights * success).sum() / total if total else np.nan
    draws = draws[np.isfinite(draws)]
    return (float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5)))


def paired(rows, target_a, target_b, method):
    a = rows[(rows.target_model == target_a) & (rows.method == method)].set_index(["seed", "sid"])
    b = rows[(rows.target_model == target_b) & (rows.method == method)].set_index(["seed", "sid"])
    shared = a.index.intersection(b.index)
    a, b = a.loc[shared].sort_index(), b.loc[shared].sort_index()
    eligible = (a.clean_detected.to_numpy(bool) & b.clean_detected.to_numpy(bool))
    if not eligible.any():
        return None
    families = a.family_id.to_numpy()
    unique = np.asarray(sorted(pd.unique(families)))
    index = {family: i for i, family in enumerate(unique)}
    row_family = np.asarray([index[f] for f in families])
    sa = a.attack_success.to_numpy(float)
    sb = b.attack_success.to_numpy(float)
    rng = np.random.default_rng(int.from_bytes(hashlib.blake2b(
        f"7702:paired:{target_a}:{target_b}:{method}".encode(), digest_size=8).digest(), "little"))
    draws = np.empty(NBOOT)
    for replicate in range(NBOOT):
        counts = np.bincount(rng.integers(0, len(unique), len(unique)), minlength=len(unique))
        weights = counts[row_family] * eligible
        total = weights.sum()
        draws[replicate] = ((weights * (sa - sb)).sum() / total) if total else np.nan
    draws = draws[np.isfinite(draws)]
    ci = [float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))]
    return dict(point=float((sa[eligible] - sb[eligible]).mean()), CI95=ci,
                excludes_zero=bool(ci[0] > 0 or ci[1] < 0),
                n_paired_eligible=int(eligible.sum()))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag-glob", default="_seed*")
    args = parser.parse_args()
    rows = load(args.tag_glob)
    methods = [m for m in ("F200", "fixed_oracle_best", "random_search", "beam_search")
               if m in set(rows.method)]
    targets = [t for t in ORDER if t in set(rows.target_model)]

    print(f"sources={rows.sid.nunique()} seeds={sorted(rows.seed.unique())} "
          f"folds={sorted(rows.fold.unique())} rows={len(rows)}\n")

    records = []
    for target in targets:
        sub = rows[rows.target_model == target]
        clean = sub.drop_duplicates(["seed", "sid"])["clean_detected"].mean()
        for method in methods:
            group = sub[sub.method == method]
            mean, sd, n_seeds = fold_then_seed(group)
            low, high = family_ci(group, f"7702:{target}:{method}")
            rule_of_three = zero_event_upper_bound(group)
            if rule_of_three is not None:
                low, high = 0.0, rule_of_three
            records.append(dict(
                target=target, method=method, clean_detection_rate=float(clean),
                ASR_foldseed_mean=mean, ASR_foldseed_sd=sd, n_seeds=n_seeds,
                zero_events=bool(rule_of_three is not None),
                ASR_pooled=asr(group), ASR_pooled_CI_low=low, ASR_pooled_CI_high=high,
                eligible=int(group["clean_detected"].sum()),
                byte_overhead_mean=float(group.byte_overhead.mean()),
                structural_validity=float(group.structural_valid.mean()),
                score_reduction_mean=float(group.score_reduction.mean())))
    table = pd.DataFrame(records)
    table.to_csv(os.path.join(OUT, "adaptive_v2_summary_table.csv"), index=False)

    print("== ASR by target and attack strategy (pooled, family-clustered 95% CI) ==")
    for target in targets:
        rows_for_target = table[table.target == target]
        clean_rate = float(rows_for_target.clean_detection_rate.iloc[0])
        print(f"\n{LABELS[target]}  (clean detection @5%FPR = {clean_rate:.3f})")
        for _, r in rows_for_target.iterrows():
            bound = "<=" if r.zero_events else "  "
            note = " (rule-of-three, 0 successes)" if r.zero_events else ""
            print(f"  {METHOD_LABELS[r.method]:<26} ASR={r.ASR_pooled:.3f} "
                  f"{bound}[{r.ASR_pooled_CI_low:.3f},{r.ASR_pooled_CI_high:.3f}]  "
                  f"n_elig={r.eligible:<5d} overhead={r.byte_overhead_mean:.2f}x  "
                  f"foldseed={r.ASR_foldseed_mean:.3f}+/-{r.ASR_foldseed_sd:.3f}{note}")

    contrasts = {}
    for method in methods:
        for other in targets:
            if other == "authguard_seq" or "authguard_seq" not in targets:
                continue
            result = paired(rows, other, "authguard_seq", method)
            if result:
                contrasts[f"{other}_minus_authguard_seq::{method}"] = result
    print("\n== Paired family-clustered ASR contrasts (baseline - AuthGuard-Seq) ==")
    for key, value in contrasts.items():
        print(f"  {key:<52} {value['point']:+.3f} "
              f"[{value['CI95'][0]:+.3f},{value['CI95'][1]:+.3f}] "
              f"excludes_zero={value['excludes_zero']} n={value['n_paired_eligible']}")

    transfer = {}
    for target in targets:
        group = rows[(rows.target_model == target) & (rows.method == "beam_search")]
        for column in group.columns:
            if column.startswith("transfer_") and column.endswith("_success"):
                other = column[len("transfer_"):-len("_success")]
                detect = f"transfer_{other}_clean_detected"
                if detect not in group or group[detect].isna().all():
                    continue
                eligible = group[group[detect].fillna(False).astype(bool)]
                if len(eligible):
                    transfer[f"{target}->{other}"] = float(eligible[column].mean())
    print("\n== Beam-search transfer ASR (attack built against row target, scored by other) ==")
    for key, value in sorted(transfer.items()):
        print(f"  {key:<40} {value:.3f}")

    with open(os.path.join(OUT, "adaptive_v2_analysis.json"), "w") as handle:
        json.dump(dict(table=records, paired_contrasts=contrasts, transfer_asr=transfer),
                  handle, indent=2)
    print(f"\nwrote {OUT}/adaptive_v2_summary_table.csv and adaptive_v2_analysis.json")


if __name__ == "__main__":
    main()
