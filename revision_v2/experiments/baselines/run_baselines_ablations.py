#!/usr/bin/env python3
"""Phase 3A/3B — stronger baselines + feature ablations under G-DET v2 protocol.

All methods use identical stored outer folds, inner family-grouped OOF thresholds, FPR
metrics, and (for stochastic learners) 5 seeds. TF-IDF baselines featurize opcode n-grams
from the frozen disassembly; hyperparameters are chosen only inside the outer-training data
via group-aware inner CV. Per-row test scores persisted for paired bootstrap vs AuthGuard.
"""
import hashlib
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
from sklearn.model_selection import GroupKFold
from xgboost import XGBClassifier

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))
sys.path.insert(0, os.path.join(HERE, "..", "gateA"))
sys.path.insert(0, os.path.join(HERE, "..", "donor_pools"))
from harness import (load_corpus, task_arrays, feature_views, best_f1_threshold,  # noqa: E402
                     inner_splits, metrics_full, make_xgb, make_rf, make_logreg,
                     run_gdet, default_methods, write_manifest, verify_frozen_or_die,
                     RV2, ROOT, DH, SEED, disasm, featurize, SENS, oof_threshold,
                     XGB_HP)
from run_gateA import first_stop_region  # noqa: E402
from pools import mut  # noqa: E402

OUT_B = os.path.join(RV2, "results", "baselines")
OUT_A = os.path.join(RV2, "results", "ablations")
OUT_FS = os.path.join(RV2, "results", "first_stop")
SEEDS = [SEED, 7703, 7704, 7705, 7706]
NBOOT = 10_000


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

            def build_est(random_state, C):
                vec = TfidfVectorizer(analyzer="word", ngram_range=(1, 4),
                                      min_df=3, max_features=20000, token_pattern=r"[^ ]+")
                if kind == "lr":
                    clf = LogisticRegression(max_iter=2000, C=C, random_state=random_state)
                    return vec, clf, "proba"
                base = LinearSVC(C=C, random_state=random_state)
                clf = CalibratedClassifierCV(base, cv=3, method="sigmoid")
                return vec, clf, "proba"

            # Training-only group-aware model selection. The selected candidate's family-OOF
            # scores are also the threshold-selection scores required by protocol v2.
            splits, splitter = inner_splits(y[tr], groups[tr], seed=seed)
            candidates = {}
            for C in [0.1, 1.0, 10.0]:
                oof_c = np.full(len(tr), np.nan)
                for itr, iva in splits:
                    vec, clf, _ = build_est(seed, C)
                    Xtr = vec.fit_transform(docs[tr][itr])
                    clf.fit(Xtr, y[tr][itr])
                    oof_c[iva] = clf.predict_proba(vec.transform(docs[tr][iva]))[:, 1]
                candidates[C] = (float(average_precision_score(y[tr], oof_c)), oof_c)
            selected_C = max(candidates, key=lambda C: (candidates[C][0], -C))
            oof = candidates[selected_C][1]
            thr = best_f1_threshold(y[tr], oof)
            vec, clf, _ = build_est(seed, selected_C)
            Xtr = vec.fit_transform(docs[tr])
            clf.fit(Xtr, y[tr])
            s = clf.predict_proba(vec.transform(docs[te]))[:, 1]
            m = metrics_full(y[te], s, thr)
            fm.append(m)
            thr_rows.append(dict(model=tag, seed=seed, fold=f, threshold=thr,
                                 splitter=splitter, selected_C=selected_C,
                                 inner_selection_AUPRC=candidates[selected_C][0]))
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


def with_seedwise(agg, name):
    """Retain the primary-seed summary and expose all approved stochastic seeds."""
    out = dict(agg[name])
    out["seedwise"] = {
        str(seed): agg[name if seed == SEED else f"{name}@seed{seed}"]
        for seed in SEEDS
    }
    return out


def first_stop_offset_and_exec_len(bc):
    """Mirror Gate A's PUSH-aware, pre-metadata first-STOP scan for diagnostics."""
    b = mut.to_bytes(bc)
    ms = mut.find_metadata_split(b)
    i = 0
    while i < ms:
        op = b[i]
        if 0x60 <= op <= 0x7f:
            i += 1 + (op - 0x60 + 1)
            continue
        if op == 0x00:
            return i, ms
        i += 1
    return None, ms


def build_first_stop_views(sub, meta):
    """Exact Gate-A first-STOP features plus auditable degenerate-case metadata."""
    regions = [first_stop_region(bc) for bc in sub["bc"]]
    Xd, Xn, _ = featurize(regions, sens=SENS)
    X = np.hstack([Xd, Xn]).astype(np.float32)
    records = []
    for i, bc in enumerate(sub["bc"]):
        stop_offset, exec_len = first_stop_offset_and_exec_len(bc)
        region_len = len(regions[i]) // 2
        records.append(dict(
            sid=sub["sid"].iloc[i], family_id=sub["family_id"].iloc[i],
            class_name=sub["class"].iloc[i], y=int(sub["class"].iloc[i] == "malicious"),
            exec_bytes=int(exec_len), first_stop_offset=(None if stop_offset is None
                                                        else int(stop_offset)),
            region_bytes=int(region_len), near_empty=bool(region_len < 20),
            whole_body=bool(region_len == exec_len), no_stop=bool(stop_offset is None),
            stop_at_final_byte=bool(stop_offset is not None and stop_offset + 1 == exec_len),
            feature_nnz=int(np.count_nonzero(X[i])),
            feature_l1=float(np.abs(X[i]).sum()),
            features_finite=bool(np.isfinite(X[i]).all())))
    return Xd, Xn, X, pd.DataFrame(records)


def family_columns(sub):
    """Attach the frozen 0.75/0.85/0.90 family assignments exactly as Phase 3C."""
    cap = pd.read_csv(os.path.join(ROOT, "capability_dataset.csv"))
    fam = pd.read_csv(os.path.join(ROOT, "family_assignment_frozen.csv"))
    cap["_key"] = cap["chain"].astype(str) + ":" + cap["address"].astype(str)
    out = {
        "0.75": sub["sid"].map(dict(zip(cap["_key"], fam["family_id_075"]))).to_numpy(),
        "0.85": sub["family_id"].to_numpy(),
        "0.90": sub["sid"].map(dict(zip(cap["_key"], fam["family_id_090"]))).to_numpy(),
    }
    assert all(pd.notna(v).all() for v in out.values()), "missing frozen family assignment"
    return out


def evaluate_grouping(X, y, groups, method):
    """Phase-3C-compatible family sensitivity, with paired per-row scores retained."""
    folds = np.full(len(y), -1, dtype=int)
    for f, (_, te) in enumerate(GroupKFold(5).split(X, y, groups)):
        folds[te] = f
    metrics, rows = [], []
    for f in range(5):
        tr, te = np.flatnonzero(folds != f), np.flatnonzero(folds == f)
        thr, splitter, _ = oof_threshold(method, X[tr], y[tr], groups[tr], SEED)
        model = method["fit"](X[tr], y[tr], SEED)
        scores = method["score"](model, X[te])
        metrics.append(metrics_full(y[te], scores, thr))
        for j, k in enumerate(te):
            rows.append(dict(row_index=int(k), fold=f, y=int(y[k]), family_id=groups[k],
                             score=float(scores[j]), threshold=thr, splitter=splitter))
    d = pd.DataFrame(metrics)
    return ({"mean": d.mean(numeric_only=True).to_dict(),
             "std": d.std(numeric_only=True, ddof=0).to_dict(),
             "folds": d.to_dict(orient="records")}, pd.DataFrame(rows))


def paired_family_bootstrap(y, score_a, score_b, families, name):
    """Frozen uncertainty protocol: resample families, retain all member rows."""
    unique = np.array(sorted(pd.unique(families)))
    index = {fam: i for i, fam in enumerate(unique)}
    obs_family = np.array([index[f] for f in families])
    seed = int.from_bytes(hashlib.blake2b(f"{SEED}:{name}".encode(), digest_size=8).digest(),
                          "little")
    rng = np.random.default_rng(seed)
    deltas = np.empty(NBOOT)
    for b in range(NBOOT):
        counts = np.bincount(rng.integers(0, len(unique), len(unique)), minlength=len(unique))
        weights = counts[obs_family]
        deltas[b] = (average_precision_score(y, score_a, sample_weight=weights) -
                     average_precision_score(y, score_b, sample_weight=weights))
    ci = [float(np.percentile(deltas, 2.5)), float(np.percentile(deltas, 97.5))]
    return dict(delta_point=float(average_precision_score(y, score_a) -
                                  average_precision_score(y, score_b)),
                delta_CI95=ci, excludes_zero=bool(ci[0] > 0 or ci[1] < 0),
                boot_mean=float(deltas.mean()), boot_std=float(deltas.std()),
                replicates=NBOOT)


def degenerate_score_diagnostics(cases, scores):
    d = cases.copy()
    d["oof_score_first_stop_full"] = scores
    diagnostics = {}
    masks = {
        "all": np.ones(len(d), dtype=bool),
        "excluding_near_empty": ~d["near_empty"].to_numpy(),
        "excluding_whole_body": ~d["whole_body"].to_numpy(),
        "interior_stop_and_non_tiny": (~d["whole_body"] & ~d["near_empty"]).to_numpy(),
    }
    for name, mask in masks.items():
        yy = d.loc[mask, "y"].to_numpy()
        ss = d.loc[mask, "oof_score_first_stop_full"].to_numpy()
        diagnostics[name] = dict(n=int(mask.sum()), positives=int(yy.sum()),
                                 negatives=int(len(yy) - yy.sum()),
                                 pooled_AUPRC=(float(average_precision_score(yy, ss))
                                               if len(np.unique(yy)) == 2 else None))
    return d, diagnostics


def main():
    started = time.time()
    verify_frozen_or_die()
    os.makedirs(OUT_B, exist_ok=True); os.makedirs(OUT_A, exist_ok=True)
    os.makedirs(OUT_FS, exist_ok=True)
    df, Xd, Xn, meta = load_corpus()
    views = feature_views(meta)
    sub, y, folds, Xds, Xns = task_arrays(df, Xd, Xn, "primary")
    Xall = np.hstack([Xds, Xns]).astype(np.float32)
    n_dense = views["n_dense"]
    docs = opcode_docs(sub)
    fs_d, fs_n, fs_all, fs_cases = build_first_stop_views(sub, meta)

    # ---------- Phase 3A baselines ----------
    baseline_results, row_frames, thr_all = {}, [], []
    # hashed-4gram-only XGB (ngram block only)
    ngram_cols = list(range(n_dense, n_dense + 512))
    for tag, method in [("hash_xgb", make_xgb(ngram_cols))]:
        agg, rows, thr = run_gdet(sub, y, folds, Xds, Xns, meta, {tag: method},
                                  seeds=SEEDS, tag="primary")
        baseline_results[tag] = with_seedwise(agg, tag); rows["experiment"] = "baseline"
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
        a = with_seedwise(agg, f"abl_{name}")
        a["dimensions"] = len(cols)
        abl_results[name] = a
        rows["experiment"] = "ablation"; row_frames.append(rows); thr_all += thr
        print(f"[ablation {name}] dims={len(cols)} AUPRC={a['mean']['AUPRC']:.3f} "
              f"FPR={a['mean']['FPR']:.3f}", flush=True)
    with open(os.path.join(OUT_A, "ablations_results.json"), "w") as f:
        json.dump(abl_results, f, indent=2)

    # ---------- Critical Gate-A follow-up: first-STOP shortcut investigation ----------
    # The same column removals are applied to features recomputed on the first-STOP prefix.
    fs_columns = {
        "first_stop_full_773": full,
        "first_stop_no_length": [i for i in full if i not in length],
        "first_stop_no_length_metadata": [i for i in full if i not in (length | meta_like)],
    }
    fs_primary, fs_rows_all = {}, []
    for name, cols in fs_columns.items():
        method = make_xgb(cols)
        agg, rows, thr = run_gdet(sub, y, folds, fs_d, fs_n, meta, {name: method},
                                  seeds=SEEDS, tag="first_stop_primary")
        entry = with_seedwise(agg, name)
        entry["dimensions"] = len(cols)
        fs_primary[name] = entry
        rows = rows[(rows["model"] == name)].copy()
        rows["experiment"] = "first_stop"
        fs_rows_all.append(rows); row_frames.append(rows); thr_all += thr
        print(f"[first-STOP {name}] dims={len(cols)} "
              f"AUPRC={entry['mean']['AUPRC']:.3f}", flush=True)

    # Family-threshold sensitivity uses the same GroupKFold construction as Phase 3C.
    grouping_results = {}
    family_maps = family_columns(sub)
    rep_specs = {
        "authguard_full_773": (Xall, full),
        **{name: (fs_all, cols) for name, cols in fs_columns.items()},
    }
    for fam_threshold, groups in family_maps.items():
        grouping_results[fam_threshold] = {}
        for name, (matrix, cols) in rep_specs.items():
            summary, _ = evaluate_grouping(matrix, y, groups, make_xgb(cols))
            summary["dimensions"] = len(cols)
            grouping_results[fam_threshold][name] = summary
            print(f"[first-STOP family {fam_threshold} {name}] "
                  f"AUPRC={summary['mean']['AUPRC']:.3f}", flush=True)

    # Paired family-clustered bootstrap on the primary stored folds, all refit on this host.
    primary_rows = pd.concat(row_frames, ignore_index=True)
    def primary_scores(model):
        q = primary_rows[(primary_rows["model"] == model) &
                         (primary_rows["seed"] == SEED) &
                         (primary_rows["split"] == "family")].drop_duplicates("sid")
        return q.set_index("sid").loc[sub["sid"], "score"].to_numpy()

    score_authguard = primary_scores("abl_full_773")
    bootstrap = {}
    for name in fs_columns:
        score_fs = primary_scores(name)
        bootstrap[f"{name}_minus_authguard_full_773"] = paired_family_bootstrap(
            y, score_fs, score_authguard, sub["family_id"].to_numpy(),
            f"first_stop:{name}:minus_authguard")

    # Tiny/whole-prefix cases are retained, but their prevalence, feature behavior, and
    # post-hoc score sensitivity are made explicit rather than silently driving the result.
    score_fs_full = primary_scores("first_stop_full_773")
    fs_cases_scored, degenerate_sensitivity = degenerate_score_diagnostics(fs_cases,
                                                                           score_fs_full)
    class_summary = {}
    for cls, d in fs_cases_scored.groupby("class_name"):
        class_summary[cls] = dict(
            n=int(len(d)), region_bytes_median=float(d["region_bytes"].median()),
            region_bytes_min=int(d["region_bytes"].min()),
            region_bytes_max=int(d["region_bytes"].max()),
            near_empty_n=int(d["near_empty"].sum()),
            whole_body_n=int(d["whole_body"].sum()),
            no_stop_n=int(d["no_stop"].sum()),
            stop_at_final_byte_n=int(d["stop_at_final_byte"].sum()),
            nonfinite_feature_rows=int((~d["features_finite"]).sum()),
            zero_feature_rows=int((d["feature_nnz"] == 0).sum()))

    fs_payload = dict(
        representation_definition="773 features recomputed on the PUSH-aware pre-metadata "
                                  "prefix through the first linear-sweep STOP; whole "
                                  "pre-metadata body when no STOP exists",
        ablation_columns={name: [dcols[i] if i < n_dense else f"ngram_{i-n_dense}"
                                 for i in cols] for name, cols in fs_columns.items()},
        primary_stored_folds=fs_primary,
        family_threshold_sensitivity=grouping_results,
        paired_family_clustered_bootstrap=bootstrap,
        degenerate_cases=dict(class_summary=class_summary,
                              score_sensitivity=degenerate_sensitivity,
                              near_empty_definition="first-STOP region <20 bytes",
                              whole_body_definition="region length equals pre-metadata length",
                              note="Exclusion AUPRCs are post-hoc score diagnostics, not "
                                   "replacement primary estimates; models were not refit."))
    with open(os.path.join(OUT_FS, "first_stop_results.json"), "w") as f:
        json.dump(fs_payload, f, indent=2)
    pd.concat(fs_rows_all, ignore_index=True).to_csv(
        os.path.join(OUT_FS, "first_stop_per_row.csv.gz"), index=False)
    fs_cases_scored.to_csv(os.path.join(OUT_FS, "first_stop_degenerate_cases.csv"), index=False)

    per_row = pd.concat(row_frames, ignore_index=True)
    per_row.to_csv(os.path.join(OUT_B, "baselines_ablations_per_row.csv.gz"), index=False)
    pd.DataFrame(thr_all).to_csv(os.path.join(OUT_B, "baselines_ablations_thresholds.csv"),
                                 index=False)

    outputs = [os.path.join(OUT_B, "baselines_results.json"),
               os.path.join(OUT_A, "ablations_results.json"),
               os.path.join(OUT_B, "baselines_ablations_per_row.csv.gz"),
               os.path.join(OUT_FS, "first_stop_results.json"),
               os.path.join(OUT_FS, "first_stop_per_row.csv.gz"),
               os.path.join(OUT_FS, "first_stop_degenerate_cases.csv")]
    write_manifest(OUT_B, dict(protocol="threshold_protocol_v2", seeds=SEEDS,
                               baselines=list(baseline_results), ablations=list(ablations),
                               first_stop=list(fs_columns), bootstrap_replicates=NBOOT),
                   outputs, started, inputs=[os.path.join(DH, "task_aligned_dataset_v1.csv")])
    write_manifest(OUT_FS, dict(protocols=["threshold_protocol_v2",
                                           "uncertainty_protocol_v2",
                                           "Phase 3C frozen-family sensitivity"],
                                seeds=SEEDS, representations=list(rep_specs),
                                bootstrap_replicates=NBOOT),
                   [os.path.join(OUT_FS, "first_stop_results.json"),
                    os.path.join(OUT_FS, "first_stop_per_row.csv.gz"),
                    os.path.join(OUT_FS, "first_stop_degenerate_cases.csv")],
                   started, inputs=[os.path.join(DH, "task_aligned_dataset_v1.csv")])
    verify_frozen_or_die()
    print(f"[baselines+ablations] done in {time.time()-started:.0f}s")


if __name__ == "__main__":
    main()
