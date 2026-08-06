"""Stage 7.6: compare decision strategies on identical frozen scores.

The model whose scores are used is selected on VALIDATION AUPRC (never on test). Policies are
applied over the full test population, including U rows, which have no binary ground truth and
are therefore only ever counted in defer accounting -- never as a warning hit or miss.

Strategies: no deferral, coverage-based (defer PARTIAL analysis), score-margin (defer the band
closest to the operating threshold), and random at the matched defer rate (mean of repeated
draws, so the comparison is not a single lucky sample).
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

from lib.config import load_config  # noqa: E402
from lib.features import build_feature_matrix  # noqa: E402
from lib.repo_paths import add_revision_v3_src_to_path  # noqa: E402

add_revision_v3_src_to_path()
from evaluation.metrics import auprc, threshold_at_nominal_fpr  # noqa: E402

POS, NEG = {"R1", "R2"}, {"B"}
N_RANDOM_REPEATS = 200


def outcome_metrics(df: pd.DataFrame, deferred: np.ndarray, warn: np.ndarray) -> dict:
    """df has columns y (nan for U) and final_label. `deferred`/`warn` are boolean arrays."""
    active = ~deferred
    decidable = df["y"].notna().to_numpy()
    y = df["y"].fillna(-1).to_numpy()

    tp = int(((warn & active) & (y == 1)).sum())
    fp = int(((warn & active) & (y == 0)).sum())
    fn = int(((~warn & active) & (y == 1)).sum())
    n_pos_total = int((y == 1).sum())

    return {
        "defer_rate": float(deferred.mean()),
        "n_deferred": int(deferred.sum()),
        "n_warned": int((warn & active).sum()),
        "warning_precision": (tp / (tp + fp)) if (tp + fp) else None,
        "warning_recall_over_active_positives": (tp / (tp + fn)) if (tp + fn) else None,
        "warning_recall_over_all_positives": (tp / n_pos_total) if n_pos_total else None,
        "positives_receiving_no_warning_while_active": fn,
        "positives_deferred": int(((deferred) & (y == 1)).sum()),
        "n_undecidable_U_deferred": int((deferred & ~decidable).sum()),
        "n_undecidable_U_warned": int(((warn & active) & ~decidable).sum()),
        "n_undecidable_U_no_warning": int(((~warn & active) & ~decidable).sum()),
    }


def main():
    cfg = load_config()
    run_id = cfg["run_id"]
    gold_dir = cfg["_resolved_paths"]["gold_dataset"]
    split_dir = cfg["_resolved_paths"]["split_manifests"]
    results_dir = os.path.join(gold_dir, "experiments")
    rng = np.random.default_rng(cfg.get("seed", 7702))

    exp = json.load(open(os.path.join(results_dir, f"{run_id}_experiment_results.json")))

    def load(split):
        d = pd.read_csv(os.path.join(split_dir, f"{run_id}_{split}.csv"))
        d["y"] = d["final_label"].map(lambda x: 1.0 if x in POS else (0.0 if x in NEG else np.nan))
        return d

    train, val, test = load("train"), load("val"), load("test")
    tr = train[train["y"].notna()]
    va = val[val["y"].notna()]

    X_tr, y_tr = build_feature_matrix(tr["runtime_bytecode"]), tr["y"].to_numpy().astype(int)
    X_va, y_va = build_feature_matrix(va["runtime_bytecode"]), va["y"].to_numpy().astype(int)
    X_huang = None

    params = dict(max_depth=3, eta=0.1, objective="binary:logistic", eval_metric="aucpr",
                  subsample=0.9, colsample_bytree=0.9, seed=7702)
    huang = pd.read_csv(os.path.join(gold_dir, f"{run_id}_huang_weak_labels.csv"))
    gold_all = pd.read_csv(os.path.join(gold_dir, f"{run_id}_gold_reviewed.csv"))
    huang = huang[~huang["address"].str.lower().isin(set(gold_all["address"].str.lower()))]
    X_huang = build_feature_matrix(huang["runtime_bytecode"])
    y_huang = huang["label"].to_numpy().astype(int)

    boosters = {
        "A_huang_only": xgb.train(params, xgb.DMatrix(X_huang, label=y_huang), num_boost_round=150),
        "B_human_only": xgb.train(params, xgb.DMatrix(X_tr, label=y_tr), num_boost_round=150),
    }
    boosters["C_pretrain_finetune"] = xgb.train(
        params, xgb.DMatrix(X_tr, label=y_tr), num_boost_round=150, xgb_model=boosters["A_huang_only"])

    # ---- model selection on VALIDATION only ----
    val_auprc = {name: auprc(y_va, b.predict(xgb.DMatrix(X_va))) for name, b in boosters.items()}
    chosen = max(val_auprc, key=val_auprc.get)
    booster = boosters[chosen]

    s_va = booster.predict(xgb.DMatrix(X_va))
    threshold = float(threshold_at_nominal_fpr(s_va, y_va, 0.05))
    X_te_all = build_feature_matrix(test["runtime_bytecode"])
    scores = booster.predict(xgb.DMatrix(X_te_all))
    test = test.assign(score=scores)

    warn_base = scores >= threshold
    n = len(test)

    strategies = {}
    none_def = np.zeros(n, dtype=bool)
    strategies["no_deferral"] = outcome_metrics(test, none_def, warn_base)

    cov_def = (test["coverage_status"] == "PARTIAL").to_numpy()
    strategies["coverage_based_deferral"] = outcome_metrics(test, cov_def, warn_base)

    matched_rate = float(cov_def.mean())
    k = int(round(matched_rate * n))
    margin_def = np.zeros(n, dtype=bool)
    if k:
        margin_def[np.argsort(np.abs(scores - threshold))[:k]] = True
    strategies["score_margin_deferral"] = outcome_metrics(test, margin_def, warn_base)

    rand_runs = []
    for _ in range(N_RANDOM_REPEATS):
        rd = np.zeros(n, dtype=bool)
        if k:
            rd[rng.choice(n, size=k, replace=False)] = True
        rand_runs.append(outcome_metrics(test, rd, warn_base))
    rand_mean = {}
    for key in rand_runs[0]:
        vals = [r[key] for r in rand_runs if r[key] is not None]
        rand_mean[key] = float(np.mean(vals)) if vals else None
    rand_mean["_note"] = f"mean over {N_RANDOM_REPEATS} random draws at the matched defer rate"
    strategies["random_deferral_matched_rate"] = rand_mean

    # ---- precision vs defer-rate curves ----
    curves = {}
    for policy in ("score_margin", "random", "coverage_then_margin"):
        pts = []
        for rate in np.linspace(0.0, 0.8, 17):
            kk = int(round(rate * n))
            if policy == "score_margin":
                d = np.zeros(n, dtype=bool)
                if kk:
                    d[np.argsort(np.abs(scores - threshold))[:kk]] = True
            elif policy == "random":
                acc = []
                for _ in range(50):
                    d0 = np.zeros(n, dtype=bool)
                    if kk:
                        d0[rng.choice(n, size=kk, replace=False)] = True
                    acc.append(outcome_metrics(test, d0, warn_base))
                p = [a["warning_precision"] for a in acc if a["warning_precision"] is not None]
                r = [a["warning_recall_over_all_positives"] for a in acc if a["warning_recall_over_all_positives"] is not None]
                pts.append({"defer_rate": float(kk / n),
                            "warning_precision": float(np.mean(p)) if p else None,
                            "warning_recall_over_all_positives": float(np.mean(r)) if r else None})
                continue
            else:
                d = cov_def.copy()
                extra = kk - int(d.sum())
                if extra > 0:
                    order = np.argsort(np.abs(scores - threshold))
                    for idx in order:
                        if extra <= 0:
                            break
                        if not d[idx]:
                            d[idx] = True
                            extra -= 1
            m = outcome_metrics(test, d, warn_base)
            pts.append({"defer_rate": m["defer_rate"], "warning_precision": m["warning_precision"],
                        "warning_recall_over_all_positives": m["warning_recall_over_all_positives"]})
        curves[policy] = pts

    out = {
        "model_selected_on_validation": chosen,
        "validation_auprc_by_model": val_auprc,
        "operating_threshold_at_5pct_val_fpr": threshold,
        "test_population": {"n_rows": int(n),
                            "n_decidable": int(test["y"].notna().sum()),
                            "n_positive": int((test["y"] == 1).sum()),
                            "n_U_undecidable": int(test["y"].isna().sum())},
        "matched_defer_rate": matched_rate,
        "strategies": strategies,
        "precision_vs_defer_rate_curves": curves,
        "notscreenable_always_deferred": int(len(pd.read_csv(os.path.join(gold_dir, f"{run_id}_notscreenable.csv")))),
    }
    path = os.path.join(results_dir, f"{run_id}_decision_strategies.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2, default=str)
    test[["address", "final_label", "coverage_status", "y", "score", "split_group"]].to_csv(
        os.path.join(results_dir, f"{run_id}_decision_scores.csv"), index=False)
    print(json.dumps({k: v for k, v in out.items() if k != "precision_vs_defer_rate_curves"},
                     indent=2, default=str))


if __name__ == "__main__":
    main()
