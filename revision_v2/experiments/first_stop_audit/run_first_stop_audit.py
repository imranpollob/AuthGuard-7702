#!/usr/bin/env python3
"""First-STOP shortcut and conservative canonicalization audit.

The runner compares six representations under identical family-grouped training, strict
cross-chain holdouts, duplicate controls, benign-general scoring, and donor-isolated mutation
stress. It consumes the separately generated bounded execution audit and never writes frozen
v1 artifacts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score
from xgboost import XGBClassifier

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "common"))
sys.path.insert(0, os.path.join(HERE, "..", "donor_pools"))
from canonicalizer import analyze_bytecode  # noqa: E402
from harness import (load_corpus, task_arrays, metrics_full, oof_threshold, featurize, SENS,
                     XGB_HP, SEED, RV2, DH, write_manifest, verify_frozen_or_die)  # noqa: E402
from pools import DonorPools, make_variant_isolated  # noqa: E402

OUT = os.path.join(RV2, "results", "first_stop_audit")
CONDITIONS = ["M1", "M2", "M3", "F200", "M3F200"]
REPRESENTATIONS = ["full", "metadata_stripped", "first_stop", "suffix_only",
                   "length_stop_only", "reachable_code"]
NBOOT = 10_000


def xgb_method(n_features):
    columns = list(range(n_features))

    def fit(X, y, seed):
        model = XGBClassifier(random_state=seed, **XGB_HP)
        model.fit(X[:, columns], y)
        return model

    def score(model, X):
        return model.predict_proba(X[:, columns])[:, 1]

    return dict(fit=fit, score=score, kind="learned")


def representation_matrices(hexes, full_matrix=None):
    analyses = [analyze_bytecode(h) for h in hexes]
    forms = {
        "metadata_stripped": [r["metadata_stripped_hex"] for r in analyses],
        "first_stop": [r["first_stop_hex"] for r in analyses],
        "suffix_only": [r["suffix_hex"] for r in analyses],
        "reachable_code": [r["reachable_compact_hex"] for r in analyses],
    }
    matrices = {}
    if full_matrix is None:
        dense, ngram, _ = featurize([r["normalized_hex"] for r in analyses], sens=SENS)
        matrices["full"] = np.hstack([dense, ngram]).astype(np.float32)
    else:
        matrices["full"] = np.asarray(full_matrix, dtype=np.float32)
    for name, values in forms.items():
        dense, ngram, _ = featurize(values, sens=SENS)
        matrices[name] = np.hstack([dense, ngram]).astype(np.float32)

    length_rows = []
    for result in analyses:
        a = result["analysis"]
        exec_bytes = a["executable_bytes"]
        stop_pc = a["first_stop_pc"]
        prefix = a["first_stop_prefix_bytes"]
        suffix = a["suffix_bytes"]
        length_rows.append([
            a["total_bytes"], exec_bytes, a["metadata_bytes"],
            -1 if stop_pc is None else stop_pc,
            prefix, suffix,
            0.0 if stop_pc is None else prefix / max(exec_bytes, 1),
            float(stop_pc is not None),
        ])
    matrices["length_stop_only"] = np.asarray(length_rows, dtype=np.float32)
    assert list(matrices) == ["full", "metadata_stripped", "first_stop", "suffix_only",
                              "reachable_code", "length_stop_only"]
    matrices = {name: matrices[name] for name in REPRESENTATIONS}
    assert all(len(matrix) == len(hexes) and np.isfinite(matrix).all()
               for matrix in matrices.values())
    return matrices, analyses


def summarize_folds(folds):
    frame = pd.DataFrame(folds)
    return dict(mean=frame.mean(numeric_only=True).to_dict(),
                std=frame.std(numeric_only=True, ddof=0).to_dict(),
                folds=frame.to_dict(orient="records"))


def family_bootstrap(y, score_rep, score_full, families, name):
    unique = np.asarray(sorted(pd.unique(families)))
    family_index = {family: i for i, family in enumerate(unique)}
    row_family = np.asarray([family_index[family] for family in families])
    rng_seed = int.from_bytes(hashlib.blake2b(
        f"{SEED}:first_stop_audit:{name}".encode(), digest_size=8).digest(), "little")
    rng = np.random.default_rng(rng_seed)
    delta = np.empty(NBOOT)
    for replicate in range(NBOOT):
        counts = np.bincount(rng.integers(0, len(unique), len(unique)),
                             minlength=len(unique))
        weights = counts[row_family]
        delta[replicate] = (
            average_precision_score(y, score_rep, sample_weight=weights) -
            average_precision_score(y, score_full, sample_weight=weights)
        )
    ci = [float(np.percentile(delta, 2.5)), float(np.percentile(delta, 97.5))]
    return dict(
        representation_minus_full_point=float(average_precision_score(y, score_rep) -
                                               average_precision_score(y, score_full)),
        CI95=ci, excludes_zero=bool(ci[0] > 0 or ci[1] < 0),
        boot_mean=float(delta.mean()), boot_std=float(delta.std()), replicates=NBOOT)


def duplicate_controls(per_row, sub):
    hash_by_sid = dict(zip(sub["sid"], sub["bchash"]))
    output = {}
    for name, group in per_row.groupby("representation"):
        d = group.copy()
        d["bchash"] = d["sid"].map(hash_by_sid)
        y = d["y"].to_numpy(); score = d["score"].to_numpy()
        family_sizes = d["family_id"].value_counts().to_dict()
        weights = np.asarray([1.0 / family_sizes[f] for f in d["family_id"]])
        collapsed = d.groupby("bchash", as_index=False).agg(
            y=("y", "first"), score=("score", "mean"), pred_rate=("pred", "mean"))
        singleton_hashes = set(d["bchash"].value_counts().loc[lambda s: s == 1].index)
        singleton = d[d["bchash"].isin(singleton_hashes)]
        output[name] = dict(
            observation_AUPRC=float(average_precision_score(y, score)),
            inverse_family_AUPRC=float(average_precision_score(y, score,
                                                                sample_weight=weights)),
            one_vote_per_exact_bytecode_AUPRC=float(average_precision_score(
                collapsed["y"], collapsed["score"])),
            exact_singleton_only_AUPRC=float(average_precision_score(
                singleton["y"], singleton["score"])),
            observations=int(len(d)), unique_exact_bytecodes=int(len(collapsed)),
            exact_singletons=int(len(singleton)))
    return output


def static_summary(df, analyses):
    rows = []
    for (_, row), result in zip(df.iterrows(), analyses):
        a = result["analysis"]
        rows.append(dict(
            sid=row["sid"], class_name=row["class"], chain=row["chain"],
            family_id=row["family_id"], bchash=row["bchash"],
            total_bytes=a["total_bytes"], executable_bytes=a["executable_bytes"],
            metadata_bytes=a["metadata_bytes"], metadata_recognized=a["metadata_recognized"],
            first_stop_pc=a["first_stop_pc"], first_stop_prefix_bytes=a["first_stop_prefix_bytes"],
            suffix_bytes=a["suffix_bytes"],
            cfg_reachable_after_first_stop=a["cfg_reachable_after_first_stop"],
            unresolved_reachable_jump_count=a["unresolved_reachable_jump_count"],
            code_introspection_reachable=a["code_introspection_reachable"],
            removed_executable_bytes=a["removed_executable_bytes"],
            retained_fraction=a["retained_fraction"], uncertainty=a["uncertainty"],
            removed_ranges_json=json.dumps(a["removed_ranges"], separators=(",", ":")),
            first_stop_equals_reachable=(result["first_stop_hex"] ==
                                         result["reachable_compact_hex"])))
    out = pd.DataFrame(rows)
    by_class = {}
    for class_name, group in out.groupby("class_name"):
        has_stop = group["first_stop_pc"].notna()
        by_class[class_name] = dict(
            n=int(len(group)), has_first_stop=int(has_stop.sum()),
            reachable_after_first_stop=int(group["cfg_reachable_after_first_stop"].sum()),
            reachable_after_first_stop_rate=float(group["cfg_reachable_after_first_stop"].mean()),
            median_first_stop_prefix_bytes=float(group["first_stop_prefix_bytes"].median()),
            median_suffix_bytes=float(group["suffix_bytes"].median()),
            median_removed_executable_bytes=float(group["removed_executable_bytes"].median()),
            any_executable_pruning=int((group["removed_executable_bytes"] > 0).sum()),
            code_introspection_retains_all=int(group["code_introspection_reachable"].sum()),
            unresolved_dynamic_jump_rows=int((group["unresolved_reachable_jump_count"] > 0).sum()),
            first_stop_equals_reachable=int(group["first_stop_equals_reachable"].sum()))
    return out, by_class


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-only", action="store_true",
                        help="Build every representation on 32 rows and exit before training")
    args = parser.parse_args()
    started = time.time()
    verify_frozen_or_die()
    os.makedirs(OUT, exist_ok=True)
    df, Xd, Xn, meta = load_corpus()
    full_all = np.hstack([Xd, Xn]).astype(np.float32)
    if args.validate_only:
        matrices, analyses = representation_matrices(df["bc"].iloc[:32], full_all[:32])
        assert set(matrices) == set(REPRESENTATIONS)
        assert len(analyses) == 32
        print("[validate] representations:", {k: v.shape for k, v in matrices.items()})
        verify_frozen_or_die()
        return

    execution_path = os.path.join(OUT, "execution_audit.json")
    if not os.path.exists(execution_path):
        raise SystemExit("Run run_execution_audit.py before the model audit")
    execution_audit = json.load(open(execution_path))

    all_reps, all_analyses = representation_matrices(df["bc"].tolist(), full_all)
    static_rows, static_by_class = static_summary(df, all_analyses)
    static_path = os.path.join(OUT, "static_reachability_per_row.csv.gz")
    static_rows.to_csv(static_path, index=False)

    primary_mask = df["class"].isin(["malicious", "benign_cleared"]).to_numpy()
    bg_mask = (df["class"] == "benign_general").to_numpy()
    sub, y, folds, _, _ = task_arrays(df, Xd, Xn, "primary")
    sub = sub.copy(); sub["y"] = y
    primary_reps = {name: matrix[primary_mask] for name, matrix in all_reps.items()}
    bg_reps = {name: matrix[bg_mask] for name, matrix in all_reps.items()}
    groups = sub["family_id"].to_numpy()

    primary_results = {}
    primary_rows = []
    threshold_rows = []
    fitted = {}
    for name, matrix in primary_reps.items():
        method = xgb_method(matrix.shape[1])
        fold_metrics = []
        fitted[name] = {}
        for fold in range(5):
            train = np.flatnonzero(folds != fold)
            test = np.flatnonzero(folds == fold)
            threshold, splitter, _ = oof_threshold(method, matrix[train], y[train],
                                                    groups[train], SEED)
            model = method["fit"](matrix[train], y[train], SEED)
            score = method["score"](model, matrix[test])
            metric = metrics_full(y[test], score, threshold)
            fold_metrics.append(metric)
            fitted[name][fold] = (model, threshold)
            threshold_rows.append(dict(evaluation="family", representation=name, fold=fold,
                                       threshold=threshold, splitter=splitter,
                                       train_rows=len(train), test_rows=len(test)))
            for position, row_index in enumerate(test):
                primary_rows.append(dict(
                    sid=sub["sid"].iloc[row_index], family_id=groups[row_index],
                    bchash=sub["bchash"].iloc[row_index], chain=sub["chain"].iloc[row_index],
                    y=int(y[row_index]), representation=name, fold=fold,
                    score=float(score[position]), threshold=float(threshold),
                    pred=int(score[position] >= threshold)))
            print(f"[family {name}] fold {fold}: AUPRC={metric['AUPRC']:.3f} "
                  f"FPR={metric['FPR']:.3f}", flush=True)
        primary_results[name] = summarize_folds(fold_metrics)

    primary_per_row = pd.DataFrame(primary_rows)
    duplicate_result = duplicate_controls(primary_per_row, sub)
    score_by_rep = {
        name: primary_per_row[primary_per_row["representation"] == name]
        .set_index("sid").loc[sub["sid"], "score"].to_numpy()
        for name in REPRESENTATIONS
    }
    bootstrap = {
        name: family_bootstrap(y, score_by_rep[name], score_by_rep["full"], groups, name)
        for name in REPRESENTATIONS if name != "full"
    }

    benign_results = {}
    benign_rows = []
    bg = df.loc[bg_mask].reset_index(drop=True)
    for name, matrix in bg_reps.items():
        fold_fpr = []
        for fold in range(5):
            model, threshold = fitted[name][fold]
            score = model.predict_proba(matrix)[:, 1]
            fold_fpr.append(float((score >= threshold).mean()))
            for i, value in enumerate(score):
                benign_rows.append(dict(sid=bg["sid"].iloc[i], representation=name,
                                        fold=fold, score=float(value), threshold=threshold,
                                        pred=int(value >= threshold)))
        benign_results[name] = dict(FPR_mean=float(np.mean(fold_fpr)),
                                    FPR_std=float(np.std(fold_fpr)), folds=fold_fpr,
                                    n=int(len(bg)))

    pools = DonorPools(df.assign(y=(df["class"] == "malicious").astype(int)),
                       "benign_general", "outer_fold_primary", "FIRST_STOP_AUDIT")
    robust_metrics = {name: {condition: [] for condition in CONDITIONS}
                      for name in REPRESENTATIONS}
    robust_rows = []
    for fold in range(5):
        pools.assert_disjoint(fold)
        test = np.flatnonzero(folds == fold)
        held = sub.iloc[test]
        for condition in CONDITIONS:
            transformed = [make_variant_isolated(pools, row.to_dict(), fold, "test",
                                                  condition, "test")
                           for _, row in held.iterrows()]
            matrices, _ = representation_matrices(transformed)
            for name, matrix in matrices.items():
                model, threshold = fitted[name][fold]
                score = model.predict_proba(matrix)[:, 1]
                metric = metrics_full(y[test], score, threshold)
                robust_metrics[name][condition].append(metric)
                for i, row_index in enumerate(test):
                    robust_rows.append(dict(
                        sid=sub["sid"].iloc[row_index], family_id=groups[row_index],
                        y=int(y[row_index]), fold=fold, condition=condition,
                        representation=name, score=float(score[i]), threshold=threshold,
                        pred=int(score[i] >= threshold)))
            print(f"[robust] fold {fold} {condition}", flush=True)
    robustness_results = {
        name: {condition: summarize_folds(metrics)
               for condition, metrics in by_condition.items()}
        for name, by_condition in robust_metrics.items()
    }

    cross_chain_results = {name: {} for name in REPRESENTATIONS}
    cross_chain_rows = []
    chains = sorted(sub["chain"].unique())
    for chain in chains:
        test = np.flatnonzero(sub["chain"].to_numpy() == chain)
        forbidden_families = set(sub["family_id"].iloc[test])
        forbidden_hashes = set(sub["bchash"].iloc[test])
        train_mask = ((sub["chain"].to_numpy() != chain) &
                      ~sub["family_id"].isin(forbidden_families).to_numpy() &
                      ~sub["bchash"].isin(forbidden_hashes).to_numpy())
        train = np.flatnonzero(train_mask)
        assert len(np.unique(y[train])) == 2 and len(np.unique(y[test])) == 2
        for name, matrix in primary_reps.items():
            method = xgb_method(matrix.shape[1])
            threshold, splitter, _ = oof_threshold(method, matrix[train], y[train],
                                                    groups[train], SEED)
            model = method["fit"](matrix[train], y[train], SEED)
            score = method["score"](model, matrix[test])
            metric = metrics_full(y[test], score, threshold)
            cross_chain_results[name][chain] = dict(
                metrics=metric, train_rows=int(len(train)), test_rows=int(len(test)),
                heldout_families=int(len(forbidden_families)),
                purged_rows=int(len(sub) - len(test) - len(train)), splitter=splitter)
            for i, row_index in enumerate(test):
                cross_chain_rows.append(dict(
                    sid=sub["sid"].iloc[row_index], heldout_chain=chain,
                    family_id=groups[row_index], y=int(y[row_index]), representation=name,
                    score=float(score[i]), threshold=threshold,
                    pred=int(score[i] >= threshold)))
        print(f"[cross-chain] {chain}: train={len(train)} test={len(test)}", flush=True)
    for name in REPRESENTATIONS:
        metrics = [entry["metrics"] for entry in cross_chain_results[name].values()]
        cross_chain_results[name]["macro_across_chains"] = summarize_folds(metrics)

    primary_path = os.path.join(OUT, "primary_per_row.csv.gz")
    benign_path = os.path.join(OUT, "benign_general_per_row.csv.gz")
    robust_path = os.path.join(OUT, "robustness_per_row.csv.gz")
    chain_path = os.path.join(OUT, "cross_chain_per_row.csv.gz")
    threshold_path = os.path.join(OUT, "thresholds.csv")
    ledger_path = os.path.join(OUT, "donor_ledger.csv.gz")
    primary_per_row.to_csv(primary_path, index=False)
    pd.DataFrame(benign_rows).to_csv(benign_path, index=False)
    pd.DataFrame(robust_rows).to_csv(robust_path, index=False)
    pd.DataFrame(cross_chain_rows).to_csv(chain_path, index=False)
    pd.DataFrame(threshold_rows).to_csv(threshold_path, index=False)
    donor_ledger = pools.write_ledger(ledger_path)
    pools_by_fold = {}
    for fold in range(5):
        pools_by_fold[str(fold)] = {
            part: dict(rows=int(len(pools.pool(fold, part))),
                       families=int(pools.pool(fold, part)["family_id"].nunique()),
                       executable_hashes=int(pools.pool(fold, part)["exec_sha"].nunique()))
            for part in ("train", "val", "test")}

    payload = dict(
        protocol="revision_v2/protocols/first_stop_audit_protocol.md",
        representations=REPRESENTATIONS,
        representation_dimensions={name: int(matrix.shape[1])
                                   for name, matrix in primary_reps.items()},
        dataset=dict(primary_rows=int(len(sub)), benign_general_rows=int(len(bg)),
                     chains=chains, temporal_holdout=dict(
                         available=False,
                         reason="No timestamp, date, or block-height field exists in the corpus.")),
        static_reachability_by_class=static_by_class,
        bounded_execution_audit=execution_audit,
        primary_family_evaluation=primary_results,
        duplicate_controls=duplicate_result,
        paired_family_bootstrap_vs_full=bootstrap,
        benign_general=benign_results,
        robustness=robustness_results,
        strict_cross_chain=cross_chain_results,
        donor_isolation=dict(pools_by_fold=pools_by_fold, ledger_rows=int(len(donor_ledger))),
        decision_deferred_to_report=True)
    results_path = os.path.join(OUT, "first_stop_audit_results.json")
    with open(results_path, "w") as handle:
        json.dump(payload, handle, indent=2)

    outputs = [results_path, static_path, primary_path, benign_path, robust_path, chain_path,
               threshold_path, ledger_path, execution_path,
               os.path.join(OUT, "execution_audit_per_call.csv")]
    write_manifest(OUT, dict(protocol="first_stop_audit_protocol", seed=SEED,
                             bootstrap_replicates=NBOOT, conditions=CONDITIONS,
                             representations=REPRESENTATIONS),
                   outputs, started,
                   inputs=[os.path.join(DH, "task_aligned_dataset_v1.csv"), execution_path])
    verify_frozen_or_die()
    print(f"[first-stop-audit] done in {time.time() - started:.0f}s", flush=True)


if __name__ == "__main__":
    main()
