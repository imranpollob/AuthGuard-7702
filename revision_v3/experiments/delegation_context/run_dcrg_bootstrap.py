"""Corrected seed-aware paired family bootstrap for DCRG fusion comparisons."""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
V3 = os.path.join(REPO_ROOT, "revision_v3")
sys.path.insert(0, os.path.join(V3, "src"))

from evaluation.bootstrap_v2 import seed_aware_paired_bootstrap_ci  # noqa: E402
from evaluation.metrics import auprc, auroc  # noqa: E402

RESULTS_DIR = os.path.join(V3, "results", "delegation_context")


def recall_from_flags(y_true, flags) -> float:
    y = np.asarray(y_true)
    pred = np.asarray(flags) >= 0.5
    positives = y == 1
    return float((pred & positives).sum() / positives.sum()) if positives.sum() else 0.0


def fpr_from_flags(y_true, flags) -> float:
    y = np.asarray(y_true)
    pred = np.asarray(flags) >= 0.5
    negatives = y == 0
    return float((pred & negatives).sum() / negatives.sum()) if negatives.sum() else 0.0


def arrays_by_seed(frame: pd.DataFrame, value_column: str):
    pivot = frame.pivot(index="sample_id", columns="seed", values=value_column).sort_index()
    meta = (frame[["sample_id", "family_id", "label"]]
            .drop_duplicates("sample_id").set_index("sample_id").sort_index())
    if list(pivot.index) != list(meta.index) or pivot.isna().any().any():
        raise RuntimeError(f"cannot align complete seed arrays for {value_column}")
    return ({int(seed): pivot[seed].to_numpy(dtype=np.float64) for seed in pivot.columns},
            meta["family_id"].to_numpy(), meta["label"].to_numpy(dtype=np.int64))


def main() -> int:
    predictions = pd.read_csv(os.path.join(RESULTS_DIR, "dcrg_fusion_predictions.csv.gz"))
    fold_metrics = pd.read_csv(os.path.join(RESULTS_DIR, "dcrg_fusion_fold_seed.csv"))
    threshold_names = {
        "sequence": "sequence_threshold_5pct",
        "dcrg": "dcrg_threshold_5pct",
    }
    for model_name, output_name in threshold_names.items():
        if output_name in predictions.columns:
            continue
        thresholds = fold_metrics[fold_metrics["model"] == model_name][
            ["seed", "test_fold", "threshold_5pct"]
        ].rename(columns={"threshold_5pct": output_name})
        predictions = predictions.merge(
            thresholds, on=["seed", "test_fold"], how="left", validate="many_to_one"
        )
    predictions["sequence_flag"] = (
        predictions["sequence_score"] >= predictions["sequence_threshold_5pct"]
    ).astype(float)
    predictions["dcrg_flag"] = (
        predictions["dcrg_score"] >= predictions["dcrg_threshold_5pct"]
    ).astype(float)
    predictions["fusion_flag"] = (
        predictions["fusion_score"] >= predictions["fusion_threshold_5pct"]
    ).astype(float)

    arrays = {}
    family_ids = labels = None
    for column in (
        "sequence_score", "dcrg_score", "fusion_score",
        "sequence_flag", "dcrg_flag", "fusion_flag",
    ):
        arrays[column], current_families, current_labels = arrays_by_seed(predictions, column)
        if family_ids is None:
            family_ids, labels = current_families, current_labels
        elif not (np.array_equal(family_ids, current_families) and
                  np.array_equal(labels, current_labels)):
            raise RuntimeError("prediction metadata alignment changed between score columns")

    comparisons = []
    for candidate, baseline in (("fusion", "sequence"), ("fusion", "dcrg")):
        result = {"candidate": candidate, "baseline": baseline}
        for metric_name, candidate_col, baseline_col, metric_fn in (
            ("auprc", f"{candidate}_score", f"{baseline}_score", auprc),
            ("auroc", f"{candidate}_score", f"{baseline}_score", auroc),
            ("recall_at_5pct", f"{candidate}_flag", f"{baseline}_flag", recall_from_flags),
            ("observed_fpr_at_5pct", f"{candidate}_flag", f"{baseline}_flag", fpr_from_flags),
        ):
            result[metric_name] = seed_aware_paired_bootstrap_ci(
                family_ids=family_ids,
                y_true=labels,
                scores_a_by_seed=arrays[candidate_col],
                scores_b_by_seed=arrays[baseline_col],
                metric_fn=metric_fn,
                n_replicates=10000,
                seed=77032026,
            )
        comparisons.append(result)

    report = {
        "status": "PROVISIONAL_LEGACY_LABEL_EVALUATION",
        "comparisons": comparisons,
        "interpretation_boundary": (
            "Intervals quantify performance against inherited benchmark labels, which partly "
            "encode static-analysis evidence. They do not establish independent semantic "
            "validity; human-final and post-cutoff evaluations remain mandatory."
        ),
    }
    out_path = os.path.join(RESULTS_DIR, "dcrg_fusion_bootstrap.json")
    with open(out_path, "w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    print(json.dumps(report, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
