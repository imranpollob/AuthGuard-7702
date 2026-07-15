#!/usr/bin/env python3
"""Outcome-blind sensitivity rerun on task_aligned_dataset_v1.csv.

Imports frozen project primitives and writes only under paper_build/data_hygiene.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
import time
import warnings

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import KFold
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PIPE = os.path.join(ROOT, "pipeline")
OUT = os.path.join(ROOT, "paper_build", "data_hygiene")
sys.path.insert(0, PIPE)

from ag_common import normalize_bytecode, SEED  # noqa: E402
from ag_features import featurize, build_sensitive_selector_set  # noqa: E402


def load_module(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


det = load_module("det03_ta", os.path.join(PIPE, "03_detection.py"))
mut = load_module("mut04_ta", os.path.join(PIPE, "04_mutations.py"))
adv = load_module("adv_ta", os.path.join(PIPE, "adv_run.py"))
SENS = build_sensitive_selector_set()
XGB_HP = dict(adv.XGB_HP)


class StoredFoldSplitter:
    def __init__(self, folds):
        self.folds = np.asarray(folds, dtype=int)

    def split(self, X, y=None, groups=None):
        idx = np.arange(len(self.folds))
        for f in range(5):
            yield idx[self.folds != f], idx[self.folds == f]


def load_dataset():
    df = pd.read_csv(os.path.join(OUT, "task_aligned_dataset_v1.csv"))
    df["bc"] = df["bytecode"].map(normalize_bytecode)
    df["bchash"] = df["bc"].map(lambda h: hashlib.sha256(h.encode()).hexdigest())
    Xd, Xn, cols = featurize(df["bytecode"].tolist(), sens=SENS)
    meta0 = json.load(open(os.path.join(ROOT, "results", "feature_meta.json")))
    if cols != meta0["dense_cols"]:
        raise AssertionError("task-aligned feature columns differ from frozen columns")
    meta = dict(meta0)
    meta["n_rows"] = len(df)
    np.savez_compressed(os.path.join(OUT, "task_aligned_features_dense.npz"), X=Xd)
    np.savez_compressed(os.path.join(OUT, "task_aligned_features_ngram.npz"), X=Xn)
    with open(os.path.join(OUT, "task_aligned_feature_meta.json"), "w") as f:
        json.dump(meta, f, indent=2)
    return df, Xd, Xn, meta


def run_det(df, Xd, Xn, meta):
    print("\n=== G-DET ===", flush=True)
    tasks = {
        "primary_mal_vs_cleared": (
            df["class"].isin(["malicious", "benign_cleared"]), "outer_fold_primary"),
        "secondary_mal_vs_cleared_general": (
            df["class"].isin(["malicious", "benign_cleared", "benign_general"]),
            "outer_fold_secondary"),
    }
    out = {}
    for name, (mask, foldcol) in tasks.items():
        folds = df.loc[mask, foldcol]
        if folds.isna().any():
            raise AssertionError(f"missing stored fold for {name}")
        print(f"[{name}] family-grouped stored folds", flush=True)
        lfo = det.run_cv(df, Xd, Xn, meta, mask, StoredFoldSplitter(folds),
                         group="family", tag=f"TA/{name}/family")
        print(f"[{name}] random diagnostic", flush=True)
        rnd = det.run_cv(df, Xd, Xn, meta, mask,
                         KFold(5, shuffle=True, random_state=SEED),
                         group=None, tag=f"TA/{name}/random")
        out[name] = {"leave_family_out": lfo, "random_split": rnd}
    with open(os.path.join(OUT, "task_aligned_detection_results.json"), "w") as f:
        json.dump(out, f, indent=2)
    return out


def primary_arrays(df, Xd, Xn, meta):
    mask = df["class"].isin(["malicious", "benign_cleared"]).to_numpy()
    sub = df.loc[mask].reset_index(drop=True).copy()
    sub["bc"] = sub["bytecode"].map(normalize_bytecode)
    sub["bchash"] = sub["bc"].map(lambda h: hashlib.sha256(h.encode()).hexdigest())
    y = (sub["class"] == "malicious").astype(int).to_numpy()
    return sub, y, Xd[mask], Xn[mask]


def run_mut(df, Xd, Xn, meta):
    print("\n=== G-MUT / G-VOL ===", flush=True)
    sub, y, Xds, Xns = primary_arrays(df, Xd, Xn, meta)
    Xfull = np.hstack([Xds, Xns])
    hist = slice(0, meta["hist_dim"])
    name_j = meta["dense_cols"].index("has_sensitive_selector")
    call_j = meta["dense_cols"].index("n_call_family")
    sel_cols = [i for i, c in enumerate(meta["dense_cols"])
                if c.startswith("has_") or c in
                ("n_selectors", "n_sensitive_selectors", "n_call_family", "n_delegatecall")]
    tiers = ["M0", "M1", "M2", "M3"]
    methods = ["usenix_name_rule", "usenix_struct_rule", "blocklist",
               "opcode_xgb", "selector_model", "authguard"]
    curve = {m: {t: [] for t in tiers} for m in methods}
    preservation = {t: {"checked": 0, "preserved": 0} for t in tiers if t != "M0"}
    folds = sub["outer_fold_primary"].astype(int).to_numpy()

    for fold in range(5):
        tr = np.flatnonzero(folds != fold)
        te = np.flatnonzero(folds == fold)
        ytr = y[tr]
        xgb = mut.gb(); xgb.fit(Xds[tr][:, hist], ytr)
        thr_xgb = mut.best_f1_threshold(ytr, xgb.predict_proba(Xds[tr][:, hist])[:, 1])
        ag = mut.gb(); ag.fit(Xfull[tr], ytr)
        thr_ag = mut.best_f1_threshold(ytr, ag.predict_proba(Xfull[tr])[:, 1])
        scaler = StandardScaler().fit(Xds[tr][:, sel_cols])
        lr = LogisticRegression(max_iter=1000, random_state=SEED)
        lr.fit(scaler.transform(Xds[tr][:, sel_cols]), ytr)
        thr_lr = mut.best_f1_threshold(
            ytr, lr.predict_proba(scaler.transform(Xds[tr][:, sel_cols]))[:, 1])
        train_mal_hashes = set(sub.iloc[tr][ytr.astype(bool)]["bchash"])
        held = sub.iloc[[i for i in te if y[i] == 1]]

        for tier in tiers:
            hexes, hashes = [], []
            for _, row in held.iterrows():
                mb = mut.make_mutant(row["bytecode"], row["address"], tier)
                if tier != "M0":
                    preservation[tier]["checked"] += 1
                    preservation[tier]["preserved"] += int(mut.verify_preservation(row["bytecode"], mb))
                h = mb.hex(); hexes.append(h)
                hashes.append(hashlib.sha256(normalize_bytecode(h).encode()).hexdigest())
            xd, xn, _ = featurize(hexes, sens=SENS)
            xf = np.hstack([xd, xn])
            curve["usenix_name_rule"][tier].append(float((xd[:, name_j] > 0).mean()))
            curve["usenix_struct_rule"][tier].append(float((xd[:, call_j] > 0).mean()))
            curve["blocklist"][tier].append(float(np.mean([h in train_mal_hashes for h in hashes])))
            curve["opcode_xgb"][tier].append(float(
                (xgb.predict_proba(xd[:, hist])[:, 1] >= thr_xgb).mean()))
            curve["selector_model"][tier].append(float(
                (lr.predict_proba(scaler.transform(xd[:, sel_cols]))[:, 1] >= thr_lr).mean()))
            curve["authguard"][tier].append(float(
                (ag.predict_proba(xf)[:, 1] >= thr_ag).mean()))
        print(f"[G-MUT fold {fold}] AG M0={curve['authguard']['M0'][-1]:.3f} "
              f"M3={curve['authguard']['M3'][-1]:.3f}", flush=True)

    agg = {m: {t: {"mean": float(np.mean(curve[m][t])),
                        "std": float(np.std(curve[m][t])),
                        "folds": curve[m][t]} for t in tiers} for m in methods}

    fracs = [0.0, 0.25, 0.5, 1.0, 2.0]
    vmethods = ["opcode_xgb", "authguard", "usenix_struct_rule", "usenix_name_rule"]
    volume = {m: {f: [] for f in fracs} for m in vmethods}
    for fold in range(5):
        tr = np.flatnonzero(folds != fold); te = np.flatnonzero(folds == fold); ytr = y[tr]
        xgb = mut.gb(); xgb.fit(Xds[tr][:, hist], ytr)
        thr_xgb = mut.best_f1_threshold(ytr, xgb.predict_proba(Xds[tr][:, hist])[:, 1])
        ag = mut.gb(); ag.fit(Xfull[tr], ytr)
        thr_ag = mut.best_f1_threshold(ytr, ag.predict_proba(Xfull[tr])[:, 1])
        held = sub.iloc[[i for i in te if y[i] == 1]]
        for frac in fracs:
            hexes = []
            for _, row in held.iterrows():
                b = mut.to_bytes(row["bytecode"])
                b = mut.mut_metadata(b, row["address"])
                b = mut.mut_addr_immediates(b, row["address"])
                b = mut.mut_selector_rewrite(b, row["address"])
                b = mut.mut_deadcode_append(b, row["address"], frac)
                hexes.append(b.hex())
            xd, xn, _ = featurize(hexes, sens=SENS); xf = np.hstack([xd, xn])
            volume["opcode_xgb"][frac].append(float(
                (xgb.predict_proba(xd[:, hist])[:, 1] >= thr_xgb).mean()))
            volume["authguard"][frac].append(float(
                (ag.predict_proba(xf)[:, 1] >= thr_ag).mean()))
            volume["usenix_struct_rule"][frac].append(float((xd[:, call_j] > 0).mean()))
            volume["usenix_name_rule"][frac].append(float((xd[:, name_j] > 0).mean()))
        print(f"[G-VOL fold {fold}] AG +200={volume['authguard'][2.0][-1]:.3f}", flush=True)
    vagg = {m: {str(f): {"mean": float(np.mean(volume[m][f])),
                              "std": float(np.std(volume[m][f])),
                              "folds": volume[m][f]} for f in fracs} for m in vmethods}
    with open(os.path.join(OUT, "task_aligned_mutation_curve.json"), "w") as f:
        json.dump(agg, f, indent=2)
    with open(os.path.join(OUT, "task_aligned_mutation_preservation.json"), "w") as f:
        json.dump(preservation, f, indent=2)
    with open(os.path.join(OUT, "task_aligned_mutation_volume.json"), "w") as f:
        json.dump(vagg, f, indent=2)
    return agg, preservation, vagg


def run_adv(df, Xd, Xn, meta):
    print("\n=== G-ADV ===", flush=True)
    sub, _, _, _ = primary_arrays(df, Xd, Xn, meta)
    sub["y"] = (sub["class"] == "malicious").astype(int)
    sub["sid"] = sub["chain"].astype(str) + ":" + sub["address"].astype(str)
    folds = sub["outer_fold_primary"].astype(int).to_numpy()
    models = ["opcode-histogram RF", "opcode-histogram XGBoost",
              "opcode-histogram XGBoost-aug", "AuthGuard-M0", "AuthGuard-aug"]
    results = {m: {c: [] for c in adv.ALL_TEST} for m in models}
    paired_rows, threshold_rows, composition_rows, leak_lines = [], [], [], []

    for fold in range(5):
        te = sub.iloc[np.flatnonzero(folds == fold)]
        va = sub.iloc[np.flatnonzero(folds == ((fold + 1) % 5))]
        tr = sub.iloc[np.flatnonzero((folds != fold) & (folds != ((fold + 1) % 5)))]
        if (set(tr.family_id) & set(va.family_id) or set(tr.family_id) & set(te.family_id)
                or set(va.family_id) & set(te.family_id)):
            raise AssertionError("stored family folds overlap")
        train = adv.build(tr, adv.SEEN, "train")
        val = adv.build(va, ["M0"], "train")
        counts = pd.Series(train["sid"]).value_counts().to_dict()
        weights = np.array([1.0 / counts[s] for s in train["sid"]], dtype=np.float32)
        tests = {c: adv.build(te, [c], "test") for c in adv.ALL_TEST}
        train_hashes = set(train["bchash"])
        test_hashes = set(np.concatenate([tests[c]["bchash"] for c in adv.ALL_TEST]))
        if train_hashes & test_hashes:
            raise AssertionError("task-aligned train/test bytecode hash overlap")
        leak_lines.append(f"fold {fold}: source/family/hash overlap=0; mutant inheritance=True")

        for c in adv.SEEN:
            cm = train["cond"] == c
            composition_rows.append({"fold": fold, "condition": c,
                                     "malicious": int(((train["y"] == 1) & cm).sum()),
                                     "benign": int(((train["y"] == 0) & cm).sum())})

        def fit(kind, augmented):
            if kind == "rf":
                m0 = train["cond"] == "M0"
                clf = RandomForestClassifier(n_estimators=300, random_state=SEED, n_jobs=4)
                clf.fit(train["Xhist"][m0], train["y"][m0])
                return clf
            X = train["Xfull"] if kind == "full" else train["Xhist"]
            yy, ww = train["y"], weights
            if not augmented:
                m0 = train["cond"] == "M0"; X, yy = X[m0], yy[m0]
                ww = np.ones(int(m0.sum()), dtype=np.float32)
            clf = XGBClassifier(**XGB_HP); clf.fit(X, yy, sample_weight=ww)
            return clf

        fitted = {
            "opcode-histogram RF": ("hist", fit("rf", False)),
            "opcode-histogram XGBoost": ("hist", fit("hist", False)),
            "opcode-histogram XGBoost-aug": ("hist", fit("hist", True)),
            "AuthGuard-M0": ("full", fit("full", False)),
            "AuthGuard-aug": ("full", fit("full", True)),
        }
        thresholds = {}
        for name, (kind, clf) in fitted.items():
            Xv = val["Xfull"] if kind == "full" else val["Xhist"]
            thresholds[name] = adv.best_f1_threshold(val["y"], clf.predict_proba(Xv)[:, 1])
            threshold_rows.append({"fold": fold, "model": name, "threshold": thresholds[name]})

        m0_recall = {}
        for cond in adv.ALL_TEST:
            tc = tests[cond]
            for name, (kind, clf) in fitted.items():
                Xc = tc["Xfull"] if kind == "full" else tc["Xhist"]
                scores = clf.predict_proba(Xc)[:, 1]
                metrics = adv.metrics(tc["y"], scores, thresholds[name],
                                      m0_recall.get(name) if cond != "M0" else None)
                if cond == "M0":
                    m0_recall[name] = metrics["recall"]
                results[name][cond].append(metrics)
                pred = (scores >= thresholds[name]).astype(int)
                for k in range(len(scores)):
                    paired_rows.append({
                        "sample_id": tc["sid"][k], "family_id": tc["fam"][k],
                        "fold": fold, "true_label": int(tc["y"][k]), "model": name,
                        "condition": cond, "mutation_seed": tc["seed"][k],
                        "raw_score": float(scores[k]), "threshold": thresholds[name],
                        "predicted_label": int(pred[k]),
                    })
        print(f"[G-ADV fold {fold}] AG-M0/aug F200 recall "
              f"{results['AuthGuard-M0']['F200'][-1]['recall']:.3f}/"
              f"{results['AuthGuard-aug']['F200'][-1]['recall']:.3f}", flush=True)

    aggregate = {}
    for model in models:
        aggregate[model] = {}
        for cond in adv.ALL_TEST:
            d = pd.DataFrame(results[model][cond])
            aggregate[model][cond] = {
                "mean": d.mean(numeric_only=True).to_dict(),
                "std": d.std(numeric_only=True, ddof=0).to_dict(),
                "folds": d.to_dict(orient="records"),
            }
    output = {"aggregate": aggregate, "seen": adv.SEEN, "held_out": adv.HELD,
              "all_test": adv.ALL_TEST, "fold_source": "stored original outer_fold_primary"}
    with open(os.path.join(OUT, "task_aligned_advtrain_results.json"), "w") as f:
        json.dump(output, f, indent=2)
    pd.DataFrame(paired_rows).to_csv(os.path.join(OUT, "task_aligned_paired_results.csv"), index=False)
    pd.DataFrame(threshold_rows).to_csv(os.path.join(OUT, "task_aligned_advtrain_thresholds.csv"), index=False)
    pd.DataFrame(composition_rows).to_csv(os.path.join(OUT, "task_aligned_advtrain_composition.csv"), index=False)
    with open(os.path.join(OUT, "task_aligned_advtrain_leakage_assertions.txt"), "w") as f:
        f.write("ALL TASK-ALIGNED LEAKAGE ASSERTIONS PASSED\n" + "\n".join(leak_lines) + "\n")
    return output


def consolidate(det_out=None, mut_out=None, preservation=None, vol_out=None, adv_out=None):
    paths = {
        "G_DET": "task_aligned_detection_results.json",
        "G_MUT": "task_aligned_mutation_curve.json",
        "mutation_preservation": "task_aligned_mutation_preservation.json",
        "G_VOL": "task_aligned_mutation_volume.json",
        "G_ADV": "task_aligned_advtrain_results.json",
    }
    supplied = {"G_DET": det_out, "G_MUT": mut_out, "mutation_preservation": preservation,
                "G_VOL": vol_out, "G_ADV": adv_out}
    out = {"protocol_sha256": open(os.path.join(OUT, "task_alignment_protocol.sha256")).read().split()[0]}
    for key, filename in paths.items():
        value = supplied[key]
        if value is None and os.path.exists(os.path.join(OUT, filename)):
            value = json.load(open(os.path.join(OUT, filename)))
        if value is not None:
            out[key] = value
    out["manifest"] = json.load(open(os.path.join(OUT, "task_aligned_manifest_summary.json")))
    with open(os.path.join(OUT, "task_aligned_results.json"), "w") as f:
        json.dump(out, f, indent=2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("groups", nargs="*", choices=["det", "mut", "adv"],
                    default=["det", "mut", "adv"])
    args = ap.parse_args()
    started = time.time()
    df, Xd, Xn, meta = load_dataset()
    d = m = p = v = a = None
    if "det" in args.groups:
        d = run_det(df, Xd, Xn, meta)
    if "mut" in args.groups:
        m, p, v = run_mut(df, Xd, Xn, meta)
    if "adv" in args.groups:
        a = run_adv(df, Xd, Xn, meta)
    consolidate(d, m, p, v, a)
    print(f"\ncompleted requested groups in {time.time() - started:.1f}s", flush=True)


if __name__ == "__main__":
    main()
