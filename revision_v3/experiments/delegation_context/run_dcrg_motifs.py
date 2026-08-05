#!/usr/bin/env python3
"""Evaluate entrypoint-local DCRG motifs against aggregate and type-erased controls."""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
V3 = os.path.join(REPO_ROOT, "revision_v3")
sys.path.insert(0, os.path.join(V3, "src"))
sys.path.insert(0, os.path.dirname(__file__))

from analysis.dcrg_motifs import (  # noqa: E402
    TYPED_MOTIF_FEATURES, UNTYPED_MOTIF_FEATURES, extract_motifs,
)
from analysis.delegation_context import DCRG_FEATURE_ORDER  # noqa: E402
from data.loader import fold_split, load_primary_dataset  # noqa: E402
from evaluation.bootstrap_v2 import seed_aware_paired_bootstrap_ci  # noqa: E402
from evaluation.metrics import auprc, full_metrics  # noqa: E402
from run_dcrg_fusion import calibrated_context_scores  # noqa: E402
from training.harness import SEEDS  # noqa: E402


def load_graphs(path: str) -> dict[str, dict]:
    with open(path) as handle:
        return {
            row["bytecode_sha256"]: row["dcrg"] for row in map(json.loads, handle)
        }


def arrays_by_seed(frame: pd.DataFrame, model_name: str):
    subset = frame[frame["model"] == model_name]
    pivot = subset.pivot(index="sample_id", columns="seed", values="score").sort_index()
    metadata = (
        subset[["sample_id", "family_id", "label"]].drop_duplicates("sample_id")
        .set_index("sample_id").loc[pivot.index]
    )
    return (
        {int(seed): pivot[seed].to_numpy(dtype=np.float64) for seed in pivot.columns},
        metadata["family_id"].to_numpy(), metadata["label"].to_numpy(dtype=np.int64),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph-path", required=True)
    parser.add_argument("--aggregate-features", required=True)
    parser.add_argument("--results-dir", required=True)
    args = parser.parse_args()
    os.makedirs(args.results_dir, exist_ok=True)
    primary = load_primary_dataset()
    graphs = load_graphs(args.graph_path)
    aggregate = pd.read_csv(args.aggregate_features)
    motif_rows = []
    for row in primary.itertuples(index=False):
        motif_rows.append({"sample_id": row.sample_id, **extract_motifs(graphs[row.bytecode_sha256])})
    motifs = pd.DataFrame(motif_rows)
    motif_path = os.path.join(args.results_dir, "dcrg_motif_features.csv.gz")
    motifs.to_csv(motif_path, index=False, compression="gzip")
    merged = primary.merge(
        aggregate[["sample_id", *DCRG_FEATURE_ORDER]], on="sample_id", validate="one_to_one"
    ).merge(motifs, on="sample_id", validate="one_to_one")

    groups = {
        "aggregate_dcrg": tuple(DCRG_FEATURE_ORDER),
        "typed_motifs_only": tuple(TYPED_MOTIF_FEATURES),
        "aggregate_plus_untyped_motifs": tuple(DCRG_FEATURE_ORDER) + tuple(UNTYPED_MOTIF_FEATURES),
        "aggregate_plus_typed_motifs": tuple(DCRG_FEATURE_ORDER) + tuple(TYPED_MOTIF_FEATURES),
    }
    fold_rows = []
    prediction_rows = []
    for seed in SEEDS:
        for test_fold in range(5):
            train, validation, test = fold_split(merged, test_fold)
            train_y = train["label"].to_numpy(dtype=np.int64)
            validation_y = validation["label"].to_numpy(dtype=np.int64)
            test_y = test["label"].to_numpy(dtype=np.int64)
            for model_name, features in groups.items():
                validation_scores, test_scores, _, _ = calibrated_context_scores(
                    train[list(features)].to_numpy(dtype=np.float32), train_y,
                    validation[list(features)].to_numpy(dtype=np.float32), validation_y,
                    test[list(features)].to_numpy(dtype=np.float32), seed,
                )
                metrics = full_metrics(test_y, test_scores, validation_scores, validation_y)
                fold_rows.append({
                    "seed": seed, "test_fold": test_fold, "model": model_name,
                    "n_features": len(features), **metrics,
                })
                for position, row in enumerate(test.itertuples(index=False)):
                    prediction_rows.append({
                        "seed": seed, "test_fold": test_fold, "model": model_name,
                        "sample_id": row.sample_id, "family_id": row.family_id,
                        "label": int(row.label), "score": float(test_scores[position]),
                        "threshold_5pct": float(metrics["threshold_5pct"]),
                    })
                print(
                    f"[dcrg_motifs] seed={seed} fold={test_fold} model={model_name} "
                    f"AUPRC={metrics['auprc']:.3f}", flush=True,
                )

    fold_frame = pd.DataFrame(fold_rows)
    prediction_frame = pd.DataFrame(prediction_rows)
    fold_path = os.path.join(args.results_dir, "dcrg_motif_fold_seed.csv")
    prediction_path = os.path.join(args.results_dir, "dcrg_motif_predictions.csv.gz")
    fold_frame.to_csv(fold_path, index=False)
    prediction_frame.to_csv(prediction_path, index=False, compression="gzip")
    candidate, families, labels = arrays_by_seed(prediction_frame, "aggregate_plus_typed_motifs")
    comparisons = []
    for baseline in groups:
        if baseline == "aggregate_plus_typed_motifs":
            continue
        other, other_families, other_labels = arrays_by_seed(prediction_frame, baseline)
        if not np.array_equal(families, other_families) or not np.array_equal(labels, other_labels):
            raise RuntimeError("motif prediction metadata alignment changed")
        comparisons.append({
            "candidate": "aggregate_plus_typed_motifs", "baseline": baseline,
            "auprc": seed_aware_paired_bootstrap_ci(
                family_ids=families, y_true=labels, scores_a_by_seed=candidate,
                scores_b_by_seed=other, metric_fn=auprc, n_replicates=10000,
                seed=77032026,
            ),
        })
    report = {
        "status": "PROVISIONAL_INHERITED_LABEL_MOTIF_EXPERIMENT",
        "feature_groups": {name: list(features) for name, features in groups.items()},
        "fold_mean_metrics": {
            name: {metric: float(group[metric].mean()) for metric in (
                "auprc", "auroc", "brier", "recall_at_5pct", "observed_fpr_at_5pct"
            )}
            for name, group in fold_frame.groupby("model")
        },
        "paired_family_bootstrap": comparisons,
        "claim_boundary": (
            "Motif learning is retained only if typed entrypoint-local relations improve over "
            "the aggregate and type-erased controls and transfer to independent labels."
        ),
        "artifacts": {
            "motif_features": os.path.relpath(motif_path, REPO_ROOT),
            "fold_seed_metrics": os.path.relpath(fold_path, REPO_ROOT),
            "predictions": os.path.relpath(prediction_path, REPO_ROOT),
        },
    }
    with open(os.path.join(args.results_dir, "dcrg_motif_report.json"), "w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    print(json.dumps(report, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
