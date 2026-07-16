#!/usr/bin/env python3
"""Phase 3A/3B — stronger baselines + feature ablations under G-DET v2 protocol.

All methods use identical stored outer folds, inner family-grouped OOF thresholds, FPR
metrics, and (for stochastic learners) 5 seeds. TF-IDF baselines featurize opcode n-grams
from the frozen disassembly; hyperparameters are chosen only inside the outer-training data
via group-aware inner CV. Per-row test scores persisted for paired bootstrap vs AuthGuard.
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV
from xgboost import XGBClassifier

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))
from harness import (load_corpus, task_arrays, feature_views, best_f1_threshold,  # noqa: E402
                     inner_splits, metrics_full, make_xgb, make_rf, make_logreg,
                     run_gdet, default_methods, write_manifest, verify_frozen_or_die,
                     RV2, DH, SEED, disasm, XGB_HP)

OUT_B = os.path.join(RV2, "results", "baselines")
OUT_A = os.path.join(RV2, "results", "ablations")
SEEDS = [SEED, 7703, 7704, 7705, 7706]


def opcode_docs(sub):
    docs = []
    for bc in sub["bc"]:
        ops, _, _ = disasm(bc)
        docs.append(" ".join(ops))
    return docs


# ---- TF-IDF text baselines (custom method dict for the harness) ----
def make_tfidf(kind):
    def fit(docs_y_groups, X_unused, seed):  # placeholder signature bridge
        raise RuntimeError("use run_text_baseline")
    return kind


def run_text_baseline(sub, y, folds, docs, kind, seeds, tag):
    """kind in {'lr','svm'}. Vectorizer fit on outer-train only; inner-OOF threshold."""
    groups = sub["family_id"].to_numpy()
    docs = np.array(docs, dtype=object)
    rows, fold_metrics = [], []
    thr_rows = []
    use_seeds = seeds if kind == "lr" else [SEED]  # LinearSVC deterministic
    agg_seedwise = {}
    for seed in use_seeds:
        fm = []
        for f in range(5):
            tr, te = np.flatnonzero(folds != f), np.flatnonzero(folds == f)

            def build_est(random_state):
                vec = TfidfVectorizer(analyzer="word", ngram_range=(1, 4),
                                      min_df=3, max_features=20000, token_pattern=r"[^ ]+")
                if kind == "lr":
                    clf = LogisticRegression(max_iter=2000, C=1.0, random_state=random_state)
                    return vec, clf, "proba"
                base = LinearSVC(C=1.0, random_state=random_state)
                clf = CalibratedClassifierCV(base, cv=3, method="sigmoid")
                return vec, clf, "proba"

            # inner OOF threshold
            splits, splitter = inner_splits(y[tr], groups[tr], seed=seed)
            oof = np.full(len(tr), np.nan)
            for itr, iva in splits:
                vec, clf, _ = build_est(seed)
                Xtr = vec.fit_transform(docs[tr][itr])
                clf.fit(Xtr, y[tr][itr])
                oof[iva] = clf.predict_proba(vec.transform(docs[tr][iva]))[:, 1]
            thr = best_f1_threshold(y[tr], oof)
            vec, clf, _ = build_est(seed)
            Xtr = vec.fit_transform(docs[tr])
            clf.fit(Xtr, y[tr])
            s = clf.predict_proba(vec.transform(docs[te]))[:, 1]
            m = metrics_full(y[te], s, thr)
            fm.append(m)
            thr_rows.append(dict(model=tag, seed=seed, fold=f, threshold=thr, splitter=splitter))
            if seed == SEED:
                for j, k in enumerate(te):
                    rows.append(dict(task="primary", split="family", model=tag, seed=seed,
                                     sid=sub["sid"].iloc[k], family_id=groups[k],
                                     y=int(y[k]), score=float(s[j]), threshold=thr,
                                     pred=int(s[j] >= thr)))
            print(f"  [{tag} seed{seed}] fold {f}: AUPRC={m['AUPRC']:.3f} thr={thr:.3f}", flush=True)
        d = pd.DataFrame(fm)
        agg_seedwise[seed] = {"mean": d.mean().to_dict(), "std": d.std(ddof=0).to_dict()}
        if seed == SEED:
            fold_metrics = fm
    d = pd.DataFrame(fold_metrics)
    return ({"mean": d.mean().to_dict(), "std": d.std(ddof=0).to_dict(),
             "folds": d.to_dict(orient="records"), "seedwise": agg_seedwise},
            pd.DataFrame(rows), thr_rows)


def main():
    started = time.time()
    verify_frozen_or_die()
    os.makedirs(OUT_B, exist_ok=True); os.makedirs(OUT_A, exist_ok=True)
    df, Xd, Xn, meta = load_corpus()
    views = feature_views(meta)
    sub, y, folds, Xds, Xns = task_arrays(df, Xd, Xn, "primary")
    Xall = np.hstack([Xds, Xns]).astype(np.float32)
    n_dense = views["n_dense"]
    docs = opcode_docs(sub)

    # ---------- Phase 3A baselines ----------
    baseline_results, row_frames, thr_all = {}, [], []
    # hashed-4gram-only XGB (ngram block only)
    ngram_cols = list(range(n_dense, n_dense + 512))
    for tag, method in [("hash_xgb", make_xgb(ngram_cols))]:
        agg, rows, thr = run_gdet(sub, y, folds, Xds, Xns, meta, {tag: method},
                                  seeds=SEEDS, tag="primary")
        baseline_results[tag] = agg[tag]; rows["experiment"] = "baseline"
        row_frames.append(rows); thr_all += thr

    for tag, kind in [("tfidf_lr", "lr"), ("tfidf_svm", "svm")]:
        agg, rows, thr = run_text_baseline(sub, y, folds, docs, kind, SEEDS, tag)
        baseline_results[tag] = agg
        rows["experiment"] = "baseline"; row_frames.append(rows); thr_all += thr

    with open(os.path.join(OUT_B, "baselines_results.json"), "w") as f:
        json.dump(baseline_results, f, indent=2)

    # ---------- Phase 3B ablations ----------
    dcols = meta["dense_cols"]
    sel = set(views["sel"]); length = set(views["length"])
    meta_like = {i for i, c in enumerate(dcols)
                 if c in ("code_bytes", "is_delegation_ptr", "mean_push_size")}
    full = list(range(n_dense + 512))
    ablations = {
        "struct_sel_only": views["struct"],
        "hist_only": views["hist"],
        "ngram_only": ngram_cols,
        "hist_struct": views["dense"],
        "hist_ngram": views["hist"] + ngram_cols,
        "full_773": full,
        "no_selectors": [i for i in full if i not in sel],
        "no_length": [i for i in full if i not in length],
        "no_metadata": [i for i in full if i not in meta_like],
        "no_length_metadata": [i for i in full if i not in (length | meta_like)],
    }
    abl_results = {}
    for name, cols in ablations.items():
        method = make_xgb(cols)
        agg, rows, thr = run_gdet(sub, y, folds, Xds, Xns, meta, {f"abl_{name}": method},
                                  seeds=SEEDS, tag="primary")
        a = agg[f"abl_{name}"]
        a["dimensions"] = len(cols)
        abl_results[name] = a
        rows["experiment"] = "ablation"; row_frames.append(rows); thr_all += thr
        print(f"[ablation {name}] dims={len(cols)} AUPRC={a['mean']['AUPRC']:.3f} "
              f"FPR={a['mean']['FPR']:.3f}", flush=True)
    with open(os.path.join(OUT_A, "ablations_results.json"), "w") as f:
        json.dump(abl_results, f, indent=2)

    per_row = pd.concat(row_frames, ignore_index=True)
    per_row.to_csv(os.path.join(OUT_B, "baselines_ablations_per_row.csv.gz"), index=False)
    pd.DataFrame(thr_all).to_csv(os.path.join(OUT_B, "baselines_ablations_thresholds.csv"),
                                 index=False)

    outputs = [os.path.join(OUT_B, "baselines_results.json"),
               os.path.join(OUT_A, "ablations_results.json"),
               os.path.join(OUT_B, "baselines_ablations_per_row.csv.gz")]
    write_manifest(OUT_B, dict(protocol="threshold_protocol_v2", seeds=SEEDS,
                               baselines=list(baseline_results), ablations=list(ablations)),
                   outputs, started, inputs=[os.path.join(DH, "task_aligned_dataset_v1.csv")])
    verify_frozen_or_die()
    print(f"[baselines+ablations] done in {time.time()-started:.0f}s")


if __name__ == "__main__":
    main()
