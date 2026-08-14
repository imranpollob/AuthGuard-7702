#!/usr/bin/env python3
"""RQ4 three-seed replication analysis.

Consumes the per-row attack records for seeds 7702/7703/7704 and emits the per-seed metric
table, the paired contrasts, a machine-readable summary, and the raw copies. Nothing is
retrained here and no attack is re-run.

Three-seed summarisation. The same bytecode families are evaluated under every seed, so the
seed-level results are repeated measures on a shared clustering structure and must not be
pooled as if independent. Two summaries are produced:

  (a) seed-level summary  -- the per-seed family-clustered estimate is computed
      independently for each seed; the replicated effect is reported as the mean and SD
      across the three seed-level point estimates, with the seed as the unit of
      replication. This is the conservative reading and makes no independence assumption
      across seeds.

  (b) family-clustered, seed-averaged estimate -- per-observation differences are first
      averaged within (family, source) across seeds, collapsing the repeated measurement,
      and the family bootstrap is then applied to those collapsed values. This respects
      family clustering and does not treat three evaluations of the same family as three
      independent observations.

Both are reported. Neither is presented as a significance test beyond the interval it states.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import subprocess
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RV2 = os.path.abspath(os.path.join(HERE, "..", ".."))
ATTACKS = os.path.join(RV2, "results", "adaptive_attacks_v2")
OUT = os.path.join(RV2, "results", "rq4_replication_3seed")
sys.path.insert(0, HERE)
import rq4_metrics as M  # noqa: E402

PARAM_COUNTS = {"chunk_attention_16384": 30_050,
                "chunk_mean_16384": 29_985,
                "flat_control_16384": 29_985}
LABEL = {"chunk_attention_16384": "Chunk attention",
         "chunk_mean_16384": "Chunk mean",
         "flat_control_16384": "Flat control"}
SEEDS = [7702, 7703, 7704]
KEY = M.KEY


def commit():
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=RV2,
                          capture_output=True, text=True).stdout.strip()


def load_records():
    """Per-seed attack records for the three controlled models, plus their source files."""
    sources = {
        7702: [os.path.join(ATTACKS, "attack_per_row_seed7702_ext.csv.gz")],
        7703: [os.path.join(ATTACKS, "attack_per_row_seed7703_rq4rep.csv.gz")],
        7704: [os.path.join(ATTACKS, "attack_per_row_seed7704_rq4rep.csv.gz")],
    }
    frames, used = {}, {}
    for seed, paths in sources.items():
        present = [p for p in paths if os.path.exists(p)]
        if not present:
            continue
        f = pd.concat([pd.read_csv(p) for p in present], ignore_index=True)
        f = f[f.target_model.isin(M.MODELS) & (f.seed == seed)]
        frames[seed] = f
        used[seed] = [os.path.relpath(p, RV2) for p in present]
    return frames, used


def thresholds_for(seed):
    """Validation-fitted 5% FPR thresholds per fold and model."""
    tag = "seed7702_ext" if seed == 7702 else f"seed{seed}_rq4rep"
    path = os.path.join(ATTACKS, f"thresholds_{tag}.csv")
    if not os.path.exists(path):
        return {}
    t = pd.read_csv(path)
    t = t[t.model.isin(M.MODELS)]
    return {(int(r.fold), r.model): float(r.threshold_05) for _, r in t.iterrows()}


def per_seed_rows(frames):
    rows = []
    for seed, f in sorted(frames.items()):
        thr = thresholds_for(seed)
        for model in M.MODELS:
            g = f[f.target_model == model]
            if not len(g):
                continue
            clean, n_obs = M.clean_detection(f, model)
            rnd = M.marginal(f, model, "random_search")
            beam = M.marginal(f, model, "beam_search")
            rr = M.robust_recall(f, model)
            searches = g[g.method.isin(M.SEARCH_METHODS)]
            eligible_rows = searches[searches.clean_detected]
            thr_vals = sorted({round(v, 6) for (fold, m), v in thr.items() if m == model})
            rows.append(dict(
                seed=seed, architecture=LABEL[model], model_key=model,
                trainable_parameters=PARAM_COUNTS[model],
                clean_detection_rate=clean,
                n_positive_observations=n_obs,
                validation_thresholds_by_fold=thr_vals,
                n_eligible_observations=rnd["n_eligible"],
                n_eligible_families=rnd["n_eligible_families"],
                random_successes=rnd["successes"], random_ASR=rnd["ASR"],
                beam_successes=beam["successes"], beam_ASR=beam["ASR"],
                robust_recall=rr["robust_recall"],
                invalid_attack_records=int((~searches.structural_valid).sum()),
                failed_attack_records=int((~eligible_rows.attack_success).sum()),
                total_attack_queries=int(searches.queries.sum()),
                clean_AUPRC=None))  # not computable: attacked population is all-positive
    return rows


def per_seed_contrasts(frames, nboot):
    out = []
    for seed, f in sorted(frames.items()):
        for method in M.SEARCH_METHODS:
            for left in ["chunk_mean_16384", "flat_control_16384"]:
                c = M.paired_contrast(f, left, "chunk_attention_16384", method,
                                      f"seed{seed}", nboot)
                if c:
                    c.update(seed=seed, scope="per_seed",
                             estimator="family-clustered bootstrap within seed")
                    out.append(c)
    return out


def seed_averaged_contrast(frames, left, right, method, nboot):
    """Collapse repeated measurement across seeds, then bootstrap families.

    For each source contract, the per-observation success difference is averaged over the
    seeds in which BOTH models detect it cleanly. Sources with no such seed are dropped.
    The resulting one-value-per-source vector is then resampled by family.
    """
    per_source = {}
    for seed, f in sorted(frames.items()):
        a = f[(f.target_model == left) & (f.method == method)].set_index(KEY).sort_index()
        b = f[(f.target_model == right) & (f.method == method)].set_index(KEY).sort_index()
        shared = a.index.intersection(b.index)
        if not len(shared):
            continue
        a, b = a.loc[shared], b.loc[shared]
        elig = a.clean_detected.to_numpy(bool) & b.clean_detected.to_numpy(bool)
        sa = a.attack_success.to_numpy(float)
        sb = b.attack_success.to_numpy(float)
        fam = a.family_id.to_numpy()
        sids = [k[2] for k in a.index]
        for i, sid in enumerate(sids):
            if elig[i]:
                per_source.setdefault(sid, dict(family=fam[i], deltas=[]))["deltas"].append(
                    sa[i] - sb[i])
    if not per_source:
        return None
    sids = sorted(per_source)
    delta = np.asarray([np.mean(per_source[s]["deltas"]) for s in sids])
    fams = np.asarray([per_source[s]["family"] for s in sids])
    n_seeds_per_source = np.asarray([len(per_source[s]["deltas"]) for s in sids])
    draws, n_fam = M._family_bootstrap(
        fams, delta, np.ones(len(delta), dtype=bool),
        f"rq4:seedavg:{left}:{right}:{method}", nboot)
    ci = [float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))]
    return dict(
        label="three_seed_family_clustered_seed_averaged",
        contrast=f"{left} - {right}", method=method, scope="three_seed",
        estimator=("per-source difference averaged over seeds where both models detect "
                   "cleanly, then family-clustered bootstrap"),
        difference=float(delta.mean()), ci_low=ci[0], ci_high=ci[1],
        excludes_zero=bool(ci[0] > 0 or ci[1] < 0),
        n_sources=int(len(delta)), n_families_eligible=int(n_fam),
        mean_seeds_per_source=float(n_seeds_per_source.mean()),
        bootstrap_replicates=int(len(draws)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nboot", type=int, default=M.NBOOT)
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    frames, used = load_records()
    if not frames:
        raise SystemExit("no RQ4 attack records found")
    print(f"[rq4] seeds loaded: {sorted(frames)}", flush=True)

    rows = per_seed_rows(frames)
    per_seed = pd.DataFrame(rows)
    per_seed.to_csv(os.path.join(OUT, "rq4_replication_per_seed.csv"), index=False)

    contrasts = per_seed_contrasts(frames, args.nboot)
    for method in M.SEARCH_METHODS:
        for left in ["chunk_mean_16384", "flat_control_16384"]:
            c = seed_averaged_contrast(frames, left, "chunk_attention_16384",
                                       method, args.nboot)
            if c:
                contrasts.append(c)
    # seed-level mean/SD summary (seed as unit of replication)
    seed_level = []
    cf = pd.DataFrame([c for c in contrasts if c.get("scope") == "per_seed"])
    if len(cf):
        for (contrast, method), grp in cf.groupby(["contrast", "method"]):
            seed_level.append(dict(
                label="three_seed_mean_of_seed_level_estimates", contrast=contrast,
                method=method, scope="three_seed",
                estimator="mean and SD across per-seed family-clustered point estimates",
                difference=float(grp.difference.mean()),
                sd_across_seeds=float(grp.difference.std(ddof=0)),
                n_seeds=int(grp.seed.nunique()),
                min_seed_effect=float(grp.difference.min()),
                max_seed_effect=float(grp.difference.max()),
                all_seeds_positive=bool((grp.difference > 0).all()),
                all_seed_cis_exclude_zero=bool(grp.excludes_zero.all())))
    contrasts.extend(seed_level)
    pd.DataFrame(contrasts).to_csv(
        os.path.join(OUT, "rq4_replication_contrasts.csv"), index=False)

    # aggregate marginal table (mean +/- SD across seeds)
    agg = []
    for model in M.MODELS:
        g = per_seed[per_seed.model_key == model]
        if not len(g):
            continue
        agg.append(dict(
            architecture=LABEL[model], model_key=model,
            trainable_parameters=PARAM_COUNTS[model], n_seeds=int(g.seed.nunique()),
            clean_detection_mean=float(g.clean_detection_rate.mean()),
            clean_detection_sd=float(g.clean_detection_rate.std(ddof=0)),
            random_ASR_mean=float(g.random_ASR.mean()),
            random_ASR_sd=float(g.random_ASR.std(ddof=0)),
            beam_ASR_mean=float(g.beam_ASR.mean()),
            beam_ASR_sd=float(g.beam_ASR.std(ddof=0)),
            robust_recall_mean=float(g.robust_recall.mean()),
            robust_recall_sd=float(g.robust_recall.std(ddof=0))))
    pd.DataFrame(agg).to_csv(os.path.join(OUT, "rq4_replication_aggregate.csv"), index=False)

    summary = dict(
        experiment="RQ4 parameter-matched aggregation controls, three-seed replication",
        git_commit=commit(), seeds=sorted(frames), folds=[0, 1, 2, 3, 4],
        models=M.MODELS, parameter_counts=PARAM_COUNTS,
        attack_action_space="full eight-action space as implemented in search.ACTIONS",
        query_budget=64, beam_width=4, max_depth=4, max_byte_overhead=2.0,
        operating_point="nominal 5% FPR from validation negatives",
        eligibility="clean_score >= validation-fitted 5% FPR threshold",
        attack_success="clean_detected AND adversarial_score < threshold",
        bootstrap_replicates=args.nboot,
        source_files=used,
        per_seed=rows, aggregate=agg, contrasts=contrasts,
        output_dir=os.path.relpath(OUT, RV2))
    with open(os.path.join(OUT, "rq4_replication_summary.json"), "w") as fh:
        json.dump(summary, fh, indent=2, default=str)

    # preserve raw records alongside the derived outputs
    for seed, paths in used.items():
        for p in paths:
            src = os.path.join(RV2, p)
            dst = os.path.join(OUT, "raw_" + os.path.basename(src))
            if not os.path.exists(dst):
                pd.read_csv(src).to_csv(dst, index=False, compression="gzip")

    print(per_seed[["seed", "architecture", "clean_detection_rate", "random_ASR",
                    "beam_ASR", "robust_recall", "n_eligible_observations",
                    "n_eligible_families"]].round(4).to_string(index=False))
    print(f"\n[rq4] wrote {OUT}")


if __name__ == "__main__":
    main()
