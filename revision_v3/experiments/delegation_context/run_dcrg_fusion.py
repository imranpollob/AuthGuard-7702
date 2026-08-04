"""Family-held-out evaluation of DCRG features and fixed context/sequence risk fusion.

Protocol for outer test fold ``t``:
  * train DCRG XGBoost on the same three training folds as AuthGuard;
  * calibrate DCRG scores on validation fold ``(t + 1) % 5``;
  * score that validation fold with the already-frozen sequence checkpoint for ``t``;
  * apply the pre-specified monotone noisy-OR fusion;
  * derive operating thresholds from validation negatives only;
  * evaluate once on untouched test-fold families.

This experiment is an engineering/provisional benchmark until the independent human labels are
complete.  The legacy labels partly encode static-analysis evidence, so improvements here alone
must not be presented as proof of semantic security or external validity.
"""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np
import pandas as pd
import torch
from sklearn.linear_model import LogisticRegression
from xgboost import XGBClassifier

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
V3 = os.path.join(REPO_ROOT, "revision_v3")
sys.path.insert(0, os.path.join(V3, "src"))

from analysis.delegation_context import DCRG_FEATURE_ORDER  # noqa: E402
from data.loader import fold_split, load_primary_dataset  # noqa: E402
from evaluation.metrics import auprc, auroc, full_metrics, metrics_at_threshold  # noqa: E402
from evaluation.model_runtime import score_dataset_single_checkpoint  # noqa: E402
from evaluation.selective_policy import (  # noqa: E402
    risk_union,
    selective_decisions,
    selective_policy_metrics,
)
from training.harness import SEEDS  # noqa: E402

RESULTS_DIR = os.path.join(V3, "results", "delegation_context")
FEATURE_PATH = os.path.join(RESULTS_DIR, "dcrg_primary_features.csv.gz")
EXTRACTION_REPORT = os.path.join(RESULTS_DIR, "dcrg_extraction_report.json")
SEQUENCE_PREDICTIONS = os.path.join(
    V3, "results", "authguard_sequence_dense_predictions.csv.gz"
)


def calibrated_context_scores(train_x, train_y, val_x, val_y, test_x, seed: int,
                              extra_x=None, train_sample_weight=None):
    """Fit a fixed-capacity context model and one-dimensional validation calibrator."""
    negatives = int((train_y == 0).sum())
    positives = int((train_y == 1).sum())
    classifier = XGBClassifier(
        n_estimators=250,
        max_depth=3,
        learning_rate=0.03,
        min_child_weight=3,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_lambda=2.0,
        objective="binary:logistic",
        eval_metric="logloss",
        scale_pos_weight=negatives / max(positives, 1),
        random_state=seed,
        n_jobs=1,
        tree_method="hist",
    )
    classifier.fit(train_x, train_y, sample_weight=train_sample_weight, verbose=False)
    raw_val = classifier.predict_proba(val_x)[:, 1]
    raw_test = classifier.predict_proba(test_x)[:, 1]
    raw_extra = classifier.predict_proba(extra_x)[:, 1] if extra_x is not None else None

    epsilon = 1e-6
    val_logit = np.log(np.clip(raw_val, epsilon, 1 - epsilon) /
                       np.clip(1 - raw_val, epsilon, 1 - epsilon)).reshape(-1, 1)
    test_logit = np.log(np.clip(raw_test, epsilon, 1 - epsilon) /
                        np.clip(1 - raw_test, epsilon, 1 - epsilon)).reshape(-1, 1)
    calibrator = LogisticRegression(C=1.0, random_state=seed)
    calibrator.fit(val_logit, val_y)
    calibrated_val = calibrator.predict_proba(val_logit)[:, 1]
    calibrated_test = calibrator.predict_proba(test_logit)[:, 1]
    if raw_extra is not None:
        extra_logit = np.log(np.clip(raw_extra, epsilon, 1 - epsilon) /
                             np.clip(1 - raw_extra, epsilon, 1 - epsilon)).reshape(-1, 1)
        calibrated_extra = calibrator.predict_proba(extra_logit)[:, 1]
    else:
        calibrated_extra = None
    importance = dict(zip(DCRG_FEATURE_ORDER, classifier.feature_importances_.tolist()))
    return calibrated_val, calibrated_test, importance, calibrated_extra


def aligned_test_sequence_scores(predictions: pd.DataFrame, test_df: pd.DataFrame,
                                 seed: int, test_fold: int) -> np.ndarray:
    subset = predictions[
        (predictions["seed"] == seed) & (predictions["test_fold"] == test_fold)
    ][["sample_id", "calibrated_score"]]
    if subset["sample_id"].duplicated().any():
        raise RuntimeError(f"duplicate sequence predictions for seed={seed}, fold={test_fold}")
    score_map = dict(zip(subset["sample_id"], subset["calibrated_score"]))
    missing = [sample_id for sample_id in test_df["sample_id"] if sample_id not in score_map]
    if missing:
        raise RuntimeError(
            f"missing {len(missing)} test predictions for seed={seed}, fold={test_fold}"
        )
    return np.asarray([score_map[sample_id] for sample_id in test_df["sample_id"]],
                      dtype=np.float64)


def main() -> int:
    os.makedirs(RESULTS_DIR, exist_ok=True)
    if not (os.path.exists(FEATURE_PATH) and os.path.exists(EXTRACTION_REPORT)):
        raise SystemExit("full DCRG extraction is incomplete; run build_dcrg_features.py first")
    with open(EXTRACTION_REPORT) as handle:
        extraction = json.load(handle)
    if extraction.get("status") != "COMPLETE":
        raise SystemExit(f"DCRG extraction status is {extraction.get('status')!r}, not COMPLETE")

    primary = load_primary_dataset()
    features = pd.read_csv(FEATURE_PATH)
    if len(features) != len(primary) or features["sample_id"].nunique() != len(primary):
        raise RuntimeError("DCRG feature artifact does not cover the canonical primary population")
    merged = primary.merge(
        features[["sample_id", "coverage", *DCRG_FEATURE_ORDER]],
        on="sample_id", how="left", validate="one_to_one"
    )
    if merged[list(DCRG_FEATURE_ORDER)].isna().any().any():
        raise RuntimeError("DCRG feature artifact contains missing scalar features")
    sequence_predictions = pd.read_csv(SEQUENCE_PREDICTIONS)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[dcrg_fusion] device={device}", flush=True)

    fold_rows = []
    prediction_rows = []
    importance_rows = []
    start = time.time()
    for seed in SEEDS:
        for test_fold in range(5):
            train_df, val_df, test_df = fold_split(merged, test_fold)
            feature_names = list(DCRG_FEATURE_ORDER)
            train_x = train_df[feature_names].to_numpy(dtype=np.float32)
            val_x = val_df[feature_names].to_numpy(dtype=np.float32)
            test_x = test_df[feature_names].to_numpy(dtype=np.float32)
            train_y = train_df["label"].to_numpy(dtype=np.int64)
            val_y = val_df["label"].to_numpy(dtype=np.int64)
            test_y = test_df["label"].to_numpy(dtype=np.int64)

            context_val, context_test, importance, _ = calibrated_context_scores(
                train_x, train_y, val_x, val_y, test_x, seed
            )
            sequence_val, checkpoint = score_dataset_single_checkpoint(
                "authguard_sequence_dense", seed, test_fold,
                val_df["runtime_bytecode"].tolist(), device=device
            )
            if int(checkpoint.get("test_fold", test_fold)) != test_fold:
                raise RuntimeError("sequence checkpoint split provenance mismatch")
            sequence_test = aligned_test_sequence_scores(
                sequence_predictions, test_df, seed, test_fold
            )
            fusion_val = risk_union(sequence_val, context_val)
            fusion_test = risk_union(sequence_test, context_test)

            metrics_by_model = {}
            for model_name, val_scores, test_scores in (
                ("sequence", sequence_val, sequence_test),
                ("dcrg", context_val, context_test),
                ("dcrg_sequence_noisy_or", fusion_val, fusion_test),
            ):
                model_metrics = full_metrics(test_y, test_scores, val_scores, val_y)
                metrics_by_model[model_name] = model_metrics
                fold_rows.append({
                    "seed": seed,
                    "test_fold": test_fold,
                    "val_fold": (test_fold + 1) % 5,
                    "model": model_name,
                    "n_train": len(train_df),
                    "n_val": len(val_df),
                    "n_test": len(test_df),
                    **model_metrics,
                })

            fusion_threshold = metrics_by_model["dcrg_sequence_noisy_or"]["threshold_5pct"]
            decisions = selective_decisions(
                fusion_test, fusion_threshold, test_df["coverage"].to_numpy()
            )
            policy_metrics = selective_policy_metrics(test_y, decisions)
            fold_rows.append({
                "seed": seed,
                "test_fold": test_fold,
                "val_fold": (test_fold + 1) % 5,
                "model": "coverage_aware_selective_policy",
                "n_train": len(train_df),
                "n_val": len(val_df),
                "n_test": len(test_df),
                "threshold_5pct": fusion_threshold,
                **policy_metrics,
            })

            for item_position, row in enumerate(test_df.itertuples(index=False)):
                prediction_rows.append({
                    "seed": seed,
                    "test_fold": test_fold,
                    "sample_id": row.sample_id,
                    "family_id": row.family_id,
                    "label": int(row.label),
                    "coverage": row.coverage,
                    "sequence_score": float(sequence_test[item_position]),
                    "dcrg_score": float(context_test[item_position]),
                    "fusion_score": float(fusion_test[item_position]),
                    "sequence_threshold_5pct": float(
                        metrics_by_model["sequence"]["threshold_5pct"]
                    ),
                    "dcrg_threshold_5pct": float(
                        metrics_by_model["dcrg"]["threshold_5pct"]
                    ),
                    "fusion_threshold_5pct": float(fusion_threshold),
                    "selective_decision": str(decisions[item_position]),
                })
            importance_rows.append({"seed": seed, "test_fold": test_fold, **importance})
            print(
                f"[dcrg_fusion] seed={seed} fold={test_fold} "
                f"sequence_AUPRC={metrics_by_model['sequence']['auprc']:.3f} "
                f"context_AUPRC={metrics_by_model['dcrg']['auprc']:.3f} "
                f"fusion_AUPRC={metrics_by_model['dcrg_sequence_noisy_or']['auprc']:.3f} "
                f"defer={policy_metrics['defer_rate']:.1%}",
                flush=True,
            )

    fold_df = pd.DataFrame(fold_rows)
    fold_path = os.path.join(RESULTS_DIR, "dcrg_fusion_fold_seed.csv")
    prediction_path = os.path.join(RESULTS_DIR, "dcrg_fusion_predictions.csv.gz")
    importance_path = os.path.join(RESULTS_DIR, "dcrg_feature_importance.csv")
    fold_df.to_csv(fold_path, index=False)
    prediction_df = pd.DataFrame(prediction_rows)
    prediction_df.to_csv(prediction_path, index=False, compression="gzip")
    pd.DataFrame(importance_rows).to_csv(importance_path, index=False)

    metric_columns = [
        "auprc", "auroc", "brier", "recall_at_5pct", "observed_fpr_at_5pct",
        "precision_at_5pct", "defer_rate", "actionable_coverage",
        "positive_rate_within_low_observed_risk",
    ]
    fold_mean_summary = {}
    for model_name, group in fold_df.groupby("model"):
        fold_mean_summary[model_name] = {}
        for metric in metric_columns:
            values = pd.to_numeric(group.get(metric), errors="coerce").dropna()
            if len(values):
                fold_mean_summary[model_name][metric] = {
                    "mean": float(values.mean()),
                    "std_across_fold_seed_runs": float(values.std(ddof=1)),
                    "n_runs": int(len(values)),
                }
    pooled_oof_summary = {}
    for model_name, score_column, threshold_column in (
        ("sequence", "sequence_score", "sequence_threshold_5pct"),
        ("dcrg", "dcrg_score", "dcrg_threshold_5pct"),
        ("dcrg_sequence_noisy_or", "fusion_score", "fusion_threshold_5pct"),
    ):
        per_seed = []
        for seed, group in prediction_df.groupby("seed"):
            labels = group["label"].to_numpy(dtype=np.int64)
            scores = group[score_column].to_numpy(dtype=np.float64)
            thresholds = group[threshold_column].to_numpy(dtype=np.float64)
            per_seed.append({
                "seed": int(seed),
                "auprc": auprc(labels, scores),
                "auroc": auroc(labels, scores),
                **metrics_at_threshold(labels, scores, thresholds),
            })
        pooled_oof_summary[model_name] = {
            "mean_across_seeds": {
                metric: float(np.mean([row[metric] for row in per_seed]))
                for metric in ("auprc", "auroc", "precision", "recall", "observed_fpr", "f1")
            },
            "per_seed": per_seed,
        }
    report = {
        "status": "PROVISIONAL_LEGACY_LABEL_EVALUATION",
        "protocol": "family-grouped 5-fold outer test x 3 seeds; validation-only calibration "
                    "and thresholds; fixed noisy-OR fusion",
        "sequence_checkpoint_provenance": "same outer-test checkpoint for validation and test; "
                                          "test families absent from checkpoint training",
        "context_feature_schema": "dcrg-1.1",
        "selective_outputs": ["WARN", "LOW_OBSERVED_RISK", "DEFER"],
        "fold_mean_summary": fold_mean_summary,
        "pooled_out_of_fold_summary": pooled_oof_summary,
        "wall_seconds": time.time() - start,
        "limitations": [
            "The primary labels partly encode static-analysis evidence; this evaluation can "
            "validate engineering behavior but cannot establish independent semantic validity.",
            "Independent human Gold-Test and legitimate post-cutoff family evaluation are "
            "required before paper-level superiority or safety claims.",
            "LOW_OBSERVED_RISK is not a proof of safety and is emitted only under COMPLETE "
            "bounded-analysis coverage.",
        ],
        "artifacts": {
            "fold_seed_metrics": os.path.relpath(fold_path, REPO_ROOT),
            "predictions": os.path.relpath(prediction_path, REPO_ROOT),
            "feature_importance": os.path.relpath(importance_path, REPO_ROOT),
        },
    }
    with open(os.path.join(RESULTS_DIR, "dcrg_fusion_report.json"), "w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    print(json.dumps(report, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
