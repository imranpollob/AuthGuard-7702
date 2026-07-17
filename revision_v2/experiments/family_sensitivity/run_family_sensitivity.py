#!/usr/bin/env python3
"""Phase 3C — family threshold + recomputation sensitivity.

Primary track: regroup the task-aligned primary population by the FROZEN family columns at
0.75 / 0.85 / 0.90 (family_id_075 / family_id / family_id_090 in family_assignment_frozen.csv,
row-aligned to capability_dataset.csv, then restricted to retained rows). For each grouping:
recompute GroupKFold(5) folds, run AuthGuard + strongest baseline under the v2 threshold
protocol, and report structure diagnostics + performance + random-vs-family gap.

Sensitivity track: recompute families AFTER task alignment on the retained corpus using the
frozen MinHash clustering at 0.85; report structure + AuthGuard performance; labeled as
sensitivity only. Frozen families are never replaced.
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score
from sklearn.model_selection import GroupKFold

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))
from harness import (load_corpus, feature_views, make_xgb, oof_threshold,  # noqa: E402
                     metrics_full, inner_splits, write_manifest, verify_frozen_or_die,
                     RV2, ROOT, DH, SEED, disasm, minhash_signature)

OUT = os.path.join(RV2, "results", "family_sensitivity")


def structure(sub, famcol):
    g = sub.groupby(famcol)
    sizes = g.size()
    mal = sub[sub["class"] == "malicious"]
    fam_classes = g["class"].nunique()
    comps = []  # min pairwise similarity within components is expensive; report size stats
    return dict(
        n_families=int(len(sizes)), singletons=int((sizes == 1).sum()),
        singleton_pct=round(100 * (sizes == 1).mean(), 1),
        malicious_bearing=int(mal[famcol].nunique()),
        cross_class=int((fam_classes > 1).sum()), largest=int(sizes.max()),
        size_p50=float(sizes.median()), size_p95=float(np.percentile(sizes, 95)),
        size_mean=float(sizes.mean()))


def eval_grouping(sub, Xall, famcol, method, tag):
    y = (sub["class"] == "malicious").astype(int).to_numpy()
    groups = sub[famcol].to_numpy()
    gkf = GroupKFold(5)
    folds = np.full(len(sub), -1)
    for f, (_, te) in enumerate(gkf.split(Xall, y, groups)):
        folds[te] = f
    fam_ap, rnd_ap, fold_m = [], [], []
    # family-grouped
    for f in range(5):
        tr, te = np.flatnonzero(folds != f), np.flatnonzero(folds == f)
        thr, _, _ = oof_threshold(method, Xall[tr], y[tr], groups[tr], SEED)
        model = method["fit"](Xall[tr], y[tr], SEED)
        s = method["score"](model, Xall[te])
        fam_ap.append(float(average_precision_score(y[te], s)))
        fold_m.append(metrics_full(y[te], s, thr))
    # random split (KFold) for the gap
    from sklearn.model_selection import KFold
    kf = KFold(5, shuffle=True, random_state=SEED)
    for tr, te in kf.split(Xall):
        model = method["fit"](Xall[tr], y[tr], SEED)
        s = method["score"](model, Xall[te])
        rnd_ap.append(float(average_precision_score(y[te], s)))
    dm = pd.DataFrame(fold_m)
    return dict(family_AUPRC_mean=float(np.mean(fam_ap)), family_AUPRC_std=float(np.std(fam_ap)),
                random_AUPRC_mean=float(np.mean(rnd_ap)),
                random_minus_family=float(np.mean(rnd_ap) - np.mean(fam_ap)),
                FPR_mean=float(dm["FPR"].mean()), F1_mean=float(dm["F1"].mean()),
                folds_family_AUPRC=fam_ap)


def main():
    started = time.time()
    verify_frozen_or_die()
    os.makedirs(OUT, exist_ok=True)
    df, Xd, Xn, meta = load_corpus()
    views = feature_views(meta)
    authguard = make_xgb(list(range(views["n_dense"] + 512)))
    opcode_xgb = make_xgb(views["hist"])

    # attach frozen 0.75 / 0.90 family columns (row-aligned original CSV) to the retained rows
    cap = pd.read_csv(os.path.join(ROOT, "capability_dataset.csv"))
    fam = pd.read_csv(os.path.join(ROOT, "family_assignment_frozen.csv"))
    cap["_key"] = cap["chain"].astype(str) + ":" + cap["address"].astype(str)
    keymap = {"family_id_075": dict(zip(cap["_key"], fam["family_id_075"])),
              "family_id_090": dict(zip(cap["_key"], fam["family_id_090"]))}
    prim = df[df["class"].isin(["malicious", "benign_cleared"])].reset_index(drop=True).copy()
    prim["fam_075"] = prim["sid"].map(keymap["family_id_075"])
    prim["fam_085"] = prim["family_id"]
    prim["fam_090"] = prim["sid"].map(keymap["family_id_090"])
    Xall = np.hstack([Xd, Xn]).astype(np.float32)[df["class"].isin(["malicious", "benign_cleared"]).to_numpy()]

    results = {"primary_track": {}, "sensitivity_track": {}}
    for thr_name, col in [("0.75", "fam_075"), ("0.85", "fam_085"), ("0.90", "fam_090")]:
        assert prim[col].notna().all(), f"missing family col {col}"
        results["primary_track"][thr_name] = dict(
            structure=structure(prim, col),
            authguard=eval_grouping(prim, Xall, col, authguard, f"prim{thr_name}"),
            opcode_xgb=eval_grouping(prim, Xall, col, opcode_xgb, f"opx{thr_name}"))
        print(f"[fam {thr_name}] AG family AUPRC "
              f"{results['primary_track'][thr_name]['authguard']['family_AUPRC_mean']:.3f} "
              f"gap {results['primary_track'][thr_name]['authguard']['random_minus_family']:.3f}",
              flush=True)

    # sensitivity track: recompute families on retained rows (frozen MinHash @0.85)
    print("[recompute] MinHash over retained corpus...", flush=True)
    sigs = np.empty((len(prim), 128), dtype=np.uint64)
    for i, bc in enumerate(prim["bc"].values):
        ops, _, _ = disasm(bc)
        sigs[i] = minhash_signature(ops, num_perm=128, k=4)

    class UF:
        def __init__(s, n): s.p = list(range(n))
        def find(s, x):
            while s.p[x] != x:
                s.p[x] = s.p[s.p[x]]; x = s.p[x]
            return x
        def union(s, a, b):
            ra, rb = s.find(a), s.find(b)
            if ra != rb: s.p[max(ra, rb)] = min(ra, rb)
    uf = UF(len(prim))
    for i in range(len(prim)):
        eq = (sigs[i + 1:] == sigs[i]).mean(axis=1)
        for j in np.nonzero(eq >= 0.85)[0] + (i + 1):
            uf.union(i, int(j))
    prim["fam_recomputed"] = [f"R{uf.find(i)}" for i in range(len(prim))]
    from sklearn.metrics import adjusted_rand_score
    results["sensitivity_track"]["recomputed_0.85"] = dict(
        structure=structure(prim, "fam_recomputed"),
        authguard=eval_grouping(prim, Xall, "fam_recomputed", authguard, "recomp"),
        adjusted_rand_vs_frozen=float(adjusted_rand_score(prim["fam_085"], prim["fam_recomputed"])),
        note="Sensitivity analysis only; frozen families remain the primary outcome.")
    print(f"[recompute] AG family AUPRC "
          f"{results['sensitivity_track']['recomputed_0.85']['authguard']['family_AUPRC_mean']:.3f} "
          f"ARI vs frozen {results['sensitivity_track']['recomputed_0.85']['adjusted_rand_vs_frozen']:.3f}")

    with open(os.path.join(OUT, "family_sensitivity.json"), "w") as f:
        json.dump(results, f, indent=2)
    write_manifest(OUT, dict(protocol="threshold_protocol_v2; frozen 0.75/0.85/0.90 + recomputed"),
                   [os.path.join(OUT, "family_sensitivity.json")], started,
                   inputs=[os.path.join(DH, "task_aligned_dataset_v1.csv")])
    verify_frozen_or_die()
    print(f"[family_sensitivity] done in {time.time()-started:.0f}s")


if __name__ == "__main__":
    main()
