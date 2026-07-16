#!/usr/bin/env python3
"""G-ADV v2: donor-isolated source-balanced augmentation.

Changes vs frozen v1 (which is retained, labeled donor-confounded):
  * flooding donors come from partition-isolated multi-donor pools (protocol v1.1),
    with a full per-segment provenance ledger;
  * the held-out compound condition M3F200 (full M3 recipe + 200% flooding) is evaluated;
  * 3 model seeds; primary thresholds = family-disjoint clean-M0 validation fold (as v1);
    sensitivity arm = inner family-grouped OOF thresholds (seed 7702 only);
  * per-row scores persisted for all seeds and both threshold arms.

Split per outer fold f: test = fold f, val = fold (f+1)%5, train-fit = remaining 3 folds.
SEEN (train aug) = M0 M1 M2 F25 F50 F100; HELD = M3 F200 M3F200.
"""
import hashlib
import json
import os
import sys
import time

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))
sys.path.insert(0, os.path.join(HERE, "..", "donor_pools"))
from harness import (load_corpus, task_arrays, feature_views, best_f1_threshold,  # noqa: E402
                     inner_splits, metrics_full, write_manifest, verify_frozen_or_die,
                     RV2, DH, SEED, featurize, SENS, XGB_HP)
from pools import DonorPools, make_variant_isolated  # noqa: E402

OUT = os.path.join(RV2, "results", "gadv_v2")
SEEN = ["M0", "M1", "M2", "F25", "F50", "F100"]
HELD = ["M3", "F200", "M3F200"]
ALL_TEST = SEEN + HELD
MODEL_SEEDS = [SEED, 7703, 7704]
MODELS = ["opcode-histogram RF", "opcode-histogram XGBoost", "opcode-histogram XGBoost-aug",
          "AuthGuard-M0", "AuthGuard-aug"]


def build(pools, sources, conditions, fold, partition, hist_slice):
    hexes, y, sid, fam, cond_l = [], [], [], [], []
    for _, r in sources.iterrows():
        row = r.to_dict()
        for c in conditions:
            h = make_variant_isolated(pools, row, fold, partition, c,
                                      "train" if partition in ("train", "val") else "test")
            hexes.append(h); y.append(int(r["y"])); sid.append(r["sid"])
            fam.append(r["family_id"]); cond_l.append(c)
    Xd, Xn, _ = featurize(hexes, sens=SENS)
    Xfull = np.hstack([Xd, Xn]).astype(np.float32)
    return dict(Xfull=Xfull, Xhist=Xd[:, hist_slice].astype(np.float32),
                y=np.array(y), sid=np.array(sid), fam=np.array(fam), cond=np.array(cond_l),
                bchash=np.array([hashlib.sha256(h.encode()).hexdigest() for h in hexes]))


def main():
    started = time.time()
    verify_frozen_or_die()
    os.makedirs(OUT, exist_ok=True)
    df, Xd, Xn, meta = load_corpus()
    views = feature_views(meta)
    hist_slice = views["hist"]
    sub, y, folds, _, _ = task_arrays(df, Xd, Xn, "primary")
    sub = sub.copy(); sub["y"] = y
    pools = DonorPools(df.assign(y=(df["class"] == "malicious").astype(int)),
                       "benign_general", "outer_fold_primary", "GADV_V2")

    results = {arm: {m: {c: [] for c in ALL_TEST} for m in MODELS}
               for arm in ["val_threshold", "oof_threshold"]}
    paired_rows, thr_rows, comp_rows, leak_lines = [], [], [], []

    for f in range(5):
        pools.assert_disjoint(f)
        vf = (f + 1) % 5
        te = sub[folds == f]; va = sub[folds == vf]
        tr = sub[(folds != f) & (folds != vf)]
        tr4 = sub[folds != f]  # 4-fold training population for the OOF sensitivity arm
        assert not (set(tr.family_id) & set(va.family_id)) and \
               not (set(tr.family_id) & set(te.family_id)) and \
               not (set(va.family_id) & set(te.family_id))

        t0 = time.time()
        train = build(pools, tr, SEEN, f, "train", hist_slice)
        val = build(pools, va, ["M0"], f, "val", hist_slice)
        train4 = build(pools, tr4, SEEN, f, "train", hist_slice)
        tests = {c: build(pools, te, [c], f, "test", hist_slice) for c in ALL_TEST}
        cnt = pd.Series(train["sid"]).value_counts().to_dict()
        w = np.array([1.0 / cnt[s] for s in train["sid"]], dtype=np.float32)
        cnt4 = pd.Series(train4["sid"]).value_counts().to_dict()
        w4 = np.array([1.0 / cnt4[s] for s in train4["sid"]], dtype=np.float32)

        ht = set(train["bchash"]) | set(train4["bchash"]) | set(val["bchash"])
        he = set(np.concatenate([tests[c]["bchash"] for c in ALL_TEST]))
        assert not (ht & he), f"fold {f} bytecode-hash leakage"
        leak_lines.append(f"fold {f}: source/family overlap=0; train(+val)/test hash overlap=0; "
                          f"donor pools disjoint=True")
        for c in SEEN:
            m = train["cond"] == c
            comp_rows.append(dict(fold=f, condition=c,
                                  malicious=int(((train["y"] == 1) & m).sum()),
                                  benign=int(((train["y"] == 0) & m).sum())))

        def fit_model(name, data, weights, seed):
            m0 = data["cond"] == "M0"
            if name == "opcode-histogram RF":
                clf = RandomForestClassifier(n_estimators=300, random_state=seed, n_jobs=4)
                clf.fit(data["Xhist"][m0], data["y"][m0]); return ("hist", clf)
            aug = name.endswith("-aug")
            kind = "full" if name.startswith("AuthGuard") else "hist"
            X = data["Xfull"] if kind == "full" else data["Xhist"]
            if aug:
                yy, sw = data["y"], weights
            else:
                X, yy = X[m0], data["y"][m0]
                sw = np.ones(int(m0.sum()), dtype=np.float32)
            clf = XGBClassifier(random_state=seed, **XGB_HP)
            clf.fit(X, yy, sample_weight=sw)
            return (kind, clf)

        # ---- primary arm: 3-fold fit, val-fold clean-M0 thresholds, all seeds ----
        for seed in MODEL_SEEDS:
            fitted = {n: fit_model(n, train, w, seed) for n in MODELS}
            for name, (kind, clf) in fitted.items():
                Xv = val["Xfull"] if kind == "full" else val["Xhist"]
                thr = best_f1_threshold(val["y"], clf.predict_proba(Xv)[:, 1])
                thr_rows.append(dict(arm="val_threshold", fold=f, model=name, seed=seed,
                                     threshold=thr))
                for cond in ALL_TEST:
                    tc = tests[cond]
                    Xc = tc["Xfull"] if kind == "full" else tc["Xhist"]
                    s = clf.predict_proba(Xc)[:, 1]
                    mm = metrics_full(tc["y"], s, thr)
                    if seed == SEED:
                        results["val_threshold"][name][cond].append(mm)
                    pred = (s >= thr).astype(int)
                    for k in range(len(s)):
                        paired_rows.append(dict(arm="val_threshold", fold=f, model=name,
                                                seed=seed, condition=cond,
                                                sid=tc["sid"][k], family_id=tc["fam"][k],
                                                y=int(tc["y"][k]), score=float(s[k]),
                                                threshold=thr, pred=int(pred[k])))

        # ---- sensitivity arm: 4-fold fit, inner family-grouped OOF thresholds, seed 7702 ----
        seed = SEED
        groups4 = train4["fam"]
        # inner OOF at SOURCE level: group by family over the augmented training matrix
        for name in MODELS:
            kind = "full" if name.startswith("AuthGuard") else "hist"
            X4 = train4["Xfull"] if kind == "full" else train4["Xhist"]
            y4 = train4["y"]
            splits, splitter = inner_splits(y4, groups4, seed=seed)
            oof = np.full(len(y4), np.nan)
            for itr, iva in splits:
                sub4 = {k: train4[k][itr] for k in ["Xfull", "Xhist", "y", "cond", "sid"]}
                cnt_i = pd.Series(sub4["sid"]).value_counts().to_dict()
                w_i = np.array([1.0 / cnt_i[s] for s in sub4["sid"]], dtype=np.float32)
                _, clf_i = fit_model(name, sub4, w_i, seed)
                Xi = train4["Xfull"][iva] if kind == "full" else train4["Xhist"][iva]
                oof[iva] = clf_i.predict_proba(Xi)[:, 1]
            m0_mask = train4["cond"] == "M0"
            thr = best_f1_threshold(y4[m0_mask], oof[m0_mask])
            kind, clf = fit_model(name, train4, w4, seed)
            thr_rows.append(dict(arm="oof_threshold", fold=f, model=name, seed=seed,
                                 threshold=thr, splitter=splitter))
            for cond in ALL_TEST:
                tc = tests[cond]
                Xc = tc["Xfull"] if kind == "full" else tc["Xhist"]
                s = clf.predict_proba(Xc)[:, 1]
                mm = metrics_full(tc["y"], s, thr)
                results["oof_threshold"][name][cond].append(mm)
                pred = (s >= thr).astype(int)
                for k in range(len(s)):
                    paired_rows.append(dict(arm="oof_threshold", fold=f, model=name,
                                            seed=seed, condition=cond, sid=tc["sid"][k],
                                            family_id=tc["fam"][k], y=int(tc["y"][k]),
                                            score=float(s[k]), threshold=thr,
                                            pred=int(pred[k])))
        r = results["val_threshold"]
        print(f"[fold {f}] {time.time()-t0:.0f}s | AG-M0/aug F200 R "
              f"{r['AuthGuard-M0']['F200'][-1]['Recall']:.3f}/"
              f"{r['AuthGuard-aug']['F200'][-1]['Recall']:.3f} | compound "
              f"{r['AuthGuard-M0']['M3F200'][-1]['Recall']:.3f}/"
              f"{r['AuthGuard-aug']['M3F200'][-1]['Recall']:.3f}", flush=True)

    agg = {}
    for arm in results:
        agg[arm] = {}
        for m in MODELS:
            agg[arm][m] = {}
            for c in ALL_TEST:
                d = pd.DataFrame(results[arm][m][c])
                agg[arm][m][c] = {"mean": d.mean(numeric_only=True).to_dict(),
                                  "std": d.std(numeric_only=True, ddof=0).to_dict(),
                                  "folds": d.to_dict(orient="records")}
    with open(os.path.join(OUT, "gadv_v2_results.json"), "w") as fjson:
        json.dump(dict(aggregate=agg, seen=SEEN, held_out=HELD, all_test=ALL_TEST,
                       model_seeds=MODEL_SEEDS,
                       primary_arm="val_threshold", sensitivity_arm="oof_threshold",
                       donor_protocol="donor_isolation_protocol v1.1 (benign_general pools)"),
                  fjson, indent=2)
    pd.DataFrame(paired_rows).to_csv(os.path.join(OUT, "gadv_v2_paired_results.csv.gz"),
                                     index=False)
    pd.DataFrame(thr_rows).to_csv(os.path.join(OUT, "gadv_v2_thresholds.csv"), index=False)
    pd.DataFrame(comp_rows).to_csv(os.path.join(OUT, "gadv_v2_training_composition.csv"),
                                   index=False)
    led = pools.write_ledger(os.path.join(OUT, "donor_ledger_gadv.csv.gz"))
    with open(os.path.join(OUT, "gadv_v2_leakage_assertions.txt"), "w") as ftxt:
        ftxt.write("ALL G-ADV-V2 LEAKAGE + DONOR-ISOLATION ASSERTIONS PASSED\n"
                   + "\n".join(leak_lines) + f"\nledger rows: {len(led)}\n")

    outputs = [os.path.join(OUT, p) for p in
               ["gadv_v2_results.json", "gadv_v2_paired_results.csv.gz",
                "gadv_v2_thresholds.csv", "gadv_v2_training_composition.csv",
                "donor_ledger_gadv.csv.gz", "gadv_v2_leakage_assertions.txt"]]
    write_manifest(OUT, dict(protocols=["threshold_protocol_v2 (G-ADV primary=val fold)",
                                        "donor_isolation_protocol v1.1"],
                             seeds=MODEL_SEEDS, seen=SEEN, held=HELD),
                   outputs, started,
                   inputs=[os.path.join(DH, "task_aligned_dataset_v1.csv")])
    verify_frozen_or_die()
    print(f"[gadv_v2] done in {time.time()-started:.0f}s")


if __name__ == "__main__":
    main()
