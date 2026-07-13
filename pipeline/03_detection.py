#!/usr/bin/env python3
"""
03_detection.py -- Detection under LEAVE-FAMILY-OUT (Task C).

Primary task : malicious (793) vs benign_cleared (1,657)  [same population, weak negatives]
Secondary    : malicious (793) vs benign_cleared + benign_general (2,457)

Evaluation   : GroupKFold(5) on frozen family_id. Report per-fold values AND mean+/-std.
               Random KFold(5) reported ONLY as a leakage-context comparison.

Methods:
  * usenix_shipped_oracle  -- the shipped USENIX label AS the detector. Tautological on M0
                              (recall=1 by construction); reported to expose the asymmetry.
  * usenix_name_rule       -- bytecode reimpl: fires if a sensitive selector (sweep/drain/...)
                              is present in the dispatch table. The brittle component.
  * usenix_struct_rule     -- bytecode reimpl: fires if an external-call opcode is present.
                              The robust-but-unspecific component (over-approximation).
  * blocklist              -- exact bytecode-hash memorization of TRAIN malicious.
  * opcode_rf              -- RandomForest on opcode histogram only.
  * opcode_xgb             -- Gradient-boosted trees on opcode histogram only.
  * selector_model         -- LogisticReg on selector-set / structural selector signals only.
  * authguard              -- Gradient-boosted trees on full bytecode features (hist+ngram+struct).

Metrics: AUPRC (primary), AUROC, F1, Precision, Recall. Threshold for F1/P/R chosen on the
TRAIN fold only (max-F1 on in-sample train scores); never tuned on test.
"""
import os, sys, json, hashlib, warnings
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold, KFold
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (average_precision_score, roc_auc_score,
                             f1_score, precision_score, recall_score)
warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ag_common import normalize_bytecode, SEED

try:
    from xgboost import XGBClassifier
    HAS_XGB = True
except Exception:
    from sklearn.ensemble import HistGradientBoostingClassifier
    HAS_XGB = False

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
N_SPLITS = 5
np.random.seed(SEED)


def load():
    df = pd.read_csv(os.path.join(ROOT, "capability_dataset.csv"))
    frozen = pd.read_csv(os.path.join(ROOT, "family_assignment_frozen.csv"))
    df["family_id"] = frozen["family_id"].values
    df["bc"] = df["bytecode"].map(normalize_bytecode)
    df["bchash"] = df["bc"].map(lambda b: hashlib.sha256(b.encode()).hexdigest())
    Xd = np.load(os.path.join(RES, "features_dense.npz"))["X"]
    Xn = np.load(os.path.join(RES, "features_ngram.npz"))["X"]
    meta = json.load(open(os.path.join(RES, "feature_meta.json")))
    return df, Xd, Xn, meta


def gb_clf():
    if HAS_XGB:
        return XGBClassifier(n_estimators=300, max_depth=6, learning_rate=0.1,
                             subsample=0.9, colsample_bytree=0.8, eval_metric="logloss",
                             random_state=SEED, n_jobs=4, tree_method="hist")
    return HistGradientBoostingClassifier(max_iter=300, max_depth=6, learning_rate=0.1,
                                          random_state=SEED)


def best_f1_threshold(y_true, scores):
    """Choose threshold maximizing F1 on the given (train) data. Honest: train-only."""
    order = np.argsort(-scores)
    ys = y_true[order]
    tp = np.cumsum(ys)
    fp = np.cumsum(1 - ys)
    P = ys.sum()
    prec = tp / np.maximum(tp + fp, 1)
    rec = tp / max(P, 1)
    f1 = 2 * prec * rec / np.maximum(prec + rec, 1e-9)
    if len(f1) == 0:
        return 0.5
    k = int(np.argmax(f1))
    return float(scores[order][k])


def metrics_at(y_true, scores, thr):
    pred = (scores >= thr).astype(int)
    return dict(
        AUPRC=float(average_precision_score(y_true, scores)) if len(set(y_true)) > 1 else float("nan"),
        AUROC=float(roc_auc_score(y_true, scores)) if len(set(y_true)) > 1 else float("nan"),
        F1=float(f1_score(y_true, pred, zero_division=0)),
        Precision=float(precision_score(y_true, pred, zero_division=0)),
        Recall=float(recall_score(y_true, pred, zero_division=0)),
    )


# ---- rule detectors (produce a score in {0,1}) ----
def score_usenix_shipped(df_test):
    # shipped label == 'malicious' is exactly the rule verdict on the original bytecode
    return (df_test["class"] == "malicious").astype(float).values

def score_usenix_name_rule(Xd_test, meta):
    j = meta["dense_cols"].index("has_sensitive_selector")
    return (Xd_test[:, j] > 0).astype(float)

def score_usenix_struct_rule(Xd_test, meta):
    j = meta["dense_cols"].index("n_call_family")
    return (Xd_test[:, j] > 0).astype(float)


def run_cv(df, Xd, Xn, meta, mask, splitter, group=None, tag=""):
    """Run all methods under one CV scheme on the subset given by `mask`."""
    sub = df[mask].reset_index(drop=True)
    y = (sub["class"] == "malicious").astype(int).values
    Xds = Xd[mask.values]
    Xns = Xn[mask.values]
    Xfull = np.hstack([Xds, Xns])
    grp = sub["family_id"].values if group == "family" else None

    hist_slice = slice(0, meta["hist_dim"])   # opcode histogram columns
    sel_cols = [i for i, c in enumerate(meta["dense_cols"])
                if c.startswith("has_") or c in ("n_selectors", "n_sensitive_selectors",
                                                 "n_call_family", "n_delegatecall")]

    methods = ["usenix_shipped_oracle", "usenix_name_rule", "usenix_struct_rule",
               "blocklist", "opcode_rf", "opcode_xgb", "selector_model", "authguard"]
    fold_metrics = {m: [] for m in methods}

    splits = list(splitter.split(Xds, y, grp)) if grp is not None else list(splitter.split(Xds, y))
    for fold, (tr, te) in enumerate(splits):
        ytr, yte = y[tr], y[te]
        # --- rule detectors (no training) ---
        for name, sc in [
            ("usenix_shipped_oracle", score_usenix_shipped(sub.iloc[te])),
            ("usenix_name_rule", score_usenix_name_rule(Xds[te], meta)),
            ("usenix_struct_rule", score_usenix_struct_rule(Xds[te], meta)),
        ]:
            thr = 0.5  # binary rules
            fold_metrics[name].append(metrics_at(yte, sc, thr))

        # --- blocklist (exact-hash memorization of train malicious) ---
        train_mal_hashes = set(sub.iloc[tr][ytr.astype(bool)]["bchash"])
        bl_scores = sub.iloc[te]["bchash"].map(lambda h: 1.0 if h in train_mal_hashes else 0.0).values
        fold_metrics["blocklist"].append(metrics_at(yte, bl_scores, 0.5))

        # --- learned models ---
        # opcode_rf / opcode_xgb : histogram only
        Xh_tr, Xh_te = Xds[tr][:, hist_slice], Xds[te][:, hist_slice]
        rf = RandomForestClassifier(n_estimators=300, random_state=SEED, n_jobs=4)
        rf.fit(Xh_tr, ytr)
        s_tr = rf.predict_proba(Xh_tr)[:, 1]; s_te = rf.predict_proba(Xh_te)[:, 1]
        thr = best_f1_threshold(ytr, s_tr)
        fold_metrics["opcode_rf"].append(metrics_at(yte, s_te, thr))

        xgb = gb_clf(); xgb.fit(Xh_tr, ytr)
        s_tr = xgb.predict_proba(Xh_tr)[:, 1]; s_te = xgb.predict_proba(Xh_te)[:, 1]
        thr = best_f1_threshold(ytr, s_tr)
        fold_metrics["opcode_xgb"].append(metrics_at(yte, s_te, thr))

        # selector_model : selector/structural selector signals only (standardized logreg)
        Xs_tr, Xs_te = Xds[tr][:, sel_cols], Xds[te][:, sel_cols]
        sc = StandardScaler().fit(Xs_tr)
        lr = LogisticRegression(max_iter=1000, random_state=SEED)
        lr.fit(sc.transform(Xs_tr), ytr)
        s_tr = lr.predict_proba(sc.transform(Xs_tr))[:, 1]; s_te = lr.predict_proba(sc.transform(Xs_te))[:, 1]
        thr = best_f1_threshold(ytr, s_tr)
        fold_metrics["selector_model"].append(metrics_at(yte, s_te, thr))

        # authguard : full bytecode features (hist+struct+ngram), gradient-boosted
        ag = gb_clf(); ag.fit(Xfull[tr], ytr)
        s_tr = ag.predict_proba(Xfull[tr])[:, 1]; s_te = ag.predict_proba(Xfull[te])[:, 1]
        thr = best_f1_threshold(ytr, s_tr)
        fold_metrics["authguard"].append(metrics_at(yte, s_te, thr))

        print(f"  [{tag}] fold {fold}: authguard AUPRC={fold_metrics['authguard'][-1]['AUPRC']:.3f} "
              f"| opcode_xgb={fold_metrics['opcode_xgb'][-1]['AUPRC']:.3f} "
              f"| name_rule R={fold_metrics['usenix_name_rule'][-1]['Recall']:.3f}", flush=True)

    # aggregate
    agg = {}
    for m in methods:
        dfm = pd.DataFrame(fold_metrics[m])
        agg[m] = {"mean": dfm.mean().to_dict(), "std": dfm.std(ddof=0).to_dict(),
                  "folds": dfm.to_dict(orient="records")}
    return agg


def main():
    df, Xd, Xn, meta = load()

    tasks = {
        "primary_mal_vs_cleared": df["class"].isin(["malicious", "benign_cleared"]),
        "secondary_mal_vs_cleared_general": df["class"].isin(["malicious", "benign_cleared", "benign_general"]),
    }

    out = {}
    for tname, mask in tasks.items():
        print(f"\n=== TASK {tname} (n={mask.sum()}) ===", flush=True)
        print("[leave-family-out]", flush=True)
        gkf = GroupKFold(n_splits=N_SPLITS)
        lfo = run_cv(df, Xd, Xn, meta, mask, gkf, group="family", tag=f"{tname}/LFO")
        print("[random-split (leakage context only)]", flush=True)
        kf = KFold(n_splits=N_SPLITS, shuffle=True, random_state=SEED)
        rnd = run_cv(df, Xd, Xn, meta, mask, kf, group=None, tag=f"{tname}/RND")
        out[tname] = {"leave_family_out": lfo, "random_split": rnd}

    with open(os.path.join(RES, "detection_results.json"), "w") as f:
        json.dump(out, f, indent=2)
    print(f"\n[detect] wrote {os.path.join(RES,'detection_results.json')} (xgb={HAS_XGB})", flush=True)


if __name__ == "__main__":
    main()
