#!/usr/bin/env python3
"""Paired confirmatory analysis for AuthGuard-MSP on untouched folds 1--4."""
from __future__ import annotations

import argparse
import os

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

HERE = os.path.dirname(os.path.abspath(__file__))
RV2 = os.path.abspath(os.path.join(HERE, "..", ".."))
DEFAULT_OUT = os.path.join(RV2, "results", "multiscale_confirmation_v1")
V3_OUT = os.path.join(RV2, "results", "long_context_ablation_v3")
MSP = "authguard_msp_16384"
COMPARATORS = (
    "chunk_attention_control_16384",
    "flat_control_16384",
    "authguard_reference_16384",
)
FOLDS = (1, 2, 3, 4)


def with_decisions(predictions, metrics):
    thresholds = metrics[[
        "model", "seed", "fold", "condition", "threshold_05"
    ]].drop_duplicates()
    output = predictions.merge(
        thresholds,
        on=["model", "seed", "fold", "condition"],
        how="left",
        validate="many_to_one",
    )
    if output["threshold_05"].isna().any():
        raise RuntimeError("missing fold-specific 5% threshold")
    output["predicted_05"] = (
        output["calibrated_score"] >= output["threshold_05"]).astype(int)
    return output


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

    msp_predictions = with_decisions(
        pd.read_csv(os.path.join(output, "predictions.csv.gz")),
        pd.read_csv(os.path.join(output, "metrics.csv")),
    )
    v3_predictions = with_decisions(
        pd.read_csv(os.path.join(V3_OUT, "predictions.csv.gz")),
        pd.read_csv(os.path.join(V3_OUT, "metrics.csv")),
    )
    v3_predictions = v3_predictions[
        v3_predictions["model"].isin(COMPARATORS)
        & v3_predictions["fold"].isin(FOLDS)
    ]
    combined = pd.concat([msp_predictions, v3_predictions], ignore_index=True)
    if set(combined["fold"].unique()) != set(FOLDS):
        raise RuntimeError("confirmation data must contain exactly folds 1--4")

    rng = np.random.default_rng(7702)
    rows = []
    for condition in ("M0", "F200"):
        condition_frame = combined[combined["condition"] == condition]
        for comparator in COMPARATORS:
            pair = condition_frame[
                condition_frame["model"].isin([MSP, comparator])
            ]
            for metric in ("AUPRC", "Recall_05"):
                observed_deltas = []
                aligned_by_seed_fold = {}
                family_rows = {}
                for seed in sorted(pair["seed"].unique()):
                    for fold in FOLDS:
                        cell = pair[
                            (pair["seed"] == seed) & (pair["fold"] == fold)
                        ]
                        left = cell[cell["model"] == MSP].sort_values("sid").reset_index(drop=True)
                        right = cell[cell["model"] == comparator].sort_values("sid").reset_index(drop=True)
                        if not left["sid"].equals(right["sid"]):
                            raise RuntimeError(
                                f"prediction pairing failed seed={seed} fold={fold}")
                        if not left["family_id"].equals(right["family_id"]):
                            raise RuntimeError("family pairing failed")
                        aligned_by_seed_fold[(int(seed), fold, MSP)] = left
                        aligned_by_seed_fold[(int(seed), fold, comparator)] = right
                        observed_deltas.append(
                            score_metric(left, metric) - score_metric(right, metric))
                        if fold not in family_rows:
                            family_ids = left["family_id"].astype(str).to_numpy()
                            family_rows[fold] = {
                                family: np.flatnonzero(family_ids == family)
                                for family in sorted(set(family_ids))
                            }

                bootstrap = np.zeros(args.replicates, dtype=float)
                for rep in range(args.replicates):
                    sampled_by_fold = {}
                    for fold in FOLDS:
                        families = list(family_rows[fold])
                        sampled = rng.choice(families, size=len(families), replace=True)
                        sampled_by_fold[fold] = np.concatenate(
                            [family_rows[fold][family] for family in sampled])
                    replicate_deltas = []
                    for seed in sorted(pair["seed"].unique()):
                        for fold in FOLDS:
                            indices = sampled_by_fold[fold]
                            left = aligned_by_seed_fold[(int(seed), fold, MSP)].iloc[indices]
                            right = aligned_by_seed_fold[
                                (int(seed), fold, comparator)].iloc[indices]
                            replicate_deltas.append(
                                score_metric(left, metric) - score_metric(right, metric))
                    bootstrap[rep] = float(np.mean(replicate_deltas))
                rows.append({
                    "condition": condition,
                    "metric": metric,
                    "left_model": MSP,
                    "right_model": comparator,
                    "delta": float(np.mean(observed_deltas)),
                    "ci95_low": float(np.percentile(bootstrap, 2.5)),
                    "ci95_high": float(np.percentile(bootstrap, 97.5)),
                    "probability_positive": float((bootstrap > 0).mean()),
                    "replicates": args.replicates,
                    "confirmation_folds": "1,2,3,4",
                    "cluster": "family_id_within_fold",
                })
    result = pd.DataFrame(rows)
    result.to_csv(os.path.join(output, "confirmation_bootstrap.csv"), index=False)

    lines = [
        "# AuthGuard-MSP confirmation decision",
        "",
        "All decisions use only outer test folds 1--4. Fold 0 is development-only.",
        "",
        "| Condition | Metric | Comparator | Delta | 95% CI | Decision |",
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
            f"| {row['condition']} | {row['metric']} | {row['right_model']} | "
            f"{row['delta']:+.4f} | [{row['ci95_low']:+.4f}, "
            f"{row['ci95_high']:+.4f}] | {decision} |"
        )
    lines.extend([
        "",
        "The primary novelty decision is clean AUPRC versus the 16K attention control.",
        "Superiority over the 16K flat control is required for a predictive hierarchy claim.",
        "",
    ])
    with open(os.path.join(output, "CONFIRMATION_DECISION.md"), "w",
              encoding="utf-8") as handle:
        handle.write("\n".join(lines))
    print(f"MSP_CONFIRMATION_ANALYSIS_READY rows={len(result)} output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

