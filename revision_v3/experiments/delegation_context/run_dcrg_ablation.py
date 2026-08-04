"""Predeclared DCRG representation ablations on the frozen family-held-out folds.

These results use inherited benchmark labels and are engineering diagnostics only.  The same
driver can be rerun without refitting after human labels arrive only for prediction evaluation;
model fitting and threshold selection always remain confined to the original train/validation
folds.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
V3 = os.path.join(REPO_ROOT, "revision_v3")
sys.path.insert(0, os.path.join(V3, "src"))
sys.path.insert(0, os.path.dirname(__file__))

from analysis.delegation_context import DCRG_FEATURE_ORDER  # noqa: E402
from analysis.dcrg_feature_groups import FEATURE_GROUPS  # noqa: E402
from data.loader import fold_split, load_primary_dataset  # noqa: E402
from evaluation.bootstrap_v2 import seed_aware_paired_bootstrap_ci  # noqa: E402
from evaluation.metrics import auprc, full_metrics  # noqa: E402
from run_dcrg_fusion import calibrated_context_scores  # noqa: E402
from training.harness import SEEDS  # noqa: E402

RESULTS_DIR = os.path.join(V3, "results", "delegation_context")
FEATURE_PATH = os.path.join(RESULTS_DIR, "dcrg_primary_features.csv.gz")

def _arrays_by_seed(frame: pd.DataFrame, model_name: str, column: str):
    subset = frame[frame["model"] == model_name]
    pivot = subset.pivot(index="sample_id", columns="seed", values=column).sort_index()
    meta = (
        subset[["sample_id", "family_id", "label"]]
        .drop_duplicates("sample_id")
        .set_index("sample_id")
        .sort_index()
    )
    if list(pivot.index) != list(meta.index) or pivot.isna().any().any():
        raise RuntimeError(f"incomplete seed alignment for {model_name}/{column}")
    arrays = {
        int(seed): pivot[seed].to_numpy(dtype=np.float64) for seed in pivot.columns
    }
    return arrays, meta["family_id"].to_numpy(), meta["label"].to_numpy(dtype=np.int64)


def main() -> int:
    primary = load_primary_dataset()
    features = pd.read_csv(FEATURE_PATH)
    merged = primary.merge(
        features[["sample_id", *DCRG_FEATURE_ORDER]],
        on="sample_id",
        how="left",
        validate="one_to_one",
    )
    if len(merged) != len(primary) or merged[list(DCRG_FEATURE_ORDER)].isna().any().any():
        raise RuntimeError("full DCRG feature coverage is required for ablation")

    fold_rows = []
    prediction_rows = []
    for seed in SEEDS:
        for test_fold in range(5):
            train, validation, test = fold_split(merged, test_fold)
            train_y = train["label"].to_numpy(dtype=np.int64)
            validation_y = validation["label"].to_numpy(dtype=np.int64)
            test_y = test["label"].to_numpy(dtype=np.int64)
            for model_name, feature_names in FEATURE_GROUPS.items():
                validation_scores, test_scores, _, _ = calibrated_context_scores(
                    train[list(feature_names)].to_numpy(dtype=np.float32),
                    train_y,
                    validation[list(feature_names)].to_numpy(dtype=np.float32),
                    validation_y,
                    test[list(feature_names)].to_numpy(dtype=np.float32),
                    seed,
                )
                metrics = full_metrics(test_y, test_scores, validation_scores, validation_y)
                fold_rows.append({
                    "seed": seed,
                    "test_fold": test_fold,
                    "model": model_name,
                    "n_features": len(feature_names),
                    **metrics,
                })
                for position, row in enumerate(test.itertuples(index=False)):
                    prediction_rows.append({
                        "seed": seed,
                        "test_fold": test_fold,
                        "model": model_name,
                        "sample_id": row.sample_id,
                        "family_id": row.family_id,
                        "label": int(row.label),
                        "score": float(test_scores[position]),
                        "threshold_5pct": float(metrics["threshold_5pct"]),
                    })
                print(
                    f"[dcrg_ablation] seed={seed} fold={test_fold} model={model_name} "
                    f"AUPRC={metrics['auprc']:.3f}",
                    flush=True,
                )

    fold_frame = pd.DataFrame(fold_rows)
    prediction_frame = pd.DataFrame(prediction_rows)
    fold_frame.to_csv(os.path.join(RESULTS_DIR, "dcrg_ablation_fold_seed.csv"), index=False)
    prediction_frame.to_csv(
        os.path.join(RESULTS_DIR, "dcrg_ablation_predictions.csv.gz"),
        index=False,
        compression="gzip",
    )

    comparisons = []
    full_arrays, family_ids, labels = _arrays_by_seed(prediction_frame, "dcrg_full", "score")
    for baseline in FEATURE_GROUPS:
        if baseline == "dcrg_full":
            continue
        baseline_arrays, current_families, current_labels = _arrays_by_seed(
            prediction_frame, baseline, "score"
        )
        if not (
            np.array_equal(family_ids, current_families)
            and np.array_equal(labels, current_labels)
        ):
            raise RuntimeError("ablation prediction metadata alignment changed")
        comparisons.append({
            "candidate": "dcrg_full",
            "baseline": baseline,
            "auprc": seed_aware_paired_bootstrap_ci(
                family_ids=family_ids,
                y_true=labels,
                scores_a_by_seed=full_arrays,
                scores_b_by_seed=baseline_arrays,
                metric_fn=auprc,
                n_replicates=10000,
                seed=77032026,
            ),
        })

    mean_metrics = {}
    for model_name, group in fold_frame.groupby("model"):
        mean_metrics[model_name] = {
            metric: float(group[metric].mean())
            for metric in (
                "auprc", "auroc", "brier", "recall_at_5pct", "observed_fpr_at_5pct"
            )
        }
    report = {
        "status": "PROVISIONAL_INHERITED_LABEL_ABLATION",
        "feature_schema": "dcrg-1.1",
        "feature_groups": {key: list(value) for key, value in FEATURE_GROUPS.items()},
        "fold_mean_metrics": mean_metrics,
        "paired_family_bootstrap": comparisons,
        "claim_boundary": (
            "These ablations test representation behavior against inherited labels only; "
            "they must be reevaluated against human-final and post-cutoff labels."
        ),
    }
    report_path = os.path.join(RESULTS_DIR, "dcrg_ablation_report.json")
    with open(report_path, "w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    print(json.dumps(report, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
