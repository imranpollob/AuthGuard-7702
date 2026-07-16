#!/usr/bin/env python3
"""Phase 1D — family-clustered bootstrap for G-DET v2 headline claims.

Reads pooled per-row test scores (revision_v2/results/gdet_v2/gdet_v2_per_row_scores.csv).
Under leave-family-out, each row appears once as a test observation, so the pooled seed-7702
predictions form one prediction/row. Bootstrap resamples frozen test families with replacement,
retaining all rows of each sampled family (uncertainty_protocol_v2.md).

Targets:
  1. AuthGuard G-DET AUPRC (primary) with 95% CI.
  2. Paired ΔAUPRC AuthGuard - strongest bytecode baseline (chosen by fold-mean AUPRC).
  3. AuthGuard random-split minus family-grouped AUPRC.
"""
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))
from harness import RV2, SEED  # noqa: E402

GDET = os.path.join(RV2, "results", "gdet_v2")
OUT = os.path.join(RV2, "results", "uncertainty")
NBOOT = 10_000
BASELINES = ["opcode_xgb", "opcode_rf", "selector_model"]


def seed_for(name):
    return int.from_bytes(hashlib.blake2b(f"{SEED}:{name}".encode(), digest_size=8).digest(),
                          "little")


def pooled(df, task, split, model, seed=SEED):
    d = df[(df["task"] == task) & (df["split"] == split) & (df["model"] == model) &
           (df["seed"] == seed)]
    return d.drop_duplicates("sid")


def boot_auprc(y, s, fam, name):
    families = np.array(sorted(pd.unique(fam)))
    idx = {f: i for i, f in enumerate(families)}
    obs_fam = np.array([idx[f] for f in fam])
    nf = len(families)
    rng = np.random.default_rng(seed_for(name))
    out = np.empty(NBOOT)
    for b in range(NBOOT):
        counts = np.bincount(rng.integers(0, nf, nf), minlength=nf)
        w = counts[obs_fam]
        out[b] = average_precision_score(y, s, sample_weight=w)
    return out


def paired_boot(y, s_a, s_b, fam, name):
    families = np.array(sorted(pd.unique(fam)))
    idx = {f: i for i, f in enumerate(families)}
    obs_fam = np.array([idx[f] for f in fam])
    nf = len(families)
    rng = np.random.default_rng(seed_for(name))
    out = np.empty(NBOOT)
    for b in range(NBOOT):
        counts = np.bincount(rng.integers(0, nf, nf), minlength=nf)
        w = counts[obs_fam]
        out[b] = (average_precision_score(y, s_a, sample_weight=w) -
                  average_precision_score(y, s_b, sample_weight=w))
    return out


def ci(a):
    return [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))]


def main():
    os.makedirs(OUT, exist_ok=True)
    df = pd.read_csv(os.path.join(GDET, "gdet_v2_per_row_scores.csv"))
    res = json.load(open(os.path.join(GDET, "gdet_v2_results.json")))
    task = "primary"

    # strongest bytecode baseline by fold-mean AUPRC (family split)
    lfo = res[task]["leave_family_out"]
    strongest = max(BASELINES, key=lambda m: lfo[m]["mean"]["AUPRC"])

    ag = pooled(df, task, "family", "authguard")
    y, fam = ag["y"].to_numpy(), ag["family_id"].to_numpy()
    s_ag = ag["score"].to_numpy()
    point_ag = float(average_precision_score(y, s_ag))
    d_ag = boot_auprc(y, s_ag, fam, "authguard_auprc")

    base = pooled(df, task, "family", strongest)
    base = base.set_index("sid").loc[ag["sid"]].reset_index()
    s_base = base["score"].to_numpy()
    point_base = float(average_precision_score(y, s_base))
    d_pair = paired_boot(y, s_ag, s_base, fam, f"paired_{strongest}")

    agr = pooled(df, task, "random", "authguard")
    yr, famr = agr["y"].to_numpy(), agr["family_id"].to_numpy()
    s_agr = agr["score"].to_numpy()
    point_rand = float(average_precision_score(yr, s_agr))
    # random-minus-family gap: paired by family requires same families/rows; both are the
    # full primary population scored under different splits -> align by sid
    agr2 = agr.set_index("sid").loc[ag["sid"]].reset_index()
    d_gap = paired_boot(y, agr2["score"].to_numpy(), s_ag, fam, "random_minus_family")

    payload = dict(
        method="family-clustered percentile bootstrap; sample frozen test families with "
               "replacement, retain all rows of each sampled family; seed=7702",
        replicates=NBOOT, task=task, strongest_baseline=strongest,
        authguard_AUPRC=dict(point=point_ag, CI95=ci(d_ag),
                             boot_mean=float(d_ag.mean()), boot_std=float(d_ag.std())),
        authguard_minus_strongest_baseline=dict(
            baseline=strongest, authguard=point_ag, baseline_point=point_base,
            delta_point=point_ag - point_base, delta_CI95=ci(d_pair),
            excludes_zero=bool(ci(d_pair)[0] > 0 or ci(d_pair)[1] < 0)),
        random_minus_family_AUPRC=dict(
            random=point_rand, family=point_ag, delta_point=point_rand - point_ag,
            delta_CI95=ci(d_gap), excludes_zero=bool(ci(d_gap)[0] > 0 or ci(d_gap)[1] < 0)),
    )
    with open(os.path.join(OUT, "gdet_bootstrap.json"), "w") as f:
        json.dump(payload, f, indent=2)
    print(json.dumps({k: v for k, v in payload.items()
                      if k not in ("method",)}, indent=1, default=str)[:1200])


if __name__ == "__main__":
    main()
