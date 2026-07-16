#!/usr/bin/env python3
"""Phase 4 Gate B — selective escalation (gateB_success_criteria.md).

Escalation signals (frozen on train/val only):
  S1 known-conflict exact-bytecode history; S2 trailing-byte ratio; S4 low prediction margin;
  S5 cross-seed disagreement (5-seed variance); S6 feature-space kNN outlier distance.
A per-fold escalation cutoff is chosen on the outer-training population to hit a target
escalation rate (<=15%); cases above the combined risk are escalated. Non-escalated cases are
scored by AuthGuard-v2. Reported: coverage, escalation rate, non-escalated recall/FPR, error
concentration vs a low-confidence-abstention baseline, under clean + G-VOL + compound.

EIP-7702-specific signals: S1 (conflict history) and S2 (trailing/terminal structure).
"""
import hashlib
import json
import os
import sys
import time

import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))
sys.path.insert(0, os.path.join(HERE, "..", "donor_pools"))
sys.path.insert(0, os.path.join(HERE, "..", "gateA"))
from harness import (load_corpus, task_arrays, feature_views, oof_threshold,  # noqa: E402
                     make_xgb, metrics_full, write_manifest, verify_frozen_or_die,
                     featurize, SENS, normalize_bytecode, XGB_HP, RV2, DH, ROOT, SEED)
from pools import DonorPools, make_variant_isolated, mut  # noqa: E402
from run_gateA import terminal_stats  # noqa: E402
from xgboost import XGBClassifier

OUT = os.path.join(RV2, "results", "gateB")
MODEL_SEEDS = [SEED, 7703, 7704, 7705, 7706]
TARGET_ESC = 0.15
NBOOT = 10_000


def zscore(train_vals, x):
    mu, sd = np.mean(train_vals), np.std(train_vals) + 1e-9
    return (x - mu) / sd


def ratio_from_weights(d, flag_col, weights=None):
    """Error-density ratio in escalated vs non-escalated rows."""
    w = np.ones(len(d), dtype=float) if weights is None else np.asarray(weights, dtype=float)
    esc = d[flag_col].to_numpy(dtype=bool)
    err = (d["pred"].to_numpy() != d["y"].to_numpy()).astype(float)
    w_esc, w_non = w * esc, w * (~esc)
    den_esc, den_non = w_esc.sum(), w_non.sum()
    if den_esc == 0 or den_non == 0:
        return float("nan")
    err_esc = float((w_esc * err).sum() / den_esc)
    err_non = float((w_non * err).sum() / den_non)
    return float(err_esc / err_non) if err_non > 0 else float("inf")


def paired_family_bootstrap(d, name):
    """Frozen uncertainty protocol for candidate vs matched low-confidence comparator."""
    families = np.array(sorted(pd.unique(d["family_id"])))
    fam_index = {fam: i for i, fam in enumerate(families)}
    obs_family = np.array([fam_index[f] for f in d["family_id"]])
    rng_seed = int.from_bytes(hashlib.blake2b(f"{SEED}:{name}".encode(), digest_size=8).digest(),
                              "little")
    rng = np.random.default_rng(rng_seed)
    candidate, baseline = np.empty(NBOOT), np.empty(NBOOT)
    for b in range(NBOOT):
        counts = np.bincount(rng.integers(0, len(families), len(families)),
                             minlength=len(families))
        weights = counts[obs_family]
        candidate[b] = ratio_from_weights(d, "escalate", weights)
        baseline[b] = ratio_from_weights(d, "esc_lc", weights)
    delta = candidate - baseline

    def summarize(values):
        finite = values[np.isfinite(values)]
        return dict(CI95=([float(np.percentile(finite, 2.5)),
                           float(np.percentile(finite, 97.5))] if len(finite) else [None, None]),
                    boot_mean=(float(finite.mean()) if len(finite) else None),
                    boot_std=(float(finite.std()) if len(finite) else None),
                    finite_replicates=int(len(finite)))
    return dict(replicates=NBOOT, candidate_ratio=summarize(candidate),
                low_conf_ratio=summarize(baseline),
                candidate_minus_low_conf=summarize(delta))


def main():
    started = time.time()
    verify_frozen_or_die()
    os.makedirs(OUT, exist_ok=True)
    df, Xd, Xn, meta = load_corpus()
    views = feature_views(meta)
    sub, y, folds, Xds, Xns = task_arrays(df, Xd, Xn, "primary")
    sub = sub.copy(); sub["y"] = y
    X = np.hstack([Xds, Xns]).astype(np.float32)
    full_cols = list(range(views["n_dense"] + 512))
    method = make_xgb(full_cols)

    conflict = pd.read_csv(os.path.join(DH, "conflicting_bytecodes.csv"))
    conflict_hashes = set(conflict["normalized_bytecode_sha256"])
    sub["bchash"] = sub["bc"].map(lambda b: hashlib.sha256(b.encode()).hexdigest())
    sub["trailing_ratio"] = [terminal_stats(bc)["post_terminal_ratio"] for bc in sub["bytecode"]]

    pools = DonorPools(df.assign(y=(df["class"] == "malicious").astype(int)),
                       "benign_general", "outer_fold_primary", "GATEB")

    rows = []
    train_rates = []
    for f in range(5):
        pools.assert_disjoint(f)
        tr, te = np.flatnonzero(folds != f), np.flatnonzero(folds == f)
        groups_tr = sub["family_id"].to_numpy()[tr]
        thr, _, _ = oof_threshold(method, X[tr], y[tr], groups_tr, SEED)
        # 5-seed ensemble for margin + disagreement
        clfs = [XGBClassifier(random_state=s, **XGB_HP).fit(X[tr], y[tr]) for s in MODEL_SEEDS]
        def ens_scores(Xte):
            S = np.stack([c.predict_proba(Xte)[:, 1] for c in clfs])
            return S.mean(0), S.std(0)
        # kNN outlier distance in standardized dense space (train reference), as frozen.
        scaler = StandardScaler().fit(Xds[tr])
        Xd_tr_scaled = scaler.transform(Xds[tr])
        nn = NearestNeighbors(n_neighbors=6).fit(Xd_tr_scaled)
        def knn_dist(Xd_te, training_query=False):
            # Training queries contain themselves (drop distance 0); held-out queries do not.
            n_neighbors = 6 if training_query else 5
            d, _ = nn.kneighbors(scaler.transform(Xd_te), n_neighbors=n_neighbors)
            return d[:, 1:].mean(1) if training_query else d.mean(1)

        s_tr_mean, s_tr_std = ens_scores(X[tr])
        margin_tr = np.abs(s_tr_mean - thr)
        knn_tr = knn_dist(Xds[tr], training_query=True)
        trail_tr = sub["trailing_ratio"].to_numpy()[tr]

        def risk_components(mean, std, knn, trail, bchash):
            conflict_component = np.array([3.0 if h in conflict_hashes else 0.0
                                           for h in bchash])
            return dict(low_margin=zscore(margin_tr, -np.abs(mean - thr)),
                        disagreement=zscore(s_tr_std, std),
                        knn_outlier=zscore(knn_tr, knn),
                        trailing_ratio=zscore(trail_tr, trail),
                        conflict_history=conflict_component)

        def combine(components, include_eip=True):
            generic = (components["low_margin"] + components["disagreement"] +
                       components["knn_outlier"])
            return (generic + components["trailing_ratio"] + components["conflict_history"]
                    if include_eip else generic)

        # escalation cutoff from TRAIN to hit target rate
        comp_tr = risk_components(s_tr_mean, s_tr_std, knn_tr, trail_tr,
                                  sub["bchash"].to_numpy()[tr])
        risk_tr = combine(comp_tr)
        generic_tr = combine(comp_tr, include_eip=False)
        cutoff = np.quantile(risk_tr, 1 - TARGET_ESC)
        cutoff_generic = np.quantile(generic_tr, 1 - TARGET_ESC)
        train_rates.append(dict(fold=f, candidate=float((risk_tr >= cutoff).mean()),
                                generic_only=float((generic_tr >= cutoff_generic).mean())))

        for cond in ["cleanM0", "F200", "M3F200"]:
            if cond == "cleanM0":
                Xte, yte = X[te], y[te]
                trail_te = sub["trailing_ratio"].to_numpy()[te]
                bch_te = sub["bchash"].to_numpy()[te]
                Xd_te = Xds[te]
            else:
                held = sub.iloc[te]
                hexes = [make_variant_isolated(pools, r.to_dict(), f, "test", cond, "test")
                         for _, r in held.iterrows()]
                d, n, _ = featurize(hexes, sens=SENS)
                Xte = np.hstack([d, n]).astype(np.float32); Xd_te = d
                yte = held["y"].to_numpy()
                sid_te = held["sid"].to_numpy()
                fam_te = held["family_id"].to_numpy()
                trail_te = np.array([terminal_stats(h)["post_terminal_ratio"] for h in hexes])
                bch_te = np.array([hashlib.sha256(normalize_bytecode(h).encode()).hexdigest()
                                   for h in hexes])
            if cond == "cleanM0":
                sid_te = sub["sid"].to_numpy()[te]
                fam_te = sub["family_id"].to_numpy()[te]
            mean, std = ens_scores(Xte)
            knn = knn_dist(Xd_te)
            components = risk_components(mean, std, knn, trail_te, bch_te)
            rk = combine(components)
            rk_generic = combine(components, include_eip=False)
            escalate = rk >= cutoff
            escalate_generic = rk_generic >= cutoff_generic
            pred = (mean >= thr).astype(int)
            for i in range(len(yte)):
                rows.append(dict(fold=f, condition=cond, sid=sid_te[i],
                                 family_id=fam_te[i], y=int(yte[i]),
                                 score=float(mean[i]), pred=int(pred[i]),
                                 escalate=bool(escalate[i]),
                                 escalate_generic_only=bool(escalate_generic[i]),
                                 margin=float(abs(mean[i] - thr)), disagreement=float(std[i]),
                                 low_conf_rank=float(-abs(mean[i] - thr)),
                                 risk=float(rk[i]), generic_risk=float(rk_generic[i]),
                                 trailing_component=float(components["trailing_ratio"][i]),
                                 conflict_component=float(components["conflict_history"][i]),
                                 knn_component=float(components["knn_outlier"][i])))
        print(f"[gateB fold {f}] cutoff set (target esc {TARGET_ESC})", flush=True)

    R = pd.DataFrame(rows)

    def concentration(d):
        esc, non = d[d.escalate], d[~d.escalate]
        err_esc = ((esc.pred != esc.y).mean()) if len(esc) else float("nan")
        err_non = ((non.pred != non.y).mean()) if len(non) else float("nan")
        return err_esc, err_non, len(esc) / len(d)

    summary = {}
    uncertainty = {}
    for cond in ["cleanM0", "F200", "M3F200"]:
        d = R[R.condition == cond]
        err_esc, err_non, esc_rate = concentration(d)
        # low-confidence abstention baseline at matched rate
        d = d.copy()
        k = int(round(esc_rate * len(d)))
        # Exact-k stable selection avoids tie-driven comparator-rate inflation.
        esc_lc = np.zeros(len(d), dtype=bool)
        if k > 0:
            order = np.argsort(-d["low_conf_rank"].to_numpy(), kind="stable")
            esc_lc[order[:k]] = True
        d["esc_lc"] = esc_lc
        R.loc[d.index, "esc_lc"] = d["esc_lc"]
        esc_lc, non_lc = d[d.esc_lc], d[~d.esc_lc]
        err_esc_lc = (esc_lc.pred != esc_lc.y).mean() if len(esc_lc) else float("nan")
        err_non_lc = (non_lc.pred != non_lc.y).mean() if len(non_lc) else float("nan")
        non = d[~d.escalate]
        fn_captured = ((d[d.escalate].y == 1) & (d[d.escalate].pred == 0)).sum()
        fn_total = ((d.y == 1) & (d.pred == 0)).sum()
        summary[cond] = dict(
            escalation_rate=float(esc_rate),
            auto_coverage=float(1 - esc_rate),
            err_density_escalated=float(err_esc), err_density_non=float(err_non),
            concentration_ratio=float(err_esc / err_non) if err_non else float("inf"),
            nonescalated_recall=float(((non.y == 1) & (non.pred == 1)).sum() /
                                      max((non.y == 1).sum(), 1)),
            nonescalated_FPR=float(((non.y == 0) & (non.pred == 1)).sum() /
                                   max((non.y == 0).sum(), 1)),
            low_conf_concentration_ratio=float(err_esc_lc / err_non_lc) if err_non_lc else float("inf"),
            fn_captured_fraction=float(fn_captured / max(fn_total, 1)),
            full_recall=float(((d.y == 1) & (d.pred == 1)).sum() / max((d.y == 1).sum(), 1)),
            full_FPR=float(((d.y == 0) & (d.pred == 1)).sum() / max((d.y == 0).sum(), 1)),
            eip_signal_decision_changes=int((d.escalate != d.escalate_generic_only).sum()))
        uncertainty[cond] = paired_family_bootstrap(d, f"gateB:{cond}")

    R["esc_lc"] = R["esc_lc"].astype(bool)
    R.to_csv(os.path.join(OUT, "gateB_per_row.csv.gz"), index=False)

    clean_ci = uncertainty["cleanM0"]["candidate_ratio"]["CI95"]
    delta_ci = uncertainty["cleanM0"]["candidate_minus_low_conf"]["CI95"]
    c1 = (summary["cleanM0"]["escalation_rate"] <= TARGET_ESC and
          summary["cleanM0"]["concentration_ratio"] >= 2.0 and
          clean_ci[0] is not None and clean_ci[0] > 1.0)
    c2 = (summary["cleanM0"]["nonescalated_recall"] >= summary["cleanM0"]["full_recall"] and
          summary["cleanM0"]["nonescalated_FPR"] <= summary["cleanM0"]["full_FPR"])
    robust_pass = [c for c in ["F200", "M3F200"]
                   if summary[c]["escalation_rate"] <= TARGET_ESC and
                   summary[c]["fn_captured_fraction"] >= 0.33]
    c3 = bool(robust_pass)
    c4 = (delta_ci[0] is not None and delta_ci[0] > 0)
    eip_changes = sum(summary[c]["eip_signal_decision_changes"] for c in summary)
    c5 = eip_changes > 0
    verdict = dict(
        verdict="PASS" if all([c1, c2, c3, c4, c5]) else "FAIL",
        criteria={
            "1_error_concentration": dict(passed=bool(c1), point=summary["cleanM0"]["concentration_ratio"],
                                          CI95=clean_ci),
            "2_automatic_coverage_quality": dict(passed=bool(c2)),
            "3_robust_value": dict(passed=bool(c3), passing_conditions=robust_pass),
            "4_beats_low_confidence": dict(passed=bool(c4), delta_ratio_CI95=delta_ci),
            "5_eip_specific_contribution": dict(passed=bool(c5),
                                                 escalation_decision_changes=int(eip_changes))},
        note="All five frozen criteria must pass; no criterion was relaxed after results.")

    with open(os.path.join(OUT, "gateB_results.json"), "w") as f:
        json.dump(dict(target_escalation=TARGET_ESC, signals=["conflict_history", "trailing_ratio",
                       "margin", "cross_seed_disagreement", "knn_outlier"],
                       knn_preprocessing="StandardScaler fit on outer-training dense features",
                       train_escalation_rates=train_rates, summary=summary,
                       family_clustered_uncertainty=uncertainty), f, indent=2)
    with open(os.path.join(OUT, "gateB_verdict.json"), "w") as f:
        json.dump(verdict, f, indent=2)
    write_manifest(OUT, dict(protocol="gateB_success_criteria", seeds=MODEL_SEEDS),
                   [os.path.join(OUT, "gateB_results.json"),
                    os.path.join(OUT, "gateB_per_row.csv.gz"),
                    os.path.join(OUT, "gateB_verdict.json")], started,
                   inputs=[os.path.join(DH, "task_aligned_dataset_v1.csv")])
    verify_frozen_or_die()
    print(json.dumps(summary, indent=1))
    print(json.dumps(verdict, indent=1))
    print(f"[gateB] done in {time.time()-started:.0f}s")


if __name__ == "__main__":
    main()
