#!/usr/bin/env python3
"""Paired family-clustered analysis for AuthGuard-Fusion versus the strongest baseline."""
from __future__ import annotations

import argparse
import hashlib
import json
import os

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

HERE = os.path.dirname(os.path.abspath(__file__))
RV2 = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(RV2, "results", "authguard_fusion")


def _seed(*parts):
    return int.from_bytes(hashlib.blake2b(":".join(map(str, parts)).encode(),
                                         digest_size=8).digest(), "little")


def metric_values(y, score, pred, weights):
    positive, negative = y == 1, y == 0
    output = {}
    if (weights * positive).sum() > 0 and (weights * negative).sum() > 0:
        output["AUPRC"] = float(average_precision_score(y, score, sample_weight=weights))
    pden = float((weights * positive).sum())
    nden = float((weights * negative).sum())
    output["Recall_05"] = float((weights * positive * pred).sum() / pden) if pden else None
    output["FPR_05"] = float((weights * negative * pred).sum() / nden) if nden else None
    return output


def paired_bootstrap(frame, candidate, baseline, condition, replicates):
    subset = frame[frame["condition"] == condition]
    a = subset[subset["model"] == candidate].set_index("sid").sort_index()
    b = subset[subset["model"] == baseline].set_index("sid").reindex(a.index)
    if len(a) == 0 or b["score"].isna().any():
        raise ValueError(f"unpaired rows for {candidate} vs {baseline} on {condition}")
    if not np.array_equal(a["y"].to_numpy(), b["y"].to_numpy()):
        raise ValueError("paired labels differ")
    families = a["family_id"].astype(str).to_numpy()
    unique = np.asarray(sorted(pd.unique(families)))
    family_index = {family: index for index, family in enumerate(unique)}
    row_family = np.asarray([family_index[family] for family in families])
    y = a["y"].to_numpy(dtype=int)
    score_a, score_b = a["score"].to_numpy(), b["score"].to_numpy()
    pred_a, pred_b = a["pred_05"].to_numpy(dtype=float), b["pred_05"].to_numpy(dtype=float)
    point_a = metric_values(y, score_a, pred_a, np.ones(len(y)))
    point_b = metric_values(y, score_b, pred_b, np.ones(len(y)))
    metric_names = sorted(metric for metric in set(point_a) & set(point_b)
                          if point_a[metric] is not None and point_b[metric] is not None)
    samples = {metric: np.empty(replicates, dtype=float) for metric in metric_names}
    rng = np.random.default_rng(_seed(candidate, baseline, condition, replicates))
    for replicate in range(replicates):
        family_weights = np.bincount(rng.integers(0, len(unique), len(unique)),
                                     minlength=len(unique))
        weights = family_weights[row_family]
        ma = metric_values(y, score_a, pred_a, weights)
        mb = metric_values(y, score_b, pred_b, weights)
        for metric in metric_names:
            samples[metric][replicate] = (
                ma[metric] - mb[metric]
                if ma.get(metric) is not None and mb.get(metric) is not None else np.nan)
    output = {"rows": len(a), "families": len(unique), "metrics": {}}
    for metric in metric_names:
        values = samples[metric]
        finite = values[np.isfinite(values)]
        delta = point_a[metric] - point_b[metric]
        output["metrics"][metric] = {
            "candidate": point_a[metric],
            "baseline": point_b[metric],
            "delta": delta,
            "CI95": [float(np.percentile(finite, 2.5)),
                     float(np.percentile(finite, 97.5))],
            "excludes_zero": bool(np.percentile(finite, 2.5) > 0 or
                                  np.percentile(finite, 97.5) < 0),
            "replicates": int(len(finite)),
        }
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", default="fusion_consistent")
    parser.add_argument("--baseline", default="hist_ngram_xgb")
    parser.add_argument("--seed", type=int, default=7702)
    parser.add_argument("--replicates", type=int, default=10_000)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if args.validate_only:
        toy = pd.DataFrame({
            "sid": [f"s{i}" for i in range(8)] * 2,
            "family_id": [f"f{i//2}" for i in range(8)] * 2,
            "y": [0, 0, 0, 0, 1, 1, 1, 1] * 2,
            "model": [args.candidate] * 8 + [args.baseline] * 8,
            "condition": ["cleanM0"] * 16,
            "score": [0.1, .2, .3, .4, .6, .7, .8, .9,
                      .2, .3, .4, .5, .5, .6, .7, .8],
            "pred_05": [0, 0, 0, 0, 1, 1, 1, 1,
                        0, 0, 0, 1, 0, 1, 1, 1],
        })
        result = paired_bootstrap(toy, args.candidate, args.baseline, "cleanM0", 100)
        print(json.dumps(result, indent=2)); return

    predictions = pd.read_csv(os.path.join(OUT, "predictions.csv.gz"))
    metrics = pd.read_csv(os.path.join(OUT, "metrics.csv"))
    predictions = predictions[predictions["seed"] == args.seed].copy()
    thresholds = (metrics[metrics["seed"] == args.seed]
                  [["seed", "fold", "model", "condition", "fpr_05"]]
                  .drop_duplicates())
    predictions = predictions.merge(thresholds,
                                    on=["seed", "fold", "model", "condition"], how="left")
    if predictions["fpr_05"].isna().any():
        raise ValueError("missing matched-FPR threshold for prediction rows")
    predictions["pred_05"] = predictions["score"] >= predictions["fpr_05"]
    conditions = sorted(set(predictions[predictions["model"] == args.candidate]["condition"]) &
                        set(predictions[predictions["model"] == args.baseline]["condition"]))
    comparisons = {
        condition: paired_bootstrap(predictions, args.candidate, args.baseline,
                                    condition, args.replicates)
        for condition in conditions
    }
    result = {
        "candidate": args.candidate,
        "baseline": args.baseline,
        "seed": args.seed,
        "conditions": comparisons,
        "claim_policy": (
            "Performance superiority requires a practically relevant positive delta whose "
            "paired family-clustered 95% interval excludes zero."
        ),
    }
    safe_candidate = args.candidate.replace("/", "_")
    result_path = os.path.join(OUT, f"paired_family_bootstrap_{safe_candidate}.json")
    report_path = os.path.join(RV2, "reports",
                               f"authguard_fusion_{safe_candidate}_decision.md")
    with open(result_path, "w") as handle:
        json.dump(result, handle, indent=2)

    clean = comparisons["cleanM0"]["metrics"]
    robust = [comparisons[name]["metrics"] for name in ("F200", "M3F200")
              if name in comparisons]
    clean_noninferior = clean["AUPRC"]["CI95"][0] >= -0.01
    robust_gain = any(metrics_["AUPRC"]["CI95"][0] > 0 or
                      metrics_["Recall_05"]["CI95"][0] > 0 for metrics_ in robust)
    performance_win = bool(clean_noninferior and robust_gain)
    lines = [
        "# AuthGuard-Fusion Contribution Decision",
        "",
        f"Candidate: `{args.candidate}`. Strongest baseline: `{args.baseline}`.",
        "",
        f"Architecture performance outcome: **{'SUPPORTED' if performance_win else 'NOT SUPPORTED'}**.",
        "",
        "This decision concerns a performance claim only. Multi-task interpretability and "
        "operational-tool claims require their separate output and runtime checks.",
        "",
        "## Paired results",
        "",
        "| Condition | Metric | Candidate | Baseline | Delta | 95% CI |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for condition, comparison in comparisons.items():
        for metric, values in comparison["metrics"].items():
            lines.append(
                f"| {condition} | {metric} | {values['candidate']:.4f} | "
                f"{values['baseline']:.4f} | {values['delta']:+.4f} | "
                f"[{values['CI95'][0]:+.4f}, {values['CI95'][1]:+.4f}] |")
    lines.extend(["", "## Claim wording", "",
                  "Use `improves` only for rows with a positive, practically meaningful delta "
                  "whose interval excludes zero. Otherwise use `is competitive with` or "
                  "`we evaluate`, as appropriate."])
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w") as handle:
        handle.write("\n".join(lines) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
