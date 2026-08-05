#!/usr/bin/env python3
"""Family-held-out relational DCRG experiment with parameter-identical graph controls."""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time

import numpy as np
import pandas as pd
import torch
from sklearn.linear_model import LogisticRegression


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
V3 = os.path.join(REPO_ROOT, "revision_v3")
sys.path.insert(0, os.path.join(V3, "src"))

from data.loader import fold_split, load_primary_dataset  # noqa: E402
from evaluation.bootstrap_v2 import seed_aware_paired_bootstrap_ci  # noqa: E402
from evaluation.metrics import auprc, full_metrics  # noqa: E402
from models.relational_dcrg import (  # noqa: E402
    RelationalDCRG, collate_graphs, encode_graph, parameter_count,
)
from training.harness import SEEDS  # noqa: E402


VARIANTS = {
    "relational_typed": {
        "typed_edges": True, "capability_only": False, "collapse_relations": False,
    },
    "relational_untyped": {
        "typed_edges": False, "capability_only": False, "collapse_relations": True,
    },
    "relational_capability_only": {
        "typed_edges": True, "capability_only": True, "collapse_relations": False,
    },
}


def load_graphs(path: str) -> dict[str, dict]:
    records = {}
    with open(path) as handle:
        for line in handle:
            row = json.loads(line)
            records[str(row["bytecode_sha256"])] = row["dcrg"]
    return records


def batches(indices: np.ndarray, batch_size: int, rng: np.random.Generator):
    order = np.asarray(indices, dtype=np.int64).copy()
    rng.shuffle(order)
    for start in range(0, len(order), batch_size):
        yield order[start:start + batch_size]


@torch.no_grad()
def predict(model, encoded, indices, batch_size, device):
    model.eval()
    scores = []
    for start in range(0, len(indices), batch_size):
        selected = indices[start:start + batch_size]
        batch = collate_graphs(encoded[index] for index in selected).to(device)
        scores.extend(torch.sigmoid(model(batch)).cpu().numpy().tolist())
    return np.asarray(scores, dtype=np.float64)


def calibrate(validation_scores, validation_y, test_scores, seed):
    epsilon = 1e-6
    validation_logits = np.log(
        np.clip(validation_scores, epsilon, 1 - epsilon)
        / np.clip(1 - validation_scores, epsilon, 1 - epsilon)
    ).reshape(-1, 1)
    test_logits = np.log(
        np.clip(test_scores, epsilon, 1 - epsilon)
        / np.clip(1 - test_scores, epsilon, 1 - epsilon)
    ).reshape(-1, 1)
    model = LogisticRegression(C=1.0, random_state=seed)
    model.fit(validation_logits, validation_y)
    return (
        model.predict_proba(validation_logits)[:, 1],
        model.predict_proba(test_logits)[:, 1],
    )


def fit_one(encoded, labels, train_indices, validation_indices, seed, epochs,
            batch_size, device, collapse_relations=False):
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    model = RelationalDCRG(collapse_relations=collapse_relations).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    train_y = labels[train_indices]
    positive_weight = float((train_y == 0).sum() / max((train_y == 1).sum(), 1))
    loss_fn = torch.nn.BCEWithLogitsLoss(
        pos_weight=torch.tensor(positive_weight, dtype=torch.float32, device=device)
    )
    rng = np.random.default_rng(seed)
    best_state = copy.deepcopy(model.state_dict())
    best_auprc = -1.0
    best_epoch = 0
    patience = 12
    for epoch in range(1, epochs + 1):
        model.train()
        for selected in batches(train_indices, batch_size, rng):
            batch = collate_graphs(encoded[index] for index in selected).to(device)
            target = torch.tensor(labels[selected], dtype=torch.float32, device=device)
            optimizer.zero_grad(set_to_none=True)
            loss = loss_fn(model(batch), target)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            optimizer.step()
        validation_scores = predict(model, encoded, validation_indices, batch_size, device)
        current = auprc(labels[validation_indices], validation_scores)
        if current > best_auprc + 1e-5:
            best_auprc = current
            best_epoch = epoch
            best_state = copy.deepcopy(model.state_dict())
        elif epoch - best_epoch >= patience:
            break
    model.load_state_dict(best_state)
    return model, best_epoch, best_auprc


def _arrays_by_seed(frame: pd.DataFrame, model_name: str):
    subset = frame[frame["model"] == model_name]
    pivot = subset.pivot(index="sample_id", columns="seed", values="score").sort_index()
    metadata = (
        subset[["sample_id", "family_id", "label"]].drop_duplicates("sample_id")
        .set_index("sample_id").loc[pivot.index]
    )
    if pivot.isna().any().any():
        raise RuntimeError(f"incomplete OOF seed coverage for {model_name}")
    return (
        {int(seed): pivot[seed].to_numpy(dtype=np.float64) for seed in pivot.columns},
        metadata["family_id"].to_numpy(), metadata["label"].to_numpy(dtype=np.int64),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph-path", required=True)
    parser.add_argument("--results-dir", required=True)
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--batch-size", type=int, default=48)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(SEEDS))
    parser.add_argument("--folds", type=int, nargs="+", default=list(range(5)))
    args = parser.parse_args()
    os.makedirs(args.results_dir, exist_ok=True)

    primary = load_primary_dataset().reset_index(drop=True)
    primary["_row_index"] = np.arange(len(primary), dtype=np.int64)
    graph_by_hash = load_graphs(args.graph_path)
    missing = sorted(set(primary["bytecode_sha256"]) - set(graph_by_hash))
    if missing:
        raise RuntimeError(f"graph artifact misses {len(missing)} primary runtime hashes")
    labels = primary["label"].to_numpy(dtype=np.int64)
    encoded_by_variant = {
        name: [encode_graph(
                   graph_by_hash[value],
                   typed_edges=settings["typed_edges"],
                   capability_only=settings["capability_only"],
               )
               for value in primary["bytecode_sha256"]]
        for name, settings in VARIANTS.items()
    }
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[relational_dcrg] device={device}", flush=True)

    fold_rows = []
    prediction_rows = []
    start = time.time()
    for seed in args.seeds:
        for test_fold in args.folds:
            train, validation, test = fold_split(primary, test_fold)
            train_indices = train["_row_index"].to_numpy(dtype=np.int64)
            validation_indices = validation["_row_index"].to_numpy(dtype=np.int64)
            test_indices = test["_row_index"].to_numpy(dtype=np.int64)
            for model_name, encoded in encoded_by_variant.items():
                settings = VARIANTS[model_name]
                model, best_epoch, best_validation_auprc = fit_one(
                    encoded, labels, train_indices, validation_indices, seed,
                    args.epochs, args.batch_size, device,
                    collapse_relations=settings["collapse_relations"],
                )
                raw_validation = predict(
                    model, encoded, validation_indices, args.batch_size, device
                )
                raw_test = predict(model, encoded, test_indices, args.batch_size, device)
                validation_scores, test_scores = calibrate(
                    raw_validation, labels[validation_indices], raw_test, seed
                )
                metrics = full_metrics(
                    labels[test_indices], test_scores,
                    validation_scores, labels[validation_indices],
                )
                fold_rows.append({
                    "seed": seed, "test_fold": test_fold, "model": model_name,
                    "best_epoch": best_epoch,
                    "best_validation_raw_auprc": best_validation_auprc,
                    "parameter_count": parameter_count(model), **metrics,
                })
                for position, index in enumerate(test_indices):
                    row = primary.iloc[index]
                    prediction_rows.append({
                        "seed": seed, "test_fold": test_fold, "model": model_name,
                        "sample_id": row.sample_id, "family_id": row.family_id,
                        "label": int(row.label), "score": float(test_scores[position]),
                        "threshold_5pct": float(metrics["threshold_5pct"]),
                    })
                print(
                    f"[relational_dcrg] seed={seed} fold={test_fold} model={model_name} "
                    f"epoch={best_epoch} AUPRC={metrics['auprc']:.3f}", flush=True,
                )

    fold_frame = pd.DataFrame(fold_rows)
    prediction_frame = pd.DataFrame(prediction_rows)
    fold_path = os.path.join(args.results_dir, "relational_dcrg_fold_seed.csv")
    prediction_path = os.path.join(args.results_dir, "relational_dcrg_predictions.csv.gz")
    fold_frame.to_csv(fold_path, index=False)
    prediction_frame.to_csv(prediction_path, index=False, compression="gzip")

    typed, family_ids, y_true = _arrays_by_seed(prediction_frame, "relational_typed")
    comparisons = []
    for baseline in ("relational_untyped", "relational_capability_only"):
        other, other_families, other_y = _arrays_by_seed(prediction_frame, baseline)
        if not np.array_equal(family_ids, other_families) or not np.array_equal(y_true, other_y):
            raise RuntimeError("relational ablation metadata alignment changed")
        comparisons.append({
            "candidate": "relational_typed", "baseline": baseline,
            "auprc": seed_aware_paired_bootstrap_ci(
                family_ids=family_ids, y_true=y_true, scores_a_by_seed=typed,
                scores_b_by_seed=other, metric_fn=auprc, n_replicates=10000,
                seed=77032026,
            ),
        })
    report = {
        "status": "PROVISIONAL_INHERITED_LABEL_RELATIONAL_EXPERIMENT",
        "protocol": "family-grouped 5-fold outer test x 3 seeds; validation early stopping "
                    "and calibration; identical model parameterization across graph controls",
        "variants": VARIANTS,
        "parameter_counts": {
            name: int(group["parameter_count"].iloc[0])
            for name, group in fold_frame.groupby("model")
        },
        "fold_mean_metrics": {
            name: {metric: float(group[metric].mean()) for metric in (
                "auprc", "auroc", "brier", "recall_at_5pct", "observed_fpr_at_5pct"
            )}
            for name, group in fold_frame.groupby("model")
        },
        "paired_family_bootstrap": comparisons,
        "wall_seconds": time.time() - start,
        "claim_boundary": "Retain relational learning as a contribution only if the typed model "
                          "beats both graph controls and the aggregate DCRG on independent labels.",
        "artifacts": {
            "fold_seed_metrics": os.path.relpath(fold_path, REPO_ROOT),
            "predictions": os.path.relpath(prediction_path, REPO_ROOT),
        },
    }
    with open(os.path.join(args.results_dir, "relational_dcrg_report.json"), "w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    print(json.dumps(report, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
