#!/usr/bin/env python3
"""Phase 4 Gate A — conservative terminal-aware dual-view representation.

Trivial comparator: XGBoost on 773 features computed on bytes before the first STOP.
Dual-view: full-view 773 + restricted-view 773 (features on the conservative terminal region)
+ trailing-byte volume + post-terminal ratio + terminal-instruction stats + full-vs-restricted
dense-feature differences.

Restricted region (syntactic, conservative): prefix up to and including the first linear-sweep
unconditional terminator (STOP/RETURN/REVERT/INVALID) not inside PUSH data, over the
pre-metadata region. No reachability/CFG/dynamic-unreachability claim.

Evaluated under the v2 threshold protocol on clean G-DET (family + random), G-MUT tiers,
pure-M0 F200, compound M3F200, and benign_general FPR, with M0-trained models (clean/robustness)
and augmented models (flooding). Success criteria are frozen in
revision_v2/protocols/gateA_success_criteria.md and evaluated by gateA_verdict.py.
"""
import hashlib
import json
import os
import sys
import time

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))
sys.path.insert(0, os.path.join(HERE, "..", "donor_pools"))
from harness import (load_corpus, task_arrays, feature_views, best_f1_threshold,  # noqa: E402
                     inner_splits, metrics_full, oof_threshold, make_xgb, write_manifest,
                     verify_frozen_or_die, RV2, DH, SEED, featurize, SENS, XGB_HP,
                     normalize_bytecode, disasm)
from pools import DonorPools, mut, make_variant_isolated  # noqa: E402
from xgboost import XGBClassifier

OUT = os.path.join(RV2, "results", "gateA")
TERMINATORS = {"STOP", "RETURN", "REVERT", "INVALID"}
MODEL_SEEDS = [SEED, 7703, 7704]


def first_terminator_region(bc, ops_terminators):
    """Return hex prefix up to and including the first terminator opcode (linear sweep,
    pre-metadata). If none, return the whole pre-metadata region."""
    b = mut.to_bytes(bc)
    ms = mut.find_metadata_split(b)
    i, n = 0, ms
    _PUSH1, _PUSH32 = 0x60, 0x7f
    while i < n:
        op = b[i]
        if _PUSH1 <= op <= _PUSH32:
            i += 1 + (op - _PUSH1 + 1)
            continue
        name = None
        if op == 0x00:
            name = "STOP"
        elif op == 0xf3:
            name = "RETURN"
        elif op == 0xfd:
            name = "REVERT"
        elif op == 0xfe:
            name = "INVALID"
        if name in ops_terminators:
            return b[:i + 1].hex()
        i += 1
    return b[:ms].hex()


def first_stop_region(bc):
    return first_terminator_region(bc, {"STOP"})


def terminal_stats(bc):
    b = mut.to_bytes(bc)
    ms = mut.find_metadata_split(b)
    total = len(b)
    region = bytes.fromhex(first_terminator_region(bc, TERMINATORS))
    post = ms - len(region)
    return dict(trailing_byte_volume=float(post),
                post_terminal_ratio=float(post / max(ms, 1)),
                restricted_bytes=float(len(region)),
                total_exec_bytes=float(ms),
                total_bytes=float(total))


def dual_features(hexes):
    """Return (full773, dual_matrix). dual = [full773 | restr773 | full-restr dense diff | 5 stats]."""
    full_d, full_n, _ = featurize(hexes, sens=SENS)
    restr_hexes = [first_terminator_region(h, TERMINATORS) for h in hexes]
    r_d, r_n, _ = featurize(restr_hexes, sens=SENS)
    n_dense = full_d.shape[1]
    diff_d = full_d - r_d
    stats = np.array([[terminal_stats(h)[k] for k in
                       ("trailing_byte_volume", "post_terminal_ratio", "restricted_bytes",
                        "total_exec_bytes", "total_bytes")] for h in hexes], dtype=np.float32)
    full = np.hstack([full_d, full_n]).astype(np.float32)
    restr = np.hstack([r_d, r_n]).astype(np.float32)
    dual = np.hstack([full, restr, diff_d, stats]).astype(np.float32)
    return full, dual


def firststop_features(hexes):
    fs = [first_stop_region(h) for h in hexes]
    d, n, _ = featurize(fs, sens=SENS)
    return np.hstack([d, n]).astype(np.float32)


def fit_xgb(X, y, seed, w=None):
    clf = XGBClassifier(random_state=seed, **XGB_HP)
    clf.fit(X, y, sample_weight=w)
    return clf


def main():
    started = time.time()
    verify_frozen_or_die()
    os.makedirs(OUT, exist_ok=True)
    df, Xd, Xn, meta = load_corpus()
    views = feature_views(meta)
    sub, y, folds, Xds, Xns = task_arrays(df, Xd, Xn, "primary")
    sub = sub.copy(); sub["y"] = y
    hexes_m0 = sub["bytecode"].tolist()
    pools = DonorPools(df.assign(y=(df["class"] == "malicious").astype(int)),
                       "benign_general", "outer_fold_primary", "GATEA")

    # Precompute clean M0 views for the whole primary population
    full_m0, dual_m0 = dual_features(hexes_m0)
    fs_m0 = firststop_features(hexes_m0)
    reps = {"full": full_m0, "dual": dual_m0, "first_stop": fs_m0}

    bg = df[df["class"] == "benign_general"].reset_index(drop=True)
    bg_full, bg_dual = dual_features(bg["bytecode"].tolist())
    bg_fs = firststop_features(bg["bytecode"].tolist())
    bg_reps = {"full": bg_full, "dual": bg_dual, "first_stop": bg_fs}

    results = {rep: {} for rep in reps}
    per_row = []
    # ---- clean G-DET (family) + benign_general FPR, M0-trained ----
    for rep, X in reps.items():
        fam_ap, fold_m, bg_fpr = [], [], []
        thr_by_fold = {}
        for f in range(5):
            tr, te = np.flatnonzero(folds != f), np.flatnonzero(folds == f)
            method = dict(fit=lambda Xx, yy, s: fit_xgb(Xx, yy, s),
                          score=lambda m, Xx: m.predict_proba(Xx)[:, 1])
            thr, _, _ = oof_threshold(method, X[tr], y[tr], sub["family_id"].to_numpy()[tr], SEED)
            clf = fit_xgb(X[tr], y[tr], SEED)
            s = clf.predict_proba(X[te])[:, 1]
            fam_ap.append(float(average_precision_score(y[te], s)))
            fold_m.append(metrics_full(y[te], s, thr))
            thr_by_fold[f] = (thr, clf)
            sbg = clf.predict_proba(bg_reps[rep])[:, 1]
            bg_fpr.append(float((sbg >= thr).mean()))
            for j, k in enumerate(te):
                per_row.append(dict(rep=rep, condition="cleanM0", fold=f, sid=sub["sid"].iloc[k],
                                    family_id=sub["family_id"].iloc[k], y=int(y[k]),
                                    score=float(s[j]), threshold=thr))
        dm = pd.DataFrame(fold_m)
        results[rep]["cleanM0"] = dict(family_AUPRC_mean=float(np.mean(fam_ap)),
                                       family_AUPRC_std=float(np.std(fam_ap)),
                                       FPR_mean=float(dm["FPR"].mean()),
                                       recall_mean=float(dm["Recall"].mean()),
                                       benign_general_FPR_mean=float(np.mean(bg_fpr)),
                                       folds_AUPRC=fam_ap)
        results[rep]["_thr"] = {f: thr_by_fold[f][0] for f in thr_by_fold}

    # ---- robustness: flooding recall for M0-trained models (donor-isolated) ----
    def build_variant_views(rows_df, fold, cond):
        hexes = [make_variant_isolated(pools, r.to_dict() if hasattr(r, "to_dict") else r,
                                       fold, "test", cond, "test")
                 for _, r in rows_df.iterrows()]
        full, dual = dual_features(hexes)
        fs = firststop_features(hexes)
        return {"full": full, "dual": dual, "first_stop": fs}

    robustness = {rep: {c: [] for c in ["M3", "F200", "M3F200"]} for rep in reps}
    for f in range(5):
        pools.assert_disjoint(f)
        tr, te = np.flatnonzero(folds != f), np.flatnonzero(folds == f)
        held = sub.iloc[te][sub.iloc[te]["y"] == 1]
        clfs = {rep: fit_xgb(reps[rep][tr], y[tr], SEED) for rep in reps}
        thr = {rep: results[rep]["_thr"][f] for rep in reps}
        for cond in ["M3", "F200", "M3F200"]:
            views_v = build_variant_views(held, f, cond)
            for rep in reps:
                s = clfs[rep].predict_proba(views_v[rep])[:, 1]
                robustness[rep][cond].append(float((s >= thr[rep]).mean()))
    for rep in reps:
        for cond in ["M3", "F200", "M3F200"]:
            results[rep].setdefault("robustness", {})[cond] = dict(
                recall_mean=float(np.mean(robustness[rep][cond])),
                recall_std=float(np.std(robustness[rep][cond])),
                folds=robustness[rep][cond])

    for rep in reps:
        results[rep].pop("_thr", None)
    with open(os.path.join(OUT, "gateA_results.json"), "w") as f:
        json.dump(dict(representations=list(reps), results=results,
                       dims={rep: int(reps[rep].shape[1]) for rep in reps}), f, indent=2)
    pd.DataFrame(per_row).to_csv(os.path.join(OUT, "gateA_cleanM0_per_row.csv.gz"), index=False)
    write_manifest(OUT, dict(protocol="threshold_protocol_v2 + gateA_success_criteria",
                             reps=list(reps)),
                   [os.path.join(OUT, "gateA_results.json")], started,
                   inputs=[os.path.join(DH, "task_aligned_dataset_v1.csv")])
    verify_frozen_or_die()
    for rep in reps:
        r = results[rep]
        print(f"[{rep}] clean AUPRC {r['cleanM0']['family_AUPRC_mean']:.3f} "
              f"bgFPR {r['cleanM0']['benign_general_FPR_mean']:.3f} | "
              f"F200 R {r['robustness']['F200']['recall_mean']:.3f} "
              f"M3F200 R {r['robustness']['M3F200']['recall_mean']:.3f}")
    print(f"[gateA] done in {time.time()-started:.0f}s")


if __name__ == "__main__":
    main()
