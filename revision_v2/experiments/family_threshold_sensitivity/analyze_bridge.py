#!/usr/bin/env python3
"""Bridge analysis: theta=0.85 on the frozen benchmark fold_id.

Produces TWO summaries that are never mixed:

  Estimator A -- the family-threshold sensitivity convention: per-seed marginals, seed-level
                 mean +/- SD, and a per-source seed-averaged paired effect with a
                 family-clustered CI (rq4_metrics.py, unchanged).

  Estimator B -- the main-paper convention, reproducing
                 revision_v2/experiments/sprint_phase4/analyze_tiered.py: per-observation
                 strongest attack within the tier, marginal ASR over the POOLED
                 seed-observations, and a paired contrast whose family-clustered bootstrap
                 runs over the pooled (seed, fold, sid) rows.

Estimator B's code below is a faithful transcription of analyze_tiered.py's `best_of`,
`asr` and `paired`, including the bootstrap seed material, so the bridge numbers are
directly comparable with the frozen main result.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RV2 = os.path.abspath(os.path.join(HERE, "..", ".."))
ROOT = os.path.abspath(os.path.join(RV2, ".."))
OUT = os.path.join(RV2, "results", "family_threshold_sensitivity_bridge")
ATTACKS = os.path.join(RV2, "results", "adaptive_attacks_v2")
SENS = os.path.join(RV2, "results", "family_threshold_sensitivity")
sys.path.insert(0, os.path.join(RV2, "experiments", "rq4_replication"))
import rq4_metrics as M  # noqa: E402

SEEDS = [7702, 7703, 7704]
FOLDS = [0, 1, 2, 3, 4]
MODELS = ["authguard_seq", "emulator_logreg"]
LABEL = {"authguard_seq": "AuthGuard-Seq", "emulator_logreg": "15-feature LR"}
SEARCH = M.SEARCH_METHODS
NBOOT = M.NBOOT
EXCLUDED = ("address", "selector")

FROZEN = dict(authguard_ASR=0.19696147585458493, lr_ASR=0.5416666666666666,
              paired=0.3699268130405855, ci=[0.20790328732981692, 0.5195357752422421],
              n_paired=1503, n_families=209)


def commit():
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()


def load():
    frames, used = {}, {}
    for seed in SEEDS:
        p = os.path.join(ATTACKS, f"attack_per_row_bridge085_s{seed}.csv.gz")
        if not os.path.exists(p):
            raise SystemExit(f"missing bridge attack records: {p}")
        f = pd.read_csv(p)
        if sorted(f.seed.unique()) != [seed]:
            raise SystemExit(f"{p}: unexpected seeds {sorted(f.seed.unique())}")
        if sorted(int(v) for v in f.fold.unique()) != FOLDS:
            raise SystemExit(f"{p}: unexpected folds")
        frames[seed] = f[f.target_model.isin(MODELS)]
        used[str(seed)] = os.path.relpath(p, RV2)
    return frames, used


def verify_actions(frames):
    out = {}
    for seed, f in sorted(frames.items()):
        s = f[f.method.isin(SEARCH)]
        used = set()
        for x in s.sequence.dropna().unique():
            used.update(str(x).split("+"))
        used.discard("clean_noop")
        leaked = sorted(used & set(EXCLUDED))
        if leaked:
            raise SystemExit(f"seed {seed}: Tier-C action {leaked} in a searched sequence")
        out[str(seed)] = dict(searched_rows=int(len(s)),
                              distinct_actions_used=sorted(used),
                              tier_c_actions_observed=leaked,
                              excluded_from_statistics=sorted(
                                  set(f.method.unique()) - set(SEARCH)))
    return out


def verify_folds(frames):
    """The defining property of this condition: attack rows carry the frozen fold_id."""
    bench = pd.read_csv(os.path.join(RV2, "data", "authguardbench_7702_v2.csv.gz"))
    p = bench[bench.population == "PRIMARY_EVALUATION"]
    frozen = dict(zip(p.sample_id.astype(str), p.fold_id.astype(int)))
    sens = pd.read_csv(os.path.join(SENS, "split_manifest_theta085.csv"))
    # The manifest spans every benchmark row; only PRIMARY_EVALUATION rows carry a fold.
    sens = sens.dropna(subset=["fold_id_theta"])
    regen = dict(zip(sens.sample_id.astype(str), sens.fold_id_theta.astype(int)))
    out = {}
    for seed, f in sorted(frames.items()):
        u = f.drop_duplicates("sid")[["sid", "fold", "family_id"]]
        match_frozen = int((u.sid.map(frozen) == u.fold).sum())
        match_regen = int((u.sid.map(regen) == u.fold).sum())
        out[str(seed)] = dict(sources=int(len(u)),
                              rows_matching_frozen_fold_id=match_frozen,
                              rows_matching_regenerated_theta085_fold=match_regen,
                              uses_frozen_folds=bool(match_frozen == len(u)))
        if match_frozen != len(u):
            raise SystemExit(f"seed {seed}: attack rows do not carry the frozen fold_id")
    return out


# --------------------------------------------------------------- ESTIMATOR A (sensitivity)
def estimator_a(frames):
    per_seed = []
    for seed, f in sorted(frames.items()):
        for model in MODELS:
            clean, n_obs = M.clean_detection(f, model)
            rnd = M.marginal(f, model, "random_search")
            beam = M.marginal(f, model, "beam_search")
            rr = M.robust_recall(f, model)
            best = M.strongest(f, model)
            be = best[best.clean_detected]
            per_seed.append(dict(
                estimator="A_sensitivity", seed=seed, model=model,
                architecture=LABEL[model], clean_detected_rate=clean,
                n_positive_observations=n_obs,
                n_eligible_observations=rnd["n_eligible"],
                n_eligible_families=rnd["n_eligible_families"],
                random_ASR=rnd["ASR"], beam_ASR=beam["ASR"],
                strongest_ASR=float(be.attack_success.mean()),
                robust_recall=rr["robust_recall"],
                successful_evasions=int(be.attack_success.sum()),
                unsuccessful_attacks=int((~be.attack_success).sum()),
                invalid_attacks=int((~f[(f.target_model == model) &
                                        f.method.isin(SEARCH)].structural_valid).sum())))
    contrasts = []
    for seed, f in sorted(frames.items()):
        for method in SEARCH:
            c = M.paired_contrast(f, "emulator_logreg", "authguard_seq", method,
                                  f"bridge085_seed{seed}", NBOOT)
            if c:
                c.update(estimator="A_sensitivity", seed=seed, scope="per_seed")
                contrasts.append(c)
    for method in SEARCH:
        per_source = {}
        for seed, f in sorted(frames.items()):
            a = f[(f.target_model == "emulator_logreg") &
                  (f.method == method)].set_index(M.KEY).sort_index()
            b = f[(f.target_model == "authguard_seq") &
                  (f.method == method)].set_index(M.KEY).sort_index()
            shared = a.index.intersection(b.index)
            a, b = a.loc[shared], b.loc[shared]
            elig = a.clean_detected.to_numpy(bool) & b.clean_detected.to_numpy(bool)
            sa, sb = a.attack_success.to_numpy(float), b.attack_success.to_numpy(float)
            fam = a.family_id.to_numpy()
            for i, key in enumerate(a.index):
                if elig[i]:
                    per_source.setdefault(key[2], dict(family=fam[i], d=[]))["d"].append(
                        sa[i] - sb[i])
        sids = sorted(per_source)
        delta = np.asarray([np.mean(per_source[s]["d"]) for s in sids])
        fams = np.asarray([per_source[s]["family"] for s in sids])
        draws, n_fam = M._family_bootstrap(
            fams, delta, np.ones(len(delta), bool),
            f"bridge085:seedavg:emulator_logreg:authguard_seq:{method}", NBOOT)
        ci = [float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))]
        contrasts.append(dict(
            estimator="A_sensitivity", scope="three_seed",
            label="three_seed_family_clustered_seed_averaged",
            contrast="emulator_logreg - authguard_seq", method=method,
            difference=float(delta.mean()), ci_low=ci[0], ci_high=ci[1],
            excludes_zero=bool(ci[0] > 0 or ci[1] < 0),
            n_sources=int(len(delta)), n_families_eligible=int(n_fam),
            estimator_note=("per-source difference averaged over seeds, then "
                            "family-clustered bootstrap")))
    ps = pd.DataFrame([c for c in contrasts if c.get("scope") == "per_seed"])
    for method, g in ps.groupby("method"):
        contrasts.append(dict(
            estimator="A_sensitivity", scope="three_seed",
            label="three_seed_mean_of_seed_level_estimates",
            contrast="emulator_logreg - authguard_seq", method=method,
            difference=float(g.difference.mean()),
            sd_across_seeds=float(g.difference.std(ddof=0)),
            min_seed_effect=float(g.difference.min()),
            max_seed_effect=float(g.difference.max()),
            all_seeds_positive=bool((g.difference > 0).all()),
            all_seed_cis_exclude_zero=bool(g.excludes_zero.all())))
    return per_seed, contrasts


# -------------------------------------------- ESTIMATOR B (main paper, analyze_tiered.py)
KEY = ["seed", "fold", "sid"]


def best_of(frame, target):
    """Transcription of analyze_tiered.py::best_of, scoped to the Tier-B search methods."""
    g = frame[(frame.target_model == target) & (frame.method.isin(SEARCH))]
    if not len(g):
        return None
    idx = g.groupby(KEY).adversarial_score.idxmin()
    best = g.loc[idx].copy()
    best["attack_success"] = best.clean_detected & (best.adversarial_score < best.threshold)
    return best


def asr(g):
    e = g[g.clean_detected]
    return float(e.attack_success.mean()) if len(e) else np.nan


def paired_pooled(frame, left, right, nboot):
    """Transcription of analyze_tiered.py::paired, including its bootstrap seed material."""
    a, b = best_of(frame, left), best_of(frame, right)
    a = a.set_index(KEY).sort_index()
    b = b.set_index(KEY).sort_index()
    shared = a.index.intersection(b.index)
    a, b = a.loc[shared], b.loc[shared]
    elig = a.clean_detected.to_numpy(bool) & b.clean_detected.to_numpy(bool)
    fams = a.family_id.to_numpy()
    uniq = np.asarray(sorted(pd.unique(fams)))
    idx = {f: i for i, f in enumerate(uniq)}
    rf = np.asarray([idx[f] for f in fams])
    sa, sb = a.attack_success.to_numpy(float), b.attack_success.to_numpy(float)
    rng = np.random.default_rng(int.from_bytes(hashlib.blake2b(
        f"phase4:{left}:{right}:B".encode(), digest_size=8).digest(), "little"))
    draws = np.empty(nboot)
    for r in range(nboot):
        c = np.bincount(rng.integers(0, len(uniq), len(uniq)), minlength=len(uniq))
        w = c[rf] * elig
        t = w.sum()
        draws[r] = ((w * (sa - sb)).sum() / t) if t else np.nan
    draws = draws[np.isfinite(draws)]
    ci = [float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))]
    return dict(estimator="B_main_paper_pooled", tier="B", left=left, right=right,
                left_ASR=float(sa[elig].mean()), right_ASR=float(sb[elig].mean()),
                difference=float((sa[elig] - sb[elig]).mean()), ci_low=ci[0],
                ci_high=ci[1], excludes_zero=bool(ci[0] > 0 or ci[1] < 0),
                n_paired_eligible=int(elig.sum()), n_families=int(len(uniq)),
                seed_scope=sorted({int(s) for s, _, _ in shared}))


def estimator_b(frames, nboot):
    pooled = pd.concat(frames.values(), ignore_index=True)
    rows = []
    for model in MODELS:
        best = best_of(pooled, model)
        e = best[best.clean_detected]
        g = pooled[(pooled.target_model == model) & pooled.method.isin(SEARCH)]
        rows.append(dict(
            estimator="B_main_paper_pooled", tier="B", model=model,
            architecture=LABEL[model],
            clean_detection=float(best.clean_detected.mean()),
            ASR_random_search=asr(g[g.method == "random_search"]),
            ASR_beam_search=asr(g[g.method == "beam_search"]),
            ASR_best_of=asr(best),
            n_eligible=int(best.clean_detected.sum()),
            n_eligible_families=int(e.family_id.nunique()),
            seed_scope=sorted(int(s) for s in pooled.seed.unique())))
    contrast = paired_pooled(pooled, "emulator_logreg", "authguard_seq", nboot)
    return rows, contrast


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nboot", type=int, default=NBOOT)
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    frames, used = load()
    seq = verify_actions(frames)
    folds = verify_folds(frames)
    print("[bridge] fold verification:",
          {k: v["uses_frozen_folds"] for k, v in folds.items()})
    print("[bridge] rows matching regenerated theta085 folds (for contrast):",
          {k: v["rows_matching_regenerated_theta085_fold"] for k, v in folds.items()})

    a_rows, a_contrasts = estimator_a(frames)
    pd.DataFrame(a_rows).to_csv(os.path.join(OUT, "bridge_estimatorA_per_seed.csv"),
                                index=False)
    pd.DataFrame(a_contrasts).to_csv(
        os.path.join(OUT, "bridge_estimatorA_contrasts.csv"), index=False)

    b_rows, b_contrast = estimator_b(frames, args.nboot)
    pd.DataFrame(b_rows).to_csv(os.path.join(OUT, "bridge_estimatorB_marginals.csv"),
                                index=False)
    pd.DataFrame([b_contrast]).to_csv(
        os.path.join(OUT, "bridge_estimatorB_paired.csv"), index=False)

    ag = [r for r in b_rows if r["model"] == "authguard_seq"][0]
    lr = [r for r in b_rows if r["model"] == "emulator_logreg"][0]
    comparison = dict(
        authguard_ASR=dict(frozen=FROZEN["authguard_ASR"], bridge=ag["ASR_best_of"],
                           delta=ag["ASR_best_of"] - FROZEN["authguard_ASR"]),
        lr_ASR=dict(frozen=FROZEN["lr_ASR"], bridge=lr["ASR_best_of"],
                    delta=lr["ASR_best_of"] - FROZEN["lr_ASR"]),
        paired=dict(frozen=FROZEN["paired"], bridge=b_contrast["difference"],
                    delta=b_contrast["difference"] - FROZEN["paired"]),
        ci=dict(frozen=FROZEN["ci"], bridge=[b_contrast["ci_low"], b_contrast["ci_high"]]),
        n_paired=dict(frozen=FROZEN["n_paired"], bridge=b_contrast["n_paired_eligible"]),
        n_families=dict(frozen=FROZEN["n_families"], bridge=b_contrast["n_families"]))

    clean = pd.concat([pd.read_csv(os.path.join(OUT, f"bridge_clean_per_fold_s{s}.csv"))
                       for s in SEEDS], ignore_index=True)
    clean.to_csv(os.path.join(OUT, "bridge_clean_per_fold_all.csv"), index=False)
    per_seed_clean = clean.groupby(["seed", "model"])[
        ["AUPRC", "AUROC", "Brier", "recall_at_5pct_nominal_fpr"]].mean().reset_index()
    clean_summary = per_seed_clean.groupby("model").agg(["mean", "std"]).round(6)

    summary = dict(
        experiment="theta=0.85 bridge on frozen benchmark fold_id",
        git_commit=commit(), seeds=SEEDS, folds=FOLDS, models=MODELS,
        fold_source="revision_v2/data/authguardbench_7702_v2.csv.gz::fold_id (unmodified)",
        family_source="frozen benchmark family_id (== theta=0.85 assignment)",
        action_space=["metadata", "neutral25", "flood25", "flood50", "flood100",
                      "flood200"],
        excluded_actions=list(EXCLUDED), query_budget=64, beam_width=4, max_depth=4,
        max_byte_overhead=2.0, bootstrap_replicates=args.nboot,
        action_verification=seq, fold_verification=folds, source_files=used,
        estimator_A=dict(per_seed=a_rows, contrasts=a_contrasts),
        estimator_B=dict(marginals=b_rows, paired=b_contrast),
        comparison_with_frozen_main=comparison,
        clean_metrics_internal=per_seed_clean.to_dict("records"))
    with open(os.path.join(OUT, "bridge_summary.json"), "w") as fh:
        json.dump(summary, fh, indent=2, default=str)

    print("\n=== ESTIMATOR B (main-paper pooled) ===")
    for r in b_rows:
        print(f"  {r['architecture']:16s} ASR_best_of={r['ASR_best_of']:.5f} "
              f"random={r['ASR_random_search']:.5f} beam={r['ASR_beam_search']:.5f} "
              f"n_eligible={r['n_eligible']} fams={r['n_eligible_families']}")
    print(f"  paired LR-AuthGuard = {b_contrast['difference']:+.6f} "
          f"[{b_contrast['ci_low']:+.5f},{b_contrast['ci_high']:+.5f}] "
          f"n_paired={b_contrast['n_paired_eligible']} fams={b_contrast['n_families']}")
    print("\n=== vs FROZEN MAIN ===")
    for k, v in comparison.items():
        print(f"  {k}: {v}")
    print("\n=== ESTIMATOR A (sensitivity convention) ===")
    for c in a_contrasts:
        if c.get("label") == "three_seed_family_clustered_seed_averaged":
            print(f"  {c['method']:14s} {c['difference']:+.4f} "
                  f"[{c['ci_low']:+.4f},{c['ci_high']:+.4f}] n={c['n_sources']} "
                  f"fams={c['n_families_eligible']}")
    print("\n=== clean (internal only) ===")
    print(clean_summary.to_string())
    print(f"\n[bridge] wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
