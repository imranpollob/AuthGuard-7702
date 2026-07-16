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


def zscore(train_vals, x):
    mu, sd = np.mean(train_vals), np.std(train_vals) + 1e-9
    return (x - mu) / sd


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
    for f in range(5):
        tr, te = np.flatnonzero(folds != f), np.flatnonzero(folds == f)
        groups_tr = sub["family_id"].to_numpy()[tr]
        thr, _, _ = oof_threshold(method, X[tr], y[tr], groups_tr, SEED)
        # 5-seed ensemble for margin + disagreement
        clfs = [XGBClassifier(random_state=s, **XGB_HP).fit(X[tr], y[tr]) for s in MODEL_SEEDS]
        def ens_scores(Xte):
            S = np.stack([c.predict_proba(Xte)[:, 1] for c in clfs])
            return S.mean(0), S.std(0)
        # kNN outlier distance in standardized dense space (train reference)
        nn = NearestNeighbors(n_neighbors=6).fit(Xds[tr])
        def knn_dist(Xd_te):
            d, _ = nn.kneighbors(Xd_te); return d[:, 1:].mean(1)

        s_tr_mean, s_tr_std = ens_scores(X[tr])
        margin_tr = np.abs(s_tr_mean - thr)
        knn_tr = knn_dist(Xds[tr])
        trail_tr = sub["trailing_ratio"].to_numpy()[tr]

        def risk(mean, std, knn, trail, bchash):
            s2 = np.array([1.0 if h in conflict_hashes else 0.0 for h in bchash])
            return (zscore(margin_tr, -np.abs(mean - thr)) + zscore(s_tr_std, std)
                    + zscore(knn_tr, knn) + zscore(trail_tr, trail) + 3.0 * s2)

        # escalation cutoff from TRAIN to hit target rate
        risk_tr = risk(s_tr_mean, s_tr_std, knn_tr, trail_tr, sub["bchash"].to_numpy()[tr])
        cutoff = np.quantile(risk_tr, 1 - TARGET_ESC)

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
                trail_te = np.array([terminal_stats(h)["post_terminal_ratio"] for h in hexes])
                bch_te = np.array([hashlib.sha256(normalize_bytecode(h).encode()).hexdigest()
                                   for h in hexes])
            mean, std = ens_scores(Xte)
            knn = knn_dist(Xd_te)
            rk = risk(mean, std, knn, trail_te, bch_te)
            escalate = rk >= cutoff
            pred = (mean >= thr).astype(int)
            for i in range(len(yte)):
                rows.append(dict(fold=f, condition=cond, y=int(yte[i]),
                                 score=float(mean[i]), pred=int(pred[i]),
                                 escalate=bool(escalate[i]),
                                 margin=float(abs(mean[i] - thr)), disagreement=float(std[i]),
                                 low_conf_rank=float(-abs(mean[i] - thr))))
        print(f"[gateB fold {f}] cutoff set (target esc {TARGET_ESC})", flush=True)

    R = pd.DataFrame(rows)
    R.to_csv(os.path.join(OUT, "gateB_per_row.csv.gz"), index=False)

    def concentration(d):
        esc, non = d[d.escalate], d[~d.escalate]
        err_esc = ((esc.pred != esc.y).mean()) if len(esc) else float("nan")
        err_non = ((non.pred != non.y).mean()) if len(non) else float("nan")
        return err_esc, err_non, len(esc) / len(d)

    summary = {}
    for cond in ["cleanM0", "F200", "M3F200"]:
        d = R[R.condition == cond]
        err_esc, err_non, esc_rate = concentration(d)
        # low-confidence abstention baseline at matched rate
        d = d.copy()
        k = int(round(esc_rate * len(d)))
        thresh_lc = np.sort(d["low_conf_rank"].to_numpy())[::-1][k - 1] if k > 0 else np.inf
        d["esc_lc"] = d["low_conf_rank"] >= thresh_lc
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
            full_FPR=float(((d.y == 0) & (d.pred == 1)).sum() / max((d.y == 0).sum(), 1)))

    with open(os.path.join(OUT, "gateB_results.json"), "w") as f:
        json.dump(dict(target_escalation=TARGET_ESC, signals=["conflict_history", "trailing_ratio",
                       "margin", "cross_seed_disagreement", "knn_outlier"], summary=summary), f, indent=2)
    write_manifest(OUT, dict(protocol="gateB_success_criteria", seeds=MODEL_SEEDS),
                   [os.path.join(OUT, "gateB_results.json"),
                    os.path.join(OUT, "gateB_per_row.csv.gz")], started,
                   inputs=[os.path.join(DH, "task_aligned_dataset_v1.csv")])
    verify_frozen_or_die()
    print(json.dumps(summary, indent=1))
    print(f"[gateB] done in {time.time()-started:.0f}s")


if __name__ == "__main__":
    main()
