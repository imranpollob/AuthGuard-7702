"""Stage 7.4 + 7.5: experiments A/B/C and evaluation on the untouched temporal test set.

Label mapping (per the brief):
    R1, R2        -> warning-positive (1)
    B             -> negative (0)
    U             -> defer/abstain: never trained on, never scored as a binary case
    NOTSCREENABLE -> defer: no bytecode exists, so no feature vector can be built

Experiments:
    A  Huang weak labels only
    B  human-reviewed labels only
    C  Huang pretraining then human-label fine-tuning (continued boosting)

The test split is used exactly once, for reporting. Thresholds and calibration come from the
validation split only. Bootstrap CIs are clustered on `split_group` (the family/proxy closure),
because contracts inside a group are not independent.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "dataset_pipeline")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import xgboost as xgb  # noqa: E402
from sklearn.isotonic import IsotonicRegression  # noqa: E402

from lib.config import load_config  # noqa: E402
from lib.features import build_feature_matrix  # noqa: E402
from lib.repo_paths import REPO_ROOT, add_revision_v3_src_to_path  # noqa: E402

add_revision_v3_src_to_path()
from evaluation.metrics import auprc, auroc, brier, metrics_at_threshold, threshold_at_nominal_fpr  # noqa: E402

POSITIVE = {"R1", "R2"}
NEGATIVE = {"B"}
DEFER = {"U"}
XGB_PARAMS = dict(max_depth=3, eta=0.1, objective="binary:logistic", eval_metric="aucpr",
                  subsample=0.9, colsample_bytree=0.9, min_child_weight=1, seed=7702)
N_ROUNDS = 150
N_BOOT = 2000


def to_binary(label: str):
    if label in POSITIVE:
        return 1
    if label in NEGATIVE:
        return 0
    return np.nan


def clustered_bootstrap(y, s, groups, fn, n_boot=N_BOOT, seed=7702):
    """Resample GROUPS with replacement, so dependence inside a family is respected."""
    rng = np.random.default_rng(seed)
    uniq = np.array(sorted(set(groups)))
    idx_by_group = {g: np.where(groups == g)[0] for g in uniq}
    out = []
    for _ in range(n_boot):
        picked = rng.choice(uniq, size=len(uniq), replace=True)
        idx = np.concatenate([idx_by_group[g] for g in picked])
        yy, ss = y[idx], s[idx]
        if len(set(yy.tolist())) < 2:
            continue
        try:
            out.append(fn(yy, ss))
        except ValueError:
            continue
    if not out:
        return (None, None)
    return (float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5)))


def main():
    cfg = load_config()
    run_id = cfg["run_id"]
    gold_dir = cfg["_resolved_paths"]["gold_dataset"]
    split_dir = cfg["_resolved_paths"]["split_manifests"]
    results_dir = os.path.join(gold_dir, "experiments")
    os.makedirs(results_dir, exist_ok=True)

    train = pd.read_csv(os.path.join(split_dir, f"{run_id}_train.csv"))
    val = pd.read_csv(os.path.join(split_dir, f"{run_id}_val.csv"))
    test = pd.read_csv(os.path.join(split_dir, f"{run_id}_test.csv"))
    for df in (train, val, test):
        df["y"] = df["final_label"].map(to_binary)

    huang = pd.read_csv(os.path.join(gold_dir, f"{run_id}_huang_weak_labels.csv"))
    gold_all = pd.read_csv(os.path.join(gold_dir, f"{run_id}_gold_reviewed.csv"))
    # Exclude any Huang row overlapping the gold population by address OR by exact bytecode,
    # so pretraining cannot see a test contract under a different address.
    import hashlib
    def bc_hash(b):
        try:
            return hashlib.sha256(bytes.fromhex(str(b).lower().removeprefix("0x"))).hexdigest()
        except ValueError:
            return None
    gold_hashes = set(gold_all["exact_bytecode_hash"])
    gold_addrs = set(gold_all["address"].str.lower())
    huang["addr_l"] = huang["address"].str.lower()
    huang["bc_sha"] = huang["runtime_bytecode"].map(bc_hash)
    n_huang_raw = len(huang)
    huang = huang[~huang["addr_l"].isin(gold_addrs) & ~huang["bc_sha"].isin(gold_hashes)].copy()
    n_huang_excluded = n_huang_raw - len(huang)

    X_huang = build_feature_matrix(huang["runtime_bytecode"])
    y_huang = huang["label"].to_numpy().astype(int)

    tr = train[train["y"].notna()].reset_index(drop=True)
    va = val[val["y"].notna()].reset_index(drop=True)
    te = test[test["y"].notna()].reset_index(drop=True)
    X_tr, y_tr = build_feature_matrix(tr["runtime_bytecode"]), tr["y"].to_numpy().astype(int)
    X_va, y_va = build_feature_matrix(va["runtime_bytecode"]), va["y"].to_numpy().astype(int)
    X_te, y_te = build_feature_matrix(te["runtime_bytecode"]), te["y"].to_numpy().astype(int)
    # every test row, including U, for defer-rate accounting
    X_te_all = build_feature_matrix(test["runtime_bytecode"])

    def fit(X, y, base=None):
        return xgb.train(XGB_PARAMS, xgb.DMatrix(X, label=y), num_boost_round=N_ROUNDS, xgb_model=base)

    boosters = {
        "A_huang_only": fit(X_huang, y_huang),
        "B_human_only": fit(X_tr, y_tr),
    }
    boosters["C_pretrain_finetune"] = fit(X_tr, y_tr, base=boosters["A_huang_only"])

    counts = {
        "A_huang_only": {"n_train": int(len(y_huang)), "n_positive": int(y_huang.sum()),
                         "n_families": None,
                         "note": f"Huang weak labels; {n_huang_excluded} rows excluded for overlap with the gold population"},
        "B_human_only": {"n_train": int(len(y_tr)), "n_positive": int(y_tr.sum()),
                         "n_families": int(tr["split_group"].nunique())},
        "C_pretrain_finetune": {"n_train_pretrain": int(len(y_huang)), "n_train_finetune": int(len(y_tr)),
                                "n_positive_finetune": int(y_tr.sum()),
                                "n_families": int(tr["split_group"].nunique())},
    }

    results, all_preds = {}, {}
    for name, booster in boosters.items():
        s_va = booster.predict(xgb.DMatrix(X_va))
        s_te = booster.predict(xgb.DMatrix(X_te))
        s_te_all = booster.predict(xgb.DMatrix(X_te_all))

        # calibration fitted on VALIDATION only
        iso = IsotonicRegression(out_of_bounds="clip").fit(s_va, y_va)
        cal_te = iso.predict(s_te)

        groups = te["split_group"].to_numpy()
        res = {
            "prevalence": float(y_te.mean()),
            "n_test_decidable": int(len(y_te)),
            "n_test_positive": int(y_te.sum()),
            "auprc": auprc(y_te, s_te),
            "auroc": auroc(y_te, s_te),
            "brier_raw": brier(y_te, s_te),
            "brier_calibrated": brier(y_te, cal_te),
        }
        res["auprc_ci95"] = clustered_bootstrap(y_te, s_te, groups, auprc)
        res["auroc_ci95"] = clustered_bootstrap(y_te, s_te, groups, auroc)

        for nf in (0.01, 0.05, 0.10):
            thr = threshold_at_nominal_fpr(s_va, y_va, nf)
            m = metrics_at_threshold(y_te, s_te, thr)
            tag = f"{int(nf*100)}pct"
            res[f"threshold_at_{tag}_fpr_from_val"] = float(thr)
            res[f"recall_at_{tag}_fpr"] = m["recall"]
            res[f"precision_at_{tag}_fpr"] = m["precision"]
            res[f"f1_at_{tag}_fpr"] = m["f1"]
            res[f"observed_fpr_at_{tag}"] = m["observed_fpr"]

        thr5 = res["threshold_at_5pct_fpr_from_val"]
        m5 = metrics_at_threshold(y_te, s_te, thr5)
        res["operating_point_5pct_fpr"] = m5

        # per-label / coverage / size breakdowns over ALL test rows (U included)
        test_scores = pd.DataFrame({
            "address": test["address"], "final_label": test["final_label"],
            "coverage_status": test["coverage_status"], "bytecode_length": test["bytecode_length"],
            "split_group": test["split_group"], "score": s_te_all,
            "y": test["y"],
        })
        test_scores["size_quartile"] = pd.qcut(test_scores["bytecode_length"], 4,
                                               labels=["Q1", "Q2", "Q3", "Q4"], duplicates="drop")
        res["score_by_final_label"] = {
            k: {"n": int(len(v)), "mean_score": float(v["score"].mean()),
                "median_score": float(v["score"].median())}
            for k, v in test_scores.groupby("final_label")}
        res["score_by_coverage_status"] = {
            k: {"n": int(len(v)), "mean_score": float(v["score"].mean())}
            for k, v in test_scores.groupby("coverage_status")}
        by_q = {}
        for k, v in test_scores.groupby("size_quartile", observed=True):
            dec = v[v["y"].notna()]
            entry = {"n": int(len(v)), "n_decidable": int(len(dec)),
                     "n_positive": int(dec["y"].sum()) if len(dec) else 0,
                     "mean_score": float(v["score"].mean())}
            if len(dec) and dec["y"].nunique() == 2:
                entry["auprc"] = auprc(dec["y"].to_numpy().astype(int), dec["score"].to_numpy())
            else:
                entry["auprc"] = None
                entry["auprc_note"] = "single class in this quartile; AUPRC undefined"
            by_q[str(k)] = entry
        res["by_code_size_quartile"] = by_q

        n_defer_u = int((test["final_label"] == "U").sum())
        notscreenable = pd.read_csv(os.path.join(gold_dir, f"{run_id}_notscreenable.csv"))
        res["defer_accounting"] = {
            "n_test_rows_total": int(len(test)),
            "n_test_decidable_R1_R2_B": int(len(y_te)),
            "n_test_U_deferred": n_defer_u,
            "defer_rate_over_test_population": float(n_defer_u / len(test)),
            "n_notscreenable_population_wide_always_deferred": int(len(notscreenable)),
        }

        results[name] = res
        test_scores["model"] = name
        test_scores["calibrated_score"] = np.nan
        test_scores.loc[test_scores["y"].notna(), "calibrated_score"] = cal_te
        all_preds[name] = test_scores
        pred_path = os.path.join(results_dir, f"{run_id}_test_predictions_{name}.csv")
        test_scores.to_csv(pred_path, index=False)
        res["predictions_csv"] = pred_path

    summary = {
        "label_mapping": {"positive": sorted(POSITIVE), "negative": sorted(NEGATIVE),
                          "defer": sorted(DEFER) + ["NOTSCREENABLE"]},
        "example_and_family_counts": counts,
        "split_sizes": {"train_total": int(len(train)), "train_decidable": int(len(tr)),
                        "val_total": int(len(val)), "val_decidable": int(len(va)),
                        "test_total": int(len(test)), "test_decidable": int(len(te))},
        "families_per_split": {s: int(pd.read_csv(os.path.join(split_dir, f"{run_id}_{s}.csv"))["split_group"].nunique())
                               for s in ("train", "val", "test")},
        "huang_rows_used": int(len(huang)), "huang_rows_excluded_overlap": int(n_huang_excluded),
        "results": results,
    }
    out = os.path.join(results_dir, f"{run_id}_experiment_results.json")
    with open(out, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
