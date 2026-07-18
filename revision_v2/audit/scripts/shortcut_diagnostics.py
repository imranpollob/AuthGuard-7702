#!/usr/bin/env python3
"""Part 3 — dataset-source shortcut diagnostics.

Tests whether trivial acquisition/provenance features (never opcode content) predict the
primary labels under the same family-disjoint outer folds, on BOTH the original primary
population (task_aligned v1) and the corrected v2 PRIMARY_EVALUATION population.

Also runs a population-identification diagnostic: can trivial features distinguish the
EXTERNAL_BENIGN_CONTROL population from primary negatives? (If yes, mixing the control
into the primary task would manufacture separability — justifying its separation.)

Output: revision_v2/audit/shortcut_diagnostics.csv
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

HERE = os.path.dirname(os.path.abspath(__file__))
AUDIT = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(AUDIT, "..", ".."))
sys.path.insert(0, HERE)
from audit_dataset import norm, opcount, sha  # noqa: E402

CBOR_MARKERS = ("a2646970667358", "a16469706673")
SEED = 7702

FEATURE_SETS = {
    "bytecode_length": ["code_bytes"],
    "opcode_count": ["opcode_count"],
    "metadata_presence": ["has_cbor_metadata"],
    "duplicate_group_size": ["exact_duplicate_count"],
    "family_size": ["family_size"],
    "chain": "CHAIN_ONEHOT",
    "all_trivial_no_chain": ["code_bytes", "opcode_count", "has_cbor_metadata",
                             "exact_duplicate_count", "family_size"],
    "all_trivial_with_chain": "ALL_PLUS_CHAIN",
}


def prepare(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    if "code_bytes" not in frame:
        frame["bc"] = frame["bytecode"].map(norm)
        frame["code_bytes"] = frame["bc"].str.len() // 2
        frame["opcode_count"] = frame["bc"].map(opcount)
        frame["has_cbor_metadata"] = frame["bc"].map(
            lambda b: any(m in b[-300:] for m in CBOR_MARKERS))
        frame["h"] = frame["bc"].map(sha)
        frame["exact_duplicate_count"] = frame.groupby("h")["address"].transform("size")
        frame["family_size"] = frame.groupby("family_id")["address"].transform("size")
    frame["has_cbor_metadata"] = frame["has_cbor_metadata"].astype(int)
    return frame


def matrix(frame: pd.DataFrame, spec) -> np.ndarray:
    chain_dummies = pd.get_dummies(frame["chain"].astype(str), prefix="chain")
    if spec == "CHAIN_ONEHOT":
        return chain_dummies.to_numpy(dtype=float)
    if spec == "ALL_PLUS_CHAIN":
        base = frame[FEATURE_SETS["all_trivial_no_chain"]].to_numpy(dtype=float)
        return np.hstack([base, chain_dummies.to_numpy(dtype=float)])
    return frame[spec].to_numpy(dtype=float).reshape(len(frame), -1)


def run_task(frame: pd.DataFrame, fold_col: str, task_name: str, rows: list):
    frame = frame.dropna(subset=[fold_col]).copy()
    frame["fold"] = frame[fold_col].astype(int)
    y_all = frame["label"].to_numpy(dtype=int)
    for feature_name, spec in FEATURE_SETS.items():
        X_all = matrix(frame, spec)
        for model_name in ("logistic", "xgboost"):
            aps, aucs = [], []
            for fold in sorted(frame["fold"].unique()):
                test = frame["fold"].to_numpy() == fold
                train = ~test
                if len(np.unique(y_all[test])) < 2 or len(np.unique(y_all[train])) < 2:
                    continue
                if model_name == "logistic":
                    scaler = StandardScaler().fit(X_all[train])
                    model = LogisticRegression(max_iter=2000, random_state=SEED)
                    model.fit(scaler.transform(X_all[train]), y_all[train])
                    scores = model.predict_proba(scaler.transform(X_all[test]))[:, 1]
                else:
                    model = XGBClassifier(
                        n_estimators=200, max_depth=4, learning_rate=0.1,
                        subsample=0.9, colsample_bytree=0.9, eval_metric="logloss",
                        n_jobs=8, tree_method="hist", random_state=SEED)
                    model.fit(X_all[train], y_all[train])
                    scores = model.predict_proba(X_all[test])[:, 1]
                aps.append(average_precision_score(y_all[test], scores))
                aucs.append(roc_auc_score(y_all[test], scores))
            rows.append({
                "task": task_name, "features": feature_name, "model": model_name,
                "n_rows": int(len(frame)), "positive_fraction": float(y_all.mean()),
                "AUPRC_mean": float(np.mean(aps)), "AUPRC_sd": float(np.std(aps)),
                "ROC_AUC_mean": float(np.mean(aucs)), "ROC_AUC_sd": float(np.std(aucs)),
                "n_folds": len(aps),
            })
            print(f"[shortcut] {task_name} | {feature_name} | {model_name}: "
                  f"AUPRC {np.mean(aps):.3f} AUROC {np.mean(aucs):.3f}", flush=True)


def main() -> int:
    rows: list = []

    # original primary population
    ta = pd.read_csv(os.path.join(ROOT, "paper_build", "data_hygiene",
                                  "task_aligned_dataset_v1.csv"))
    ta["label"] = (ta["class"] == "malicious").astype(int)
    original = prepare(ta[ta["class"].isin(["malicious", "benign_cleared"])])
    run_task(original, "outer_fold_primary",
             "original_primary_mal_vs_cleared", rows)

    # corrected v2 primary population
    v2 = pd.read_csv(os.path.join(ROOT, "revision_v2", "data",
                                  "authguardbench_7702_v2.csv.gz"))
    primary = v2[v2["population"] == "PRIMARY_EVALUATION"].copy()
    primary["fold_source"] = primary["fold_id"]
    run_task(prepare_v2(primary), "fold_id", "v2_primary_mal_vs_cleared", rows)

    # population-identification: external control vs primary negatives (label =
    # "is external control"), family-disjoint on secondary folds
    negatives = v2[(v2["label"] == 0) & v2["population"].isin(
        ["PRIMARY_EVALUATION", "EXTERNAL_BENIGN_CONTROL"])].copy()
    negatives["label"] = (negatives["population"] == "EXTERNAL_BENIGN_CONTROL").astype(int)
    run_task(prepare_v2(negatives), "outer_fold_secondary",
             "population_id_control_vs_primary_negatives", rows)

    frame = pd.DataFrame(rows)
    frame.to_csv(os.path.join(AUDIT, "shortcut_diagnostics.csv"), index=False)
    print(f"[shortcut] wrote {len(frame)} rows")
    return 0


def prepare_v2(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame["has_cbor_metadata"] = frame["has_cbor_metadata"].astype(int)
    # duplicate/family sizes recomputed within the evaluated population so the
    # diagnostic reflects what a model could exploit inside that task
    frame["exact_duplicate_count"] = frame.groupby("bytecode_sha256")[
        "sample_id"].transform("size")
    frame["family_size"] = frame.groupby("family_id")["sample_id"].transform("size")
    return frame


if __name__ == "__main__":
    sys.exit(main())
