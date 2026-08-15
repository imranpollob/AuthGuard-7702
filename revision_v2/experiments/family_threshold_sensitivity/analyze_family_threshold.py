#!/usr/bin/env python3
"""Steps 6, 8 and 11: clean performance, Tier-B adaptive robustness, and the paired
contrasts across family thresholds.

Estimators are taken from the existing pipeline rather than re-invented:

  clean AUPRC / paired dAUPRC
      family-clustered bootstrap exactly as run_statistical_analysis_v2.py: families are
      resampled with replacement WITHIN each fold, the same weight draw is applied to both
      compared models (paired), sample-weighted average precision is computed per replicate,
      replicate distributions are averaged across folds within a seed and then across seeds.

  adaptive ASR / robust recall / paired dASR
      rq4_metrics.py, unchanged - the same module that produced the RQ4 replication and the
      RQ4 Tier-B replication, so the numbers are comparable by construction.

Reads the theta runs read-only and writes only into
revision_v2/results/family_threshold_sensitivity/.
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
from sklearn.metrics import average_precision_score, roc_auc_score

HERE = os.path.dirname(os.path.abspath(__file__))
RV2 = os.path.abspath(os.path.join(HERE, "..", ".."))
ROOT = os.path.abspath(os.path.join(RV2, ".."))
OUT = os.path.join(RV2, "results", "family_threshold_sensitivity")
ATTACKS = os.path.join(RV2, "results", "adaptive_attacks_v2")
sys.path.insert(0, os.path.join(RV2, "experiments", "rq4_replication"))
import rq4_metrics as M  # noqa: E402

# The pipeline's own exact sample-weighted average precision, plus its self-test against
# sklearn. Reused rather than reimplemented so the clean bootstrap is the same estimator.
sys.path.insert(0, os.path.join(RV2, "experiments", "statistical_analysis_v2"))
from run_statistical_analysis_v2 import (fast_weighted_ap_batch,  # noqa: E402
                                         verify_fast_ap)

THETAS = [0.80, 0.85, 0.90]
SEEDS = [7702, 7703, 7704]
FOLDS = [0, 1, 2, 3, 4]
MODELS = ["authguard_seq", "emulator_logreg"]
LABEL = {"authguard_seq": "AuthGuard-Seq", "emulator_logreg": "15-feature LR"}
NBOOT = M.NBOOT
BOOTSTRAP_SEED = "family_threshold_sensitivity"
EXCLUDED_ACTIONS = ("address", "selector")
SEARCH = M.SEARCH_METHODS


def tag_of(theta):
    return f"theta{int(round(theta * 100)):03d}"


def commit():
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()


def fold_seed(*parts):
    return int.from_bytes(hashlib.blake2b(":".join(str(p) for p in parts).encode(),
                                          digest_size=8).digest(), "little")


# ------------------------------------------------------------------------------ loading
def load_attacks():
    frames, used = {}, {}
    for theta in THETAS:
        for seed in SEEDS:
            path = os.path.join(ATTACKS,
                                f"attack_per_row_{tag_of(theta)}_s{seed}.csv.gz")
            if not os.path.exists(path):
                raise SystemExit(f"missing attack records: {path}")
            f = pd.read_csv(path)
            seeds_in = sorted(f.seed.unique())
            folds_in = sorted(int(v) for v in f.fold.unique())
            if seeds_in != [seed]:
                raise SystemExit(f"{path} holds seeds {seeds_in}, expected [{seed}]")
            if folds_in != FOLDS:
                raise SystemExit(f"{path} holds folds {folds_in}, expected {FOLDS}")
            frames[(theta, seed)] = f[f.target_model.isin(MODELS)]
            used[f"{tag_of(theta)}_s{seed}"] = os.path.relpath(path, RV2)
    return frames, used


def load_clean():
    metric_frames, pred_frames, used = [], [], {}
    for theta in THETAS:
        for seed in SEEDS:
            run = f"{tag_of(theta)}_s{seed}"
            mpath = os.path.join(OUT, f"clean_per_fold_{run}.csv")
            ppath = os.path.join(OUT, f"clean_predictions_{run}.csv.gz")
            for p in (mpath, ppath):
                if not os.path.exists(p):
                    raise SystemExit(f"missing clean artifact: {p}")
            m = pd.read_csv(mpath)
            p = pd.read_csv(ppath)
            for name, frame in (("metrics", m), ("predictions", p)):
                if sorted(frame.seed.unique()) != [seed]:
                    raise SystemExit(f"{run} {name}: unexpected seeds")
                if sorted(int(v) for v in frame.fold.unique()) != FOLDS:
                    raise SystemExit(f"{run} {name}: unexpected folds")
                if not np.allclose(frame.theta.unique(), [theta]):
                    raise SystemExit(f"{run} {name}: unexpected theta")
            metric_frames.append(m)
            pred_frames.append(p)
            used[run] = os.path.relpath(ppath, RV2)
    return pd.concat(metric_frames, ignore_index=True), \
        pd.concat(pred_frames, ignore_index=True), used


# ------------------------------------------------------- Tier-B verification on records
def seed_replication_check(frames, predictions):
    """Are the three seeds genuine replicates for each model?

    A model whose fit is deterministic given the data will produce identical scores under
    every seed, in which case its across-seed SD is zero by construction and must not be
    read as stability. Checked directly rather than assumed.
    """
    out = {}
    for theta in THETAS:
        for model in MODELS:
            clean = {}
            for seed in SEEDS:
                p = predictions[(predictions.theta == theta) &
                                (predictions.seed == seed) &
                                (predictions.model == model)]
                clean[seed] = p.sort_values(["fold", "sid"]).score.to_numpy()
            base = clean[SEEDS[0]]
            identical_clean = all(
                len(clean[s]) == len(base) and np.allclose(clean[s], base)
                for s in SEEDS[1:])

            atk = {}
            for seed in SEEDS:
                f = frames[(theta, seed)]
                g = f[(f.target_model == model) & f.method.isin(SEARCH)]
                atk[seed] = g.sort_values(["fold", "sid", "method"])[
                    "attack_success"].to_numpy()
            abase = atk[SEEDS[0]]
            identical_attack = all(
                len(atk[s]) == len(abase) and (atk[s] == abase).all() for s in SEEDS[1:])
            out[f"{tag_of(theta)}::{model}"] = dict(
                theta=theta, model=model,
                identical_clean_scores_across_seeds=bool(identical_clean),
                identical_attack_outcomes_across_seeds=bool(identical_attack),
                seeds_are_independent_replicates=bool(not identical_clean),
                note=("deterministic fit: across-seed SD is 0 by construction, not a "
                      "stability estimate" if identical_clean else
                      "stochastic fit: across-seed SD is a genuine dispersion estimate"))
    return out


def verify_actions(frames):
    out = {}
    for (theta, seed), f in sorted(frames.items()):
        searched = f[f.method.isin(SEARCH)]
        used = set()
        for s in searched.sequence.dropna().unique():
            used.update(str(s).split("+"))
        n_noop = int((searched.sequence == "clean_noop").sum())
        used.discard("clean_noop")
        leaked = sorted(used & set(EXCLUDED_ACTIONS))
        if leaked:
            raise SystemExit(f"theta={theta} seed={seed}: Tier-C action {leaked} present "
                             "in a searched sequence")
        out[f"{tag_of(theta)}_s{seed}"] = dict(
            searched_rows=int(len(searched)), distinct_actions_used=sorted(used),
            empty_sequence_rows=n_noop, tier_c_actions_observed=leaked,
            excluded_from_statistics=sorted(set(f.method.unique()) - set(SEARCH)),
            excluded_row_count=int((~f.method.isin(SEARCH)).sum()))
    return out


# --------------------------------------------------------------- clean bootstrap engine
class CleanBootstrap:
    """Family-clustered bootstrap over clean test predictions, paired across models.

    Mirrors run_statistical_analysis_v2.py: weights are drawn per (theta, fold) and shared
    by every model and seed evaluated on that fold, so model differences are paired.
    """

    def __init__(self, predictions, replicates=NBOOT):
        self.pred = predictions
        self.replicates = replicates
        self.counts, self.order = {}, {}
        for theta in THETAS:
            for fold in FOLDS:
                sub = predictions[(predictions.theta == theta) &
                                  (predictions.fold == fold)]
                fams = np.asarray(sorted(sub.family_id.unique()))
                self.order[(theta, fold)] = fams
                rng = np.random.default_rng(fold_seed(BOOTSTRAP_SEED, theta, fold))
                draws = rng.integers(0, len(fams), size=(replicates, len(fams)))
                matrix = np.zeros((replicates, len(fams)), dtype=np.uint16)
                rows = np.repeat(np.arange(replicates), len(fams))
                np.add.at(matrix, (rows, draws.reshape(-1)), 1)
                self.counts[(theta, fold)] = matrix

    def _cell(self, theta, seed, fold, model):
        sub = self.pred[(self.pred.theta == theta) & (self.pred.seed == seed) &
                        (self.pred.fold == fold) & (self.pred.model == model)]
        sub = sub.sort_values("sid").reset_index(drop=True)
        lookup = {f: i for i, f in enumerate(self.order[(theta, fold)])}
        row_family = sub.family_id.map(lookup).to_numpy(dtype=int)
        return sub, row_family

    def distribution(self, theta, seed, fold, model, metric):
        sub, row_family = self._cell(theta, seed, fold, model)
        y = sub.label.to_numpy(dtype=int)
        scores = sub.score.to_numpy(dtype=float)
        counts = self.counts[(theta, fold)]
        if metric == "AUPRC":
            point = float(average_precision_score(y, scores))
            dist = fast_weighted_ap_batch(y, scores, row_family, counts)
        elif metric == "Recall@5%":
            weights = counts[:, row_family].astype(np.float64)
            thr = float(sub.threshold_05.iloc[0])
            decision = (scores >= thr).astype(float)
            point = float(decision[y == 1].mean())
            num = weights @ (decision * (y == 1))
            den = weights @ (y == 1).astype(float)
            dist = np.divide(num, den, out=np.full(len(num), np.nan), where=den > 0)
        else:
            raise ValueError(metric)
        return point, dist

    def metric(self, theta, model, metric):
        points, dists = [], []
        for seed in SEEDS:
            sp, sd = [], []
            for fold in FOLDS:
                p, d = self.distribution(theta, seed, fold, model, metric)
                sp.append(p)
                sd.append(d)
            points.append(float(np.mean(sp)))
            dists.append(np.mean(sd, axis=0))
        return float(np.mean(points)), np.mean(dists, axis=0), points

    def contrast(self, theta, left, right, metric):
        pl, dl, _ = self.metric(theta, left, metric)
        pr, dr, _ = self.metric(theta, right, metric)
        diff = dl - dr
        diff = diff[np.isfinite(diff)]
        ci = [float(np.percentile(diff, 2.5)), float(np.percentile(diff, 97.5))]
        return dict(theta=theta, metric=metric, contrast=f"{left} - {right}",
                    left_point=pl, right_point=pr, difference=float(pl - pr),
                    ci_low=ci[0], ci_high=ci[1],
                    excludes_zero=bool(ci[0] > 0 or ci[1] < 0),
                    bootstrap_replicates=int(len(diff)),
                    estimator=("family-clustered bootstrap within fold, shared weights "
                               "across models, averaged over folds then seeds"))


# --------------------------------------------------------------- adaptive-side analysis
def attack_rows(frames):
    rows = []
    for (theta, seed), f in sorted(frames.items()):
        for model in MODELS:
            g = f[f.target_model == model]
            if not len(g):
                continue
            clean, n_obs = M.clean_detection(f, model)
            rnd = M.marginal(f, model, "random_search")
            beam = M.marginal(f, model, "beam_search")
            rr = M.robust_recall(f, model)
            searches = g[g.method.isin(SEARCH)]
            elig = searches[searches.clean_detected]
            best = M.strongest(f, model)
            # Strongest-attack ASR must use the same denominator as the marginal ASRs
            # (the model's own clean-detected population), otherwise it is not comparable
            # with random/beam ASR. Robust recall below keeps the all-positives denominator.
            best_elig = best[best.clean_detected] if best is not None else None
            rows.append(dict(
                theta=theta, tag=tag_of(theta), seed=seed, model=model,
                architecture=LABEL[model],
                clean_detected_rate=clean, n_positive_observations=n_obs,
                n_eligible_observations=rnd["n_eligible"],
                n_eligible_families=rnd["n_eligible_families"],
                random_successes=rnd["successes"], random_ASR=rnd["ASR"],
                beam_successes=beam["successes"], beam_ASR=beam["ASR"],
                strongest_ASR=(float(best_elig.attack_success.mean())
                               if best_elig is not None and len(best_elig) else np.nan),
                strongest_successes=(int(best_elig.attack_success.sum())
                                     if best_elig is not None else 0),
                n_strongest_eligible=int(len(best_elig)) if best_elig is not None else 0,
                robust_recall=rr["robust_recall"],
                successful_evasions=int(elig.attack_success.sum()),
                unsuccessful_attacks=int((~elig.attack_success).sum()),
                invalid_attacks=int((~searches.structural_valid).sum()),
                total_attack_queries=int(searches.queries.sum())))
    return rows


def seed_averaged(frames, theta, left, right, method, nboot):
    """Per-source differences averaged over seeds, then family-clustered bootstrap.
    Same estimator as the RQ4 replication: repeated seed evaluations of one source are
    never treated as independent observations."""
    per_source = {}
    for seed in SEEDS:
        f = frames[(theta, seed)]
        a = f[(f.target_model == left) & (f.method == method)].set_index(M.KEY).sort_index()
        b = f[(f.target_model == right) & (f.method == method)].set_index(M.KEY).sort_index()
        shared = a.index.intersection(b.index)
        if not len(shared):
            continue
        a, b = a.loc[shared], b.loc[shared]
        elig = a.clean_detected.to_numpy(bool) & b.clean_detected.to_numpy(bool)
        sa = a.attack_success.to_numpy(float)
        sb = b.attack_success.to_numpy(float)
        fam = a.family_id.to_numpy()
        for i, key in enumerate(a.index):
            if elig[i]:
                per_source.setdefault(key[2], dict(family=fam[i], d=[]))["d"].append(
                    sa[i] - sb[i])
    if not per_source:
        return None
    sids = sorted(per_source)
    delta = np.asarray([np.mean(per_source[s]["d"]) for s in sids])
    fams = np.asarray([per_source[s]["family"] for s in sids])
    draws, n_fam = M._family_bootstrap(
        fams, delta, np.ones(len(delta), bool),
        f"famthresh:{theta}:{left}:{right}:{method}", nboot)
    ci = [float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))]
    return dict(theta=theta, scope="three_seed",
                label="three_seed_family_clustered_seed_averaged",
                contrast=f"{left} - {right}", method=method,
                difference=float(delta.mean()), ci_low=ci[0], ci_high=ci[1],
                excludes_zero=bool(ci[0] > 0 or ci[1] < 0),
                n_sources=int(len(delta)), n_families_eligible=int(n_fam),
                bootstrap_replicates=int(len(draws)),
                estimator=("per-source difference averaged over seeds where both models "
                           "detect cleanly, then family-clustered bootstrap"))


# -------------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nboot", type=int, default=NBOOT)
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    verify_fast_ap()          # pipeline's own check: fast weighted AP == sklearn
    print("[fts] fast weighted-AP self-test passed")
    frames, attack_files = load_attacks()
    clean_metrics, predictions, clean_files = load_clean()
    print(f"[fts] loaded {len(frames)} theta x seed attack runs")

    rep_check = seed_replication_check(frames, predictions)
    with open(os.path.join(OUT, "family_threshold_seed_replication.json"), "w") as fh:
        json.dump(rep_check, fh, indent=2)
    for k, v in rep_check.items():
        if not v["seeds_are_independent_replicates"]:
            print(f"[fts] NOTE {k}: identical across seeds -> SD is 0 by construction")

    seq_check = verify_actions(frames)
    with open(os.path.join(OUT, "family_threshold_action_verification.json"), "w") as fh:
        json.dump(seq_check, fh, indent=2)
    print("[fts] Tier-C actions observed in searched sequences:",
          {k: v["tier_c_actions_observed"] for k, v in seq_check.items()})

    # -------------------------------------------------------------- Step 6: clean
    per_seed_clean = (clean_metrics.groupby(["theta", "seed", "model"])
                      [["AUPRC", "AUROC", "Brier", "recall_at_5pct_nominal_fpr",
                        "realized_fpr_at_threshold"]].mean().reset_index())
    clean_rows = []
    for theta in THETAS:
        for model in MODELS:
            g = per_seed_clean[(per_seed_clean.theta == theta) &
                               (per_seed_clean.model == model)]
            row = dict(theta=theta, tag=tag_of(theta), model=model,
                       architecture=LABEL[model], n_seeds=int(g.seed.nunique()),
                       per_seed_AUPRC=[round(v, 6) for v in g.AUPRC])
            for col, name in (("AUPRC", "AUPRC"), ("AUROC", "AUROC"),
                              ("Brier", "Brier"),
                              ("recall_at_5pct_nominal_fpr", "recall_at_5pct_nominal_fpr"),
                              ("realized_fpr_at_threshold", "realized_fpr_at_threshold")):
                row[f"{name}_mean"] = float(g[col].mean())
                row[f"{name}_sd"] = float(g[col].std(ddof=0))
            clean_rows.append(row)
    clean_df = pd.DataFrame(clean_rows)
    clean_df.to_csv(os.path.join(OUT, "family_threshold_clean_results.csv"), index=False)
    clean_metrics.to_csv(os.path.join(OUT, "family_threshold_clean_per_fold.csv"),
                         index=False)

    print("[fts] running clean paired bootstrap ...", flush=True)
    engine = CleanBootstrap(predictions, args.nboot)
    clean_contrasts = []
    for theta in THETAS:
        for metric in ("AUPRC", "Recall@5%"):
            clean_contrasts.append(engine.contrast(
                theta, "authguard_seq", "emulator_logreg", metric))
            print(f"  theta={theta} {metric}: "
                  f"{clean_contrasts[-1]['difference']:+.4f} "
                  f"[{clean_contrasts[-1]['ci_low']:+.4f},"
                  f"{clean_contrasts[-1]['ci_high']:+.4f}]", flush=True)
    pd.DataFrame(clean_contrasts).to_csv(
        os.path.join(OUT, "family_threshold_clean_contrasts.csv"), index=False)

    # ------------------------------------------------------------- Step 8: adaptive
    atk = pd.DataFrame(attack_rows(frames))
    atk.to_csv(os.path.join(OUT, "family_threshold_attack_results.csv"), index=False)

    agg_rows = []
    for theta in THETAS:
        for model in MODELS:
            g = atk[(atk.theta == theta) & (atk.model == model)]
            row = dict(theta=theta, tag=tag_of(theta), model=model,
                       architecture=LABEL[model], n_seeds=int(g.seed.nunique()))
            for col in ("clean_detected_rate", "random_ASR", "beam_ASR",
                        "strongest_ASR", "robust_recall", "n_eligible_observations",
                        "n_eligible_families"):
                row[f"{col}_mean"] = float(g[col].mean())
                row[f"{col}_sd"] = float(g[col].std(ddof=0))
            row["invalid_attacks_total"] = int(g.invalid_attacks.sum())
            row["successful_evasions_total"] = int(g.successful_evasions.sum())
            row["unsuccessful_attacks_total"] = int(g.unsuccessful_attacks.sum())
            agg_rows.append(row)
    agg = pd.DataFrame(agg_rows)
    agg.to_csv(os.path.join(OUT, "family_threshold_attack_aggregate.csv"), index=False)

    # ------------------------------------------------------- paired robustness contrasts
    contrasts = []
    for theta in THETAS:
        for seed in SEEDS:
            for method in SEARCH:
                c = M.paired_contrast(frames[(theta, seed)], "emulator_logreg",
                                      "authguard_seq", method,
                                      f"famthresh_{tag_of(theta)}_seed{seed}", args.nboot)
                if c:
                    c.update(theta=theta, seed=seed, scope="per_seed",
                             estimator="family-clustered bootstrap within seed")
                    contrasts.append(c)
    per_seed_c = pd.DataFrame([c for c in contrasts if c["scope"] == "per_seed"])
    for (theta, method), grp in per_seed_c.groupby(["theta", "method"]):
        contrasts.append(dict(
            theta=theta, scope="three_seed",
            label="three_seed_mean_of_seed_level_estimates",
            contrast="emulator_logreg - authguard_seq", method=method,
            difference=float(grp.difference.mean()),
            sd_across_seeds=float(grp.difference.std(ddof=0)),
            n_seeds=int(grp.seed.nunique()),
            min_seed_effect=float(grp.difference.min()),
            max_seed_effect=float(grp.difference.max()),
            all_seeds_positive=bool((grp.difference > 0).all()),
            all_seed_cis_exclude_zero=bool(grp.excludes_zero.all()),
            estimator="mean and SD across per-seed family-clustered point estimates"))
    for theta in THETAS:
        for method in SEARCH:
            c = seed_averaged(frames, theta, "emulator_logreg", "authguard_seq",
                              method, args.nboot)
            if c:
                contrasts.append(c)
    pd.DataFrame(contrasts).to_csv(
        os.path.join(OUT, "family_threshold_paired_contrasts.csv"), index=False)

    # ------------------------------------------------- Step 11: compact candidate table
    sa = {(c["theta"], c["method"]): c for c in contrasts
          if c.get("label") == "three_seed_family_clustered_seed_averaged"}
    fam_stats = pd.read_csv(os.path.join(OUT, "family_threshold_family_stats.csv"))
    sim_stats = pd.read_csv(os.path.join(OUT, "family_threshold_similarity_stats.csv"))
    compact, internal = [], []
    for theta in THETAS:
        n_fam = int(fam_stats.loc[fam_stats.theta == theta, "n_families"].iloc[0])
        def cell(model, col):
            return float(agg[(agg.theta == theta) &
                             (agg.model == model)][col].iloc[0])
        c = sa[(theta, "beam_search")]
        compact.append(dict(
            family_threshold=theta, n_families=n_fam,
            authguard_AUPRC=float(clean_df[(clean_df.theta == theta) &
                                           (clean_df.model == "authguard_seq")
                                           ]["AUPRC_mean"].iloc[0]),
            lr_AUPRC=float(clean_df[(clean_df.theta == theta) &
                                    (clean_df.model == "emulator_logreg")
                                    ]["AUPRC_mean"].iloc[0]),
            authguard_tierb_ASR=cell("authguard_seq", "strongest_ASR_mean"),
            lr_tierb_ASR=cell("emulator_logreg", "strongest_ASR_mean"),
            paired_delta_ASR_beam=c["difference"],
            ci_low=c["ci_low"], ci_high=c["ci_high"],
            excludes_zero=c["excludes_zero"]))
        s = sim_stats[sim_stats.theta == theta].iloc[0]
        internal.append(dict(
            family_threshold=theta,
            paired_observations=c["n_sources"],
            paired_families=c["n_families_eligible"],
            median_nearest_train_similarity=float(s["median"]),
            p90=float(s.p90), p95=float(s.p95), maximum=float(s.maximum),
            n_test_above_0_90=int(s.n_above_0_90),
            pct_test_above_0_90=float(s.pct_above_0_90),
            n_test_above_own_threshold=int(s.n_above_theta),
            pct_test_above_own_threshold=float(s.pct_above_theta)))
    compact_df = pd.DataFrame(compact)
    compact_df.to_csv(os.path.join(OUT, "family_threshold_compact_table.csv"), index=False)
    pd.DataFrame(internal).to_csv(
        os.path.join(OUT, "family_threshold_internal_table.csv"), index=False)

    summary = dict(
        experiment="family-threshold sensitivity (theta = 0.80 / 0.85 / 0.90)",
        git_commit=commit(), thetas=THETAS, seeds=SEEDS, folds=FOLDS, models=MODELS,
        reference_theta=0.85,
        action_space=["metadata", "neutral25", "flood25", "flood50", "flood100",
                      "flood200"],
        excluded_actions=list(EXCLUDED_ACTIONS),
        query_budget=64, beam_width=4, max_depth=4, max_byte_overhead=2.0,
        operating_point="nominal 5% FPR from validation negatives",
        bootstrap_replicates=args.nboot,
        clean_estimator=("family-clustered bootstrap within fold, shared weights across "
                         "models, averaged over folds then seeds "
                         "(run_statistical_analysis_v2.py convention)"),
        adaptive_estimator="rq4_metrics.py, unchanged",
        attack_files=attack_files, clean_prediction_files=clean_files,
        action_verification=seq_check, seed_replication_check=rep_check,
        clean_results=clean_rows, clean_contrasts=clean_contrasts,
        attack_per_seed=atk.to_dict("records"), attack_aggregate=agg_rows,
        paired_contrasts=contrasts, compact_table=compact,
        internal_table=internal)
    with open(os.path.join(OUT, "family_threshold_summary.json"), "w") as fh:
        json.dump(summary, fh, indent=2, default=str)

    print("\n[fts] clean (mean +/- SD over seeds of fold-averaged values)")
    print(clean_df[["theta", "architecture", "AUPRC_mean", "AUPRC_sd", "AUROC_mean",
                    "Brier_mean", "recall_at_5pct_nominal_fpr_mean"]].round(4)
          .to_string(index=False))
    print("\n[fts] Tier-B adaptive")
    print(agg[["theta", "architecture", "clean_detected_rate_mean", "random_ASR_mean",
               "beam_ASR_mean", "strongest_ASR_mean", "robust_recall_mean"]].round(4)
          .to_string(index=False))
    print("\n[fts] paired dASR (LR - AuthGuard), seed-averaged family-clustered")
    for theta in THETAS:
        for method in SEARCH:
            c = sa[(theta, method)]
            print(f"  theta={theta} {method:<14}{c['difference']:+.4f} "
                  f"[{c['ci_low']:+.4f},{c['ci_high']:+.4f}] "
                  f"excl0={c['excludes_zero']} n={c['n_sources']} "
                  f"fams={c['n_families_eligible']}")
    print(f"\n[fts] wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
