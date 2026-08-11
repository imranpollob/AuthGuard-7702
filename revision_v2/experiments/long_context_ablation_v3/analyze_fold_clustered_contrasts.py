#!/usr/bin/env python3
"""Fold-stratified family bootstrap matching the reported v3 metric aggregation."""
from __future__ import annotations

import argparse
import os

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

HERE = os.path.dirname(os.path.abspath(__file__))
RV2 = os.path.abspath(os.path.join(HERE, "..", ".."))
DEFAULT_OUT = os.path.join(RV2, "results", "long_context_ablation_v3")
CONTRASTS = {
    "coverage": ("chunk_attention_control_16384", "chunk_attention_control_2048"),
    "attention": ("chunk_attention_control_16384", "chunk_mean_control_16384"),
    "hierarchy": ("chunk_attention_control_16384", "flat_control_16384"),
}


def score_metric(frame, metric):
    if metric == "AUPRC":
        return float(average_precision_score(frame["y"], frame["calibrated_score"]))
    positives = frame["y"] == 1
    return float(frame.loc[positives, "predicted_05"].mean())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=DEFAULT_OUT)
    parser.add_argument("--replicates", type=int, default=2_000)
    args = parser.parse_args()
    output = os.path.abspath(args.output_dir)
    predictions = pd.read_csv(os.path.join(output, "predictions.csv.gz"))
    metrics = pd.read_csv(os.path.join(output, "metrics.csv"))
    thresholds = metrics[[
        "model", "seed", "fold", "condition", "threshold_05"
    ]].drop_duplicates()
    predictions = predictions.merge(
        thresholds,
        on=["model", "seed", "fold", "condition"],
        how="left",
        validate="many_to_one",
    )
    predictions["predicted_05"] = (
        predictions["calibrated_score"] >= predictions["threshold_05"]).astype(int)
    rng = np.random.default_rng(7702)
    rows = []
    for condition in ("M0", "F200"):
        for contrast, (left_model, right_model) in CONTRASTS.items():
            pair = predictions[
                (predictions["condition"] == condition)
                & predictions["model"].isin([left_model, right_model])
            ]
            for metric in ("AUPRC", "Recall_05"):
                aligned, family_rows, observed = {}, {}, []
                for seed in (7702, 7703, 7704):
                    for fold in range(5):
                        cell = pair[
                            (pair["seed"] == seed) & (pair["fold"] == fold)
                        ]
                        left = cell[cell["model"] == left_model].sort_values(
                            "sid").reset_index(drop=True)
                        right = cell[cell["model"] == right_model].sort_values(
                            "sid").reset_index(drop=True)
                        if not left["sid"].equals(right["sid"]):
                            raise RuntimeError(
                                f"pairing failed {contrast} seed={seed} fold={fold}")
                        aligned[(seed, fold, left_model)] = left
                        aligned[(seed, fold, right_model)] = right
                        observed.append(
                            score_metric(left, metric) - score_metric(right, metric))
                        if fold not in family_rows:
                            families = left["family_id"].astype(str).to_numpy()
                            family_rows[fold] = {
                                family: np.flatnonzero(families == family)
                                for family in sorted(set(families))
                            }
                bootstrap = np.zeros(args.replicates, dtype=float)
                for rep in range(args.replicates):
                    sampled_by_fold = {}
                    for fold in range(5):
                        families = list(family_rows[fold])
                        sampled = rng.choice(families, size=len(families), replace=True)
                        sampled_by_fold[fold] = np.concatenate([
                            family_rows[fold][family] for family in sampled
                        ])
                    deltas = []
                    for seed in (7702, 7703, 7704):
                        for fold in range(5):
                            indices = sampled_by_fold[fold]
                            left = aligned[(seed, fold, left_model)].iloc[indices]
                            right = aligned[(seed, fold, right_model)].iloc[indices]
                            deltas.append(
                                score_metric(left, metric) - score_metric(right, metric))
                    bootstrap[rep] = float(np.mean(deltas))
                rows.append({
                    "contrast": contrast,
                    "condition": condition,
                    "metric": metric,
                    "left_model": left_model,
                    "right_model": right_model,
                    "delta": float(np.mean(observed)),
                    "ci95_low": float(np.percentile(bootstrap, 2.5)),
                    "ci95_high": float(np.percentile(bootstrap, 97.5)),
                    "probability_positive": float((bootstrap > 0).mean()),
                    "replicates": args.replicates,
                    "aggregation": "fold_mean_then_seed_mean",
                    "cluster": "family_id_within_fold",
                })
    result = pd.DataFrame(rows)
    result.to_csv(
        os.path.join(output, "fold_clustered_contrasts.csv"), index=False)
    lines = [
        "# Long-context v3 fold-clustered contribution decision",
        "",
        "Intervals mirror the reported fold-mean then seed-mean aggregation.",
        "",
        "| Gate | Condition | Metric | Delta | 95% CI | Decision |",
        "|---|---|---|---:|---:|---|",
    ]
    for row in result.to_dict("records"):
        if row["ci95_low"] > 0:
            decision = "SUPPORTED"
        elif row["ci95_high"] < 0:
            decision = "NOT SUPPORTED"
        else:
            decision = "INCONCLUSIVE"
        lines.append(
            f"| {row['contrast']} | {row['condition']} | {row['metric']} | "
            f"{row['delta']:+.4f} | [{row['ci95_low']:+.4f}, "
            f"{row['ci95_high']:+.4f}] | {decision} |"
        )
    lines.append("")
    with open(
            os.path.join(output, "FOLD_CLUSTERED_CONTRIBUTION_DECISION.md"),
            "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))
    print(f"V3_FOLD_CLUSTERED_ANALYSIS_READY rows={len(result)} output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

