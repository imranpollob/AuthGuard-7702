#!/usr/bin/env python3
"""Gate 0A — how much of the USENIX source rule does a cheap emulator recover?

Protocol mirrors revision_v2/experiments/baseline_v2/run_baseline_v2.py:
benchmark v2, PRIMARY_EVALUATION, stored family-disjoint `fold_id`, seeds
7702/7703/7704. Thresholds for recall@5%FPR come from grouped out-of-fold
predictions on the training folds only -- never from test.

Outputs go to revision_v2/results/gate_0a_rule_emulator/.
"""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score, roc_curve
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier, export_text

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from emulator_features import FEATURE_NAMES, extract, featurize  # noqa: E402

RV2 = os.path.abspath(os.path.join(HERE, "..", ".."))
BENCH = os.path.join(RV2, "data", "authguardbench_7702_v2.csv.gz")
SEQ_PREDS = os.path.join(RV2, "experiments", "baseline_v2", "baseline_predictions.csv.gz")
OUT = os.path.join(RV2, "results", "gate_0a_rule_emulator")
SEEDS = [7702, 7703, 7704]
NBOOT = 2000
TARGET_FPR = 0.05

SINGLE_RULE = "fallback_reaches_external_call_over"


def recall_at_fpr(y, s, target=TARGET_FPR):
    """Recall at the operating point whose FPR is closest to (but <=) target."""
    fpr, tpr, thr = roc_curve(y, s)
    ok = np.flatnonzero(fpr <= target)
    if len(ok) == 0:
        return 0.0, 1.0, 0.0
    k = ok[-1]
    return float(tpr[k]), float(fpr[k]), float(thr[k])


def apply_threshold(y, s, thr):
    pred = s >= thr
    tp = int(((pred == 1) & (y == 1)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    tn = int(((pred == 0) & (y == 0)).sum())
    return {
        "recall": tp / max(tp + fn, 1),
        "fpr": fp / max(fp + tn, 1),
        "precision": tp / max(tp + fp, 1),
    }


def make_models(seed):
    return {
        "decision_tree_d4": DecisionTreeClassifier(
            max_depth=4, random_state=seed, class_weight="balanced"
        ),
        "logreg_l2": make_pipeline(
            StandardScaler(),
            LogisticRegression(
                penalty="l2", C=1.0, max_iter=5000, random_state=seed,
                class_weight="balanced",
            ),
        ),
    }


def oof_threshold(model_factory, X_tr, y_tr, g_tr, seed):
    """Threshold hitting TARGET_FPR on grouped OOF predictions of the training folds."""
    n_splits = min(5, len(np.unique(g_tr[y_tr == 1])), len(np.unique(g_tr[y_tr == 0])))
    if n_splits < 2:
        return 0.5
    sgkf = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    oof = np.zeros(len(y_tr), dtype=float)
    for tr, va in sgkf.split(X_tr, y_tr, groups=g_tr):
        m = model_factory()
        m.fit(X_tr[tr], y_tr[tr])
        oof[va] = m.predict_proba(X_tr[va])[:, 1]
    _, _, thr = recall_at_fpr(y_tr, oof)
    return thr


def main():
    os.makedirs(OUT, exist_ok=True)
    df = pd.read_csv(BENCH)
    p = df[df.population == "PRIMARY_EVALUATION"].reset_index(drop=True)
    y = p.label.to_numpy(dtype=int)
    folds = p.fold_id.to_numpy(dtype=int)
    fam = p.family_id.to_numpy()
    sid = p.sample_id.to_numpy()

    # ---- features + featurization latency ----
    t0 = time.perf_counter()
    X = featurize(p.runtime_bytecode.tolist())
    feat_wall = time.perf_counter() - t0
    per_contract_ms = []
    for bc in p.runtime_bytecode.sample(300, random_state=7702):
        t = time.perf_counter()
        extract(bc)
        per_contract_ms.append((time.perf_counter() - t) * 1e3)
    per_contract_ms = np.array(per_contract_ms)

    rows, fold_rows = [], []
    per_row_scores = []

    for seed in SEEDS:
        for name in list(make_models(seed).keys()) + [SINGLE_RULE]:
            scores = np.zeros(len(y), dtype=float)
            thr_by_fold = {}
            for f in sorted(np.unique(folds)):
                tr = np.flatnonzero(folds != f)
                te = np.flatnonzero(folds == f)
                if name == SINGLE_RULE:
                    col = FEATURE_NAMES.index(SINGLE_RULE)
                    scores[te] = X[te, col]
                    thr_by_fold[int(f)] = 0.5
                else:
                    factory = lambda: make_models(seed)[name]  # noqa: E731
                    m = factory()
                    m.fit(X[tr], y[tr])
                    scores[te] = m.predict_proba(X[te])[:, 1]
                    thr_by_fold[int(f)] = oof_threshold(factory, X[tr], y[tr], fam[tr], seed)

                fm = apply_threshold(y[te], scores[te], thr_by_fold[int(f)])
                fold_rows.append(dict(
                    seed=seed, model=name, fold=int(f), n=len(te), n_pos=int(y[te].sum()),
                    prevalence=float(y[te].mean()),
                    auprc=float(average_precision_score(y[te], scores[te])),
                    auroc=float(roc_auc_score(y[te], scores[te])),
                    **{f"thr_{k}": v for k, v in fm.items()},
                ))

            # Primary aggregation MUST match run_baseline_v2.py: mean of per-fold
            # metrics, then mean over seeds. Pooled is reported alongside, not instead.
            sel = [r for r in fold_rows if r["seed"] == seed and r["model"] == name]
            pooled_thr = float(np.mean(list(thr_by_fold.values())))
            pm = apply_threshold(y, scores, pooled_thr)
            r5, f5, _ = recall_at_fpr(y, scores)
            rows.append(dict(
                seed=seed, model=name,
                auprc_macro=float(np.mean([r["auprc"] for r in sel])),
                auroc_macro=float(np.mean([r["auroc"] for r in sel])),
                auprc_pooled=float(average_precision_score(y, scores)),
                auroc_pooled=float(roc_auc_score(y, scores)),
                recall_at_5fpr_curve=r5, fpr_at_that_point=f5,
                recall_oof_thr=pm["recall"], fpr_oof_thr=pm["fpr"],
                precision_oof_thr=pm["precision"],
            ))
            for i in range(len(y)):
                per_row_scores.append(dict(
                    sample_id=sid[i], family_id=fam[i], fold=int(folds[i]), seed=seed,
                    model=name, true_label=int(y[i]), score=float(scores[i]),
                ))

    summary = pd.DataFrame(rows)
    per_fold = pd.DataFrame(fold_rows)
    preds = pd.DataFrame(per_row_scores)
    summary.to_csv(os.path.join(OUT, "gate_0a_summary.csv"), index=False)
    per_fold.to_csv(os.path.join(OUT, "gate_0a_per_fold.csv"), index=False)
    preds.to_csv(os.path.join(OUT, "gate_0a_predictions.csv.gz"), index=False)

    # ---- paired family-clustered bootstrap vs AuthGuard-Seq ----
    seq = pd.read_csv(SEQ_PREDS)
    seq = seq[seq.model == "authguard_seq"][["sample_id", "seed", "calibrated_score", "true_label", "family_id"]]
    boot = {}
    rng = np.random.default_rng(7702)
    fams = np.unique(fam)
    fam_idx = {f: i for i, f in enumerate(fams)}
    obs_fam = np.array([fam_idx[f] for f in fam])

    def macro_auprc(y_all, s_all, folds_all, w):
        """Mean of per-fold weighted AUPRC -- the baseline_v2 aggregation."""
        vals = []
        for f in np.unique(folds_all):
            m = folds_all == f
            if w[m].sum() == 0 or len(np.unique(y_all[m][w[m] > 0])) < 2:
                continue
            vals.append(average_precision_score(y_all[m], s_all[m], sample_weight=w[m]))
        return float(np.mean(vals)) if vals else np.nan

    for name in ["decision_tree_d4", "logreg_l2", SINGLE_RULE]:
        deltas = []
        for seed in SEEDS:
            e = preds[(preds.model == name) & (preds.seed == seed)][["sample_id", "score"]]
            s = seq[seq.seed == seed][["sample_id", "calibrated_score"]]
            merged = p[["sample_id"]].merge(e, on="sample_id").merge(s, on="sample_id")
            assert len(merged) == len(p), f"{name} seed {seed}: {len(merged)} != {len(p)}"
            es, ss = merged.score.to_numpy(), merged.calibrated_score.to_numpy()
            for _ in range(NBOOT // len(SEEDS)):
                w = rng.multinomial(len(fams), np.ones(len(fams)) / len(fams))[obs_fam]
                a = macro_auprc(y, es, folds, w)
                b = macro_auprc(y, ss, folds, w)
                if np.isnan(a) or np.isnan(b):
                    continue
                deltas.append(a - b)
        deltas = np.array(deltas)
        boot[name] = dict(
            mean_delta_auprc=float(deltas.mean()),
            ci95=[float(np.percentile(deltas, 2.5)), float(np.percentile(deltas, 97.5))],
            replicates=int(len(deltas)),
            excludes_zero=bool(np.percentile(deltas, 2.5) > 0 or np.percentile(deltas, 97.5) < 0),
        )

    # ---- printed trees (one per fold, seed 7702) ----
    trees = {}
    for f in sorted(np.unique(folds)):
        tr = np.flatnonzero(folds != f)
        m = DecisionTreeClassifier(max_depth=4, random_state=7702, class_weight="balanced")
        m.fit(X[tr], y[tr])
        trees[f"fold_{f}"] = export_text(m, feature_names=list(FEATURE_NAMES), decimals=3)

    # ---- error profile vs AuthGuard-Seq, by family ----
    emu = preds[(preds.model == "decision_tree_d4") & (preds.seed == 7702)][["sample_id", "score"]]
    sq = seq[seq.seed == 7702][["sample_id", "calibrated_score"]]
    cmp_df = p[["sample_id", "family_id", "label", "family_size"]].merge(emu, on="sample_id").merge(sq, on="sample_id")
    
    # rank-based comparison avoids threshold coupling
    cmp_df["emu_rank"] = cmp_df.score.rank(pct=True)
    cmp_df["seq_rank"] = cmp_df.calibrated_score.rank(pct=True)
    cmp_df["seq_better"] = np.where(
        cmp_df.label == 1, cmp_df.seq_rank - cmp_df.emu_rank, cmp_df.emu_rank - cmp_df.seq_rank
    )
    fam_gap = (cmp_df.groupby("family_id")
               .agg(n=("sample_id", "size"), pos=("label", "sum"), seq_advantage=("seq_better", "mean"))
               .sort_values("seq_advantage", ascending=False))
    fam_gap.to_csv(os.path.join(OUT, "gate_0a_family_error_profile.csv"))

    latency = dict(
        featurize_all_wall_seconds=float(feat_wall),
        n_contracts=int(len(p)),
        per_contract_ms_median=float(np.median(per_contract_ms)),
        per_contract_ms_mean=float(per_contract_ms.mean()),
        per_contract_ms_p95=float(np.percentile(per_contract_ms, 95)),
        note="pure-Python linear sweep + CFG; not an optimised implementation",
    )

    out = dict(
        seeds=SEEDS, n_rows=int(len(p)), n_families=int(len(fams)),
        features=list(FEATURE_NAMES),
        aggregation="macro over folds then over seeds (matches run_baseline_v2.py)",
        seed_means={
            m: dict(
                auprc_macro_mean=float(summary[summary.model == m].auprc_macro.mean()),
                auprc_macro_sd=float(summary[summary.model == m].auprc_macro.std(ddof=1)),
                auroc_macro_mean=float(summary[summary.model == m].auroc_macro.mean()),
                auprc_pooled_mean=float(summary[summary.model == m].auprc_pooled.mean()),
                recall5_mean=float(summary[summary.model == m].recall_at_5fpr_curve.mean()),
                recall_oof_thr_mean=float(summary[summary.model == m].recall_oof_thr.mean()),
                fpr_oof_thr_mean=float(summary[summary.model == m].fpr_oof_thr.mean()),
            )
            for m in summary.model.unique()
        },
        paired_bootstrap_vs_authguard_seq=boot,
        latency=latency,
        trees=trees,
        top_families_seq_advantage=fam_gap.head(15).reset_index().to_dict("records"),
    )
    with open(os.path.join(OUT, "gate_0a_results.json"), "w") as fh:
        json.dump(out, fh, indent=2)

    print(json.dumps({k: v for k, v in out.items() if k != "trees"}, indent=2)[:4000])
    print("\n=== DECISION TREE (fold 0, seed 7702) ===")
    print(trees["fold_0"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
