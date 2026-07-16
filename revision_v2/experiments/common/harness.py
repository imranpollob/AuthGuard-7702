#!/usr/bin/env python3
"""Shared Revision-v2 experiment harness.

Implements threshold_protocol_v2.md: inner family-grouped stratified OOF threshold selection,
refit on full outer-train, single test evaluation, per-row score persistence, FPR metrics.

Frozen modules (pipeline/ag_common.py, pipeline/ag_features.py) are imported read-only.
All outputs go under revision_v2/. Never writes outside revision_v2/.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import warnings

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import KFold, StratifiedGroupKFold
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
PIPE = os.path.join(ROOT, "pipeline")
DH = os.path.join(ROOT, "paper_build", "data_hygiene")
RV2 = os.path.join(ROOT, "revision_v2")
sys.path.insert(0, PIPE)

from ag_common import normalize_bytecode, disasm, SEED  # noqa: E402
from ag_features import featurize, build_sensitive_selector_set  # noqa: E402

SENS = build_sensitive_selector_set()
N_OUTER = 5
N_INNER = 4

XGB_HP = dict(n_estimators=300, max_depth=6, learning_rate=0.1, subsample=0.9,
              colsample_bytree=0.8, eval_metric="logloss", n_jobs=4, tree_method="hist")


def blake_seed(*parts) -> int:
    h = hashlib.blake2b(":".join(str(p) for p in parts).encode(), digest_size=8,
                        salt=SEED.to_bytes(8, "little"))
    return int.from_bytes(h.digest(), "little")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Data loading (frozen inputs, read-only)
# ---------------------------------------------------------------------------
def load_corpus():
    """Task-aligned v1 corpus + frozen features + meta. Returns (df, Xd, Xn, meta)."""
    df = pd.read_csv(os.path.join(DH, "task_aligned_dataset_v1.csv"))
    df["bc"] = df["bytecode"].map(normalize_bytecode)
    df["bchash"] = df["bc"].map(lambda h: hashlib.sha256(h.encode()).hexdigest())
    df["sid"] = df["chain"].astype(str) + ":" + df["address"].astype(str)
    Xd = np.load(os.path.join(DH, "task_aligned_features_dense.npz"))["X"]
    Xn = np.load(os.path.join(DH, "task_aligned_features_ngram.npz"))["X"]
    meta = json.load(open(os.path.join(DH, "task_aligned_feature_meta.json")))
    assert len(df) == Xd.shape[0] == Xn.shape[0]
    return df, Xd, Xn, meta


def task_arrays(df, Xd, Xn, task="primary"):
    """Subset to a task population with stored outer folds."""
    if task == "primary":
        mask = df["class"].isin(["malicious", "benign_cleared"])
        foldcol = "outer_fold_primary"
    elif task == "secondary":
        mask = df["class"].isin(["malicious", "benign_cleared", "benign_general"])
        foldcol = "outer_fold_secondary"
    else:
        raise ValueError(task)
    sub = df.loc[mask].reset_index(drop=True)
    assert not sub[foldcol].isna().any()
    y = (sub["class"] == "malicious").astype(int).to_numpy()
    folds = sub[foldcol].astype(int).to_numpy()
    return sub, y, folds, Xd[mask.to_numpy()], Xn[mask.to_numpy()]


def feature_views(meta):
    """Column-index helpers over [dense | ngram] stacking (dense first)."""
    hist_dim = meta["hist_dim"]
    dcols = meta["dense_cols"]
    n_dense = len(dcols)
    sel_cols = [i for i, c in enumerate(dcols)
                if c.startswith("has_") or c in ("n_selectors", "n_sensitive_selectors",
                                                 "n_call_family", "n_delegatecall")]
    length_cols = [dcols.index(c) for c in ("code_bytes", "n_ops") if c in dcols]
    return dict(hist=list(range(hist_dim)),
                struct=list(range(hist_dim, n_dense)),
                dense=list(range(n_dense)),
                sel=sel_cols,
                length=length_cols,
                n_dense=n_dense)


# ---------------------------------------------------------------------------
# Threshold selection (protocol v2)
# ---------------------------------------------------------------------------
def best_f1_threshold(y_true, scores):
    order = np.argsort(-scores)
    ys = np.asarray(y_true)[order]
    tp = np.cumsum(ys); fp = np.cumsum(1 - ys); P = ys.sum()
    prec = tp / np.maximum(tp + fp, 1)
    rec = tp / max(P, 1)
    f1 = 2 * prec * rec / np.maximum(prec + rec, 1e-9)
    return float(np.asarray(scores)[order][int(np.argmax(f1))]) if len(f1) else 0.5


def inner_splits(y_tr, groups_tr, n_splits=N_INNER, seed=SEED):
    """Deterministic group-aware stratified inner splits. Asserts both classes per val fold.
    Falls back to a greedy deterministic allocator if StratifiedGroupKFold fails the check."""
    try:
        sgkf = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
        splits = list(sgkf.split(np.zeros(len(y_tr)), y_tr, groups_tr))
        if all(len(set(y_tr[va])) == 2 for _, va in splits):
            return splits, "StratifiedGroupKFold"
    except Exception:
        pass
    # deterministic greedy fallback: sort families by hashed id, assign to the fold with the
    # smallest count of that family's majority class
    fam = pd.Series(groups_tr)
    fam_order = sorted(fam.unique(), key=lambda f: blake_seed("innerfold", f))
    counts = np.zeros((n_splits, 2))
    assign = {}
    ally = pd.Series(y_tr)
    for f in fam_order:
        idx = fam[fam == f].index
        pos = int(ally[idx].sum()); neg = len(idx) - pos
        target = np.argmin(counts[:, 1] if pos >= neg else counts[:, 0])
        assign[f] = int(target)
        counts[target, 0] += neg; counts[target, 1] += pos
    fold_of = fam.map(assign).to_numpy()
    splits = [(np.flatnonzero(fold_of != k), np.flatnonzero(fold_of == k))
              for k in range(n_splits)]
    assert all(len(set(y_tr[va])) == 2 for _, va in splits), "fallback stratification failed"
    return splits, "greedy_group_stratified_fallback"


def oof_threshold(method, X_tr, y_tr, groups_tr, seed=SEED):
    """Inner family-grouped OOF predictions on the outer-train population -> max-F1 threshold.
    Returns (threshold, splitter_name, oof_scores)."""
    splits, splitter_name = inner_splits(y_tr, groups_tr, seed=seed)
    oof = np.full(len(y_tr), np.nan)
    for itr, iva in splits:
        model = method["fit"](X_tr[itr], y_tr[itr], seed)
        oof[iva] = method["score"](model, X_tr[iva])
    assert not np.isnan(oof).any(), "incomplete OOF coverage"
    return best_f1_threshold(y_tr, oof), splitter_name, oof


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
def metrics_full(y, s, thr):
    y = np.asarray(y); s = np.asarray(s)
    pred = (s >= thr).astype(int)
    tp = int(((pred == 1) & (y == 1)).sum()); fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum()); tn = int(((pred == 0) & (y == 0)).sum())
    P, N = tp + fn, fp + tn
    rec = tp / P if P else float("nan")
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    fpr = fp / N if N else float("nan")
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    two = len(set(y.tolist())) > 1
    return dict(AUPRC=float(average_precision_score(y, s)) if two else float("nan"),
                AUROC=float(roc_auc_score(y, s)) if two else float("nan"),
                F1=float(f1), Precision=float(prec), Recall=float(rec), FPR=float(fpr),
                TP=tp, FP=fp, FN=fn, TN=tn)


# ---------------------------------------------------------------------------
# Method registry
# ---------------------------------------------------------------------------
def make_xgb(cols):
    def fit(X, y, seed):
        clf = XGBClassifier(random_state=seed, **XGB_HP)
        clf.fit(X[:, cols], y)
        return clf
    def score(m, X):
        return m.predict_proba(X[:, cols])[:, 1]
    return dict(fit=fit, score=score, kind="learned")


def make_rf(cols):
    def fit(X, y, seed):
        clf = RandomForestClassifier(n_estimators=300, random_state=seed, n_jobs=4)
        clf.fit(X[:, cols], y)
        return clf
    def score(m, X):
        return m.predict_proba(X[:, cols])[:, 1]
    return dict(fit=fit, score=score, kind="learned")


def make_logreg(cols):
    def fit(X, y, seed):
        sc = StandardScaler().fit(X[:, cols])
        lr = LogisticRegression(max_iter=1000, random_state=seed)
        lr.fit(sc.transform(X[:, cols]), y)
        return (sc, lr)
    def score(m, X):
        sc, lr = m
        return lr.predict_proba(sc.transform(X[:, cols]))[:, 1]
    return dict(fit=fit, score=score, kind="learned")


def default_methods(views, n_dense):
    """The v1 method set re-expressed for the v2 harness (learned methods only; rules and
    blocklist are handled separately since they need raw columns / no thresholds)."""
    full_cols = list(range(n_dense + 512))
    return {
        "opcode_rf": make_rf(views["hist"]),
        "opcode_xgb": make_xgb(views["hist"]),
        "selector_model": make_logreg(views["sel"]),
        "authguard": make_xgb(full_cols),
    }


# ---------------------------------------------------------------------------
# G-DET v2 runner
# ---------------------------------------------------------------------------
def run_gdet(sub, y, folds, Xd, Xn, meta, methods, seeds=(SEED,), tag="primary",
             random_split=False, rule_scores=None):
    """Corrected-protocol detection run. Returns (aggregate_dict, per_row_frame, thr_rows).

    rule_scores: dict name -> np.array of scores over `sub` rows (threshold 0.5, no fit).
    """
    X = np.hstack([Xd, Xn]).astype(np.float32)
    groups = sub["family_id"].to_numpy()
    rows, thr_rows = [], []
    fold_metrics = {}

    if random_split:
        kf = KFold(N_OUTER, shuffle=True, random_state=SEED)
        fold_iter = [(np.asarray(tr), np.asarray(te)) for tr, te in kf.split(X)]
    else:
        fold_iter = [(np.flatnonzero(folds != f), np.flatnonzero(folds == f))
                     for f in range(N_OUTER)]

    for name, sc_all in (rule_scores or {}).items():
        fold_metrics[name] = []
        for f, (tr, te) in enumerate(fold_iter):
            m = metrics_full(y[te], sc_all[te], 0.5)
            fold_metrics[name].append(m)
            for k in te:
                rows.append(dict(sid=sub["sid"].iloc[k], family_id=groups[k], fold=f,
                                 y=int(y[k]), model=name, seed=0,
                                 score=float(sc_all[k]), threshold=0.5,
                                 pred=int(sc_all[k] >= 0.5), split="random" if random_split else "family"))

    # blocklist (exact-hash memorization; fixed 0.5 threshold)
    fold_metrics["blocklist"] = []
    for f, (tr, te) in enumerate(fold_iter):
        train_mal = set(sub["bchash"].to_numpy()[tr[y[tr] == 1]])
        sc = np.array([1.0 if h in train_mal else 0.0 for h in sub["bchash"].to_numpy()[te]])
        fold_metrics["blocklist"].append(metrics_full(y[te], sc, 0.5))
        for j, k in enumerate(te):
            rows.append(dict(sid=sub["sid"].iloc[k], family_id=groups[k], fold=f,
                             y=int(y[k]), model="blocklist", seed=0, score=float(sc[j]),
                             threshold=0.5, pred=int(sc[j] >= 0.5),
                             split="random" if random_split else "family"))

    for mname, method in methods.items():
        for seed in seeds:
            key = mname if seed == SEED else f"{mname}@seed{seed}"
            fold_metrics[key] = []
            for f, (tr, te) in enumerate(fold_iter):
                if random_split:
                    # random diagnostic keeps v2 OOF thresholds too (grouped by family within train)
                    thr, splitter, _ = oof_threshold(method, X[tr], y[tr], groups[tr], seed)
                else:
                    thr, splitter, _ = oof_threshold(method, X[tr], y[tr], groups[tr], seed)
                model = method["fit"](X[tr], y[tr], seed)
                s_te = method["score"](model, X[te])
                fold_metrics[key].append(metrics_full(y[te], s_te, thr))
                thr_rows.append(dict(task=tag, model=mname, seed=seed, fold=f,
                                     threshold=thr, splitter=splitter,
                                     split="random" if random_split else "family"))
                for j, k in enumerate(te):
                    rows.append(dict(sid=sub["sid"].iloc[k], family_id=groups[k], fold=f,
                                     y=int(y[k]), model=mname, seed=seed,
                                     score=float(s_te[j]), threshold=thr,
                                     pred=int(s_te[j] >= thr),
                                     split="random" if random_split else "family"))
                print(f"  [{tag}{'/rnd' if random_split else ''}] {key} fold {f}: "
                      f"AUPRC={fold_metrics[key][-1]['AUPRC']:.3f} thr={thr:.3f}", flush=True)

    agg = {}
    for k, fm in fold_metrics.items():
        d = pd.DataFrame(fm)
        agg[k] = {"mean": d.mean().to_dict(), "std": d.std(ddof=0).to_dict(),
                  "folds": d.to_dict(orient="records")}
    return agg, pd.DataFrame(rows), thr_rows


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------
def write_manifest(outdir, config, outputs, started, inputs=None):
    import platform
    import sklearn
    import xgboost
    man = dict(
        command=" ".join(sys.argv),
        config=config,
        seed=SEED,
        started_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
        wall_seconds=round(time.time() - started, 1),
        versions=dict(python=sys.version.split()[0], numpy=np.__version__,
                      pandas=pd.__version__, sklearn=sklearn.__version__,
                      xgboost=xgboost.__version__, platform=platform.platform()),
        inputs={p: sha256_file(p) for p in (inputs or []) if os.path.exists(p)},
        outputs={p: sha256_file(p) for p in outputs if os.path.exists(p)},
    )
    with open(os.path.join(outdir, "manifest.json"), "w") as f:
        json.dump(man, f, indent=2)
    return man


def verify_frozen_or_die():
    rc = subprocess.call([sys.executable, os.path.join(HERE, "frozen.py"), "verify"])
    if rc != 0:
        raise SystemExit("FROZEN ARTIFACT GUARD FAILED — HARD STOP")
