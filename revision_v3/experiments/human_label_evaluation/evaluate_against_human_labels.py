"""Phase 2, Part 10: evaluation code prepared for when Gold-Dev/Gold-Test human labels exist.

THIS SCRIPT PRODUCES NO RESULTS RIGHT NOW. As of this Phase 2 pass, zero human annotations
have been collected (revision_v3/annotation_app/annotation.db has 230 seeded items, 400
assignments, 0 annotations -- verified in PHASE2_INFRASTRUCTURE_AND_MODEL_FINALIZATION.md).
Running `main()` against an empty or missing release export raises, on purpose, rather than
silently reporting on an empty set as if it were a real evaluation.

Once revision_v3/annotation_app/export.py has produced a real `release_gold_test.json` (or
`release_gold_dev.json`) with finalized human labels, run:

    python3 evaluate_against_human_labels.py <release_json_path> <sample_set>

This compares, against the human reference label:
  - the source static analyzer rule (binary predictor, from the canonical v2 benchmark's
    `label` column) -- precision, recall, specificity, FPR, F1, balanced accuracy.
  - the final frozen AuthGuard model, Flat CNN, and other selected baselines (continuous
    scores) -- AUPRC, AUROC, precision/recall/F1/FPR at the frozen 5%-FPR threshold, and
    calibration (Brier score, expected calibration error).

Binary mapping of the 4-way human label for these metrics: SAFE -> 0, UNSAFE -> 1;
INDETERMINATE and NOT_BYTECODE_SCREENABLE items are EXCLUDED from binary metrics (reported
separately as a count and fraction) since forcing them into a 0/1 label would misrepresent
what the human reviewer actually said.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "revision_v3", "src"))

EXCLUDED_FROM_BINARY = {"INDETERMINATE", "NOT_BYTECODE_SCREENABLE"}
LABEL_TO_BINARY = {"SAFE": 0, "UNSAFE": 1}


def load_human_reference(release_json_path: str) -> pd.DataFrame:
    with open(release_json_path) as f:
        rows = json.load(f)
    if len(rows) == 0:
        raise ValueError(
            f"{release_json_path} contains zero finalized items -- there is nothing to "
            "evaluate. This is expected until human annotation has actually happened; do "
            "not proceed by fabricating or estimating a result."
        )
    df = pd.DataFrame(rows)
    unresolved = df[df["final_label"].isna()]
    if len(unresolved) > 0:
        print(f"[WARNING] {len(unresolved)} items have no finalized label yet "
              f"(resolution={unresolved['resolution'].unique().tolist()}) and are excluded.",
              file=sys.stderr)
    df = df[df["final_label"].notna()].copy()
    df["binary_label"] = df["final_label"].map(LABEL_TO_BINARY)
    df["excluded_from_binary"] = df["final_label"].isin(EXCLUDED_FROM_BINARY)
    return df


def binary_rule_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    tp = int(((y_pred == 1) & (y_true == 1)).sum())
    fp = int(((y_pred == 1) & (y_true == 0)).sum())
    tn = int(((y_pred == 0) & (y_true == 0)).sum())
    fn = int(((y_pred == 0) & (y_true == 1)).sum())
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    balanced_accuracy = (recall + specificity) / 2
    return {
        "n": len(y_true), "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "precision": precision, "recall": recall, "specificity": specificity,
        "fpr": fpr, "f1": f1, "balanced_accuracy": balanced_accuracy,
    }


def continuous_score_metrics(y_true: np.ndarray, scores: np.ndarray, threshold: float) -> dict:
    preds = (scores >= threshold).astype(int)
    rule_metrics = binary_rule_metrics(y_true, preds)
    ece = expected_calibration_error(y_true, scores, n_bins=10)
    return {
        "auprc": float(average_precision_score(y_true, scores)),
        "auroc": float(roc_auc_score(y_true, scores)) if len(set(y_true)) > 1 else None,
        "brier": float(brier_score_loss(y_true, scores)),
        "expected_calibration_error": ece,
        **{f"threshold_{threshold:.3f}_{k}": v for k, v in rule_metrics.items()
           if k in ("precision", "recall", "f1", "fpr")},
    }


def expected_calibration_error(y_true: np.ndarray, scores: np.ndarray, n_bins: int = 10) -> float:
    bins = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    n = len(y_true)
    for i in range(n_bins):
        mask = (scores >= bins[i]) & (scores < bins[i + 1] if i < n_bins - 1 else scores <= bins[i + 1])
        if mask.sum() == 0:
            continue
        bin_acc = y_true[mask].mean()
        bin_conf = scores[mask].mean()
        ece += (mask.sum() / n) * abs(bin_acc - bin_conf)
    return float(ece)


def evaluate_static_rule(human_df: pd.DataFrame, v2_benchmark_path: str) -> dict:
    v2 = pd.read_csv(v2_benchmark_path)[["sample_id", "label"]].rename(columns={"label": "source_rule_label"})
    merged = human_df[~human_df["excluded_from_binary"]].merge(v2, left_on="item_id", right_on="sample_id", how="left")
    missing = merged["source_rule_label"].isna().sum()
    if missing > 0:
        print(f"[WARNING] {missing} items have no source-rule label in the v2 benchmark "
              "(e.g. temporal-collection items outside the original population) and are excluded "
              "from the static-rule comparison.", file=sys.stderr)
    merged = merged.dropna(subset=["source_rule_label"])
    return binary_rule_metrics(merged["binary_label"].to_numpy(), merged["source_rule_label"].to_numpy())


def main(release_json_path: str, sample_set: str) -> int:
    human_df = load_human_reference(release_json_path)
    n_excluded = int(human_df["excluded_from_binary"].sum())
    print(f"loaded {len(human_df)} finalized human labels for {sample_set} "
          f"({n_excluded} excluded from binary metrics: INDETERMINATE/NOT_BYTECODE_SCREENABLE)")

    v2_path = os.path.join(REPO_ROOT, "revision_v2", "data", "authguardbench_7702_v2.csv.gz")
    static_rule_result = evaluate_static_rule(human_df, v2_path)
    print("static analyzer rule vs. human reference:")
    print(json.dumps(static_rule_result, indent=2))

    print(
        "\nML model comparison (AuthGuard, Flat CNN, other baselines) is NOT run here: it "
        "requires scoring each Gold-Dev/Gold-Test item with the FROZEN final model selected "
        "in FINAL_MODEL_SELECTION.md, which is a separate, explicit step to keep this "
        "evaluation script decoupled from any specific model's inference code. Call "
        "`continuous_score_metrics(y_true, scores, threshold)` once those scores exist."
    )
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: evaluate_against_human_labels.py <release_json_path> <sample_set>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2]))
