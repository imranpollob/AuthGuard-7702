"""Development-only test of a statistically risk-gated DCRG decision contract.

WARN uses the existing validation-derived nominal-5%-FPR threshold. LOW_OBSERVED_RISK uses a
separate threshold selected only from COMPLETE validation items: among all lower score prefixes,
choose the largest whose one-sided Clopper-Pearson upper confidence bound on unsafe prevalence
does not exceed the target risk. Everything between the thresholds, and every incomplete item,
is DEFER.

The inherited source-rule labels fit thresholds. Provisional Gold-Test labels are used only as a
distribution-shift diagnostic and never as human evidence or for threshold selection.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from scipy.stats import beta

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
V3 = os.path.join(REPO_ROOT, "revision_v3")
sys.path.insert(0, os.path.join(V3, "src"))
sys.path.insert(0, os.path.join(V3, "experiments", "delegation_context"))

from analysis.dcrg_feature_groups import FEATURE_GROUPS  # noqa: E402
from data.loader import fold_split, load_primary_dataset  # noqa: E402
from evaluation.metrics import threshold_at_nominal_fpr  # noqa: E402
from run_dcrg_fusion import calibrated_context_scores  # noqa: E402
from training.harness import SEEDS  # noqa: E402

FEATURE_PATH = os.path.join(
    V3, "results", "delegation_context", "dcrg_primary_features.csv.gz"
)
PROXY_LABEL_PATH = os.path.join(
    V3, "results", "llm_provisional_opus5", "gold_test_labels.json"
)
OUTPUT_DIR = os.path.join(V3, "results", "selective_policy_path")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "risk_controlled_dcrg_policy.json")
PREDICTION_PATH = os.path.join(OUTPUT_DIR, "risk_controlled_dcrg_predictions.csv.gz")
RISK_TARGETS = (0.05, 0.10, 0.20)
BOUND_FAILURE_PROBABILITY = 0.05


def clopper_pearson_upper(n_unsafe: int, n_total: int, *, delta: float = 0.05) -> float:
    """One-sided (1-delta) exact binomial upper confidence bound."""
    if n_total < 0 or not 0 <= n_unsafe <= n_total:
        raise ValueError("invalid binomial counts")
    if not 0 < delta < 1:
        raise ValueError("delta must be in (0,1)")
    if n_total == 0 or n_unsafe == n_total:
        return 1.0
    return float(beta.ppf(1.0 - delta, n_unsafe + 1, n_total - n_unsafe))


def select_low_risk_threshold(
    scores: np.ndarray,
    labels: np.ndarray,
    complete: np.ndarray,
    *,
    risk_target: float,
    delta: float = BOUND_FAILURE_PROBABILITY,
) -> dict:
    """Select the largest COMPLETE lower-score prefix passing the risk upper bound."""
    scores = np.asarray(scores, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.int64)
    complete = np.asarray(complete, dtype=bool)
    if not (len(scores) == len(labels) == len(complete)):
        raise ValueError("score, label, and coverage arrays must align")
    if not 0 < risk_target < 1:
        raise ValueError("risk_target must be in (0,1)")
    eligible = pd.DataFrame({"score": scores[complete], "label": labels[complete]})
    eligible = eligible.sort_values("score", kind="mergesort")
    best = None
    for threshold, prefix in eligible.groupby("score", sort=True):
        through_threshold = eligible[eligible["score"] <= threshold]
        n_total = int(len(through_threshold))
        n_unsafe = int(through_threshold["label"].sum())
        upper = clopper_pearson_upper(n_unsafe, n_total, delta=delta)
        if upper <= risk_target:
            best = {
                "threshold": float(threshold),
                "n_validation_low": n_total,
                "n_validation_unsafe": n_unsafe,
                "empirical_validation_risk": n_unsafe / n_total,
                "risk_upper_bound": upper,
            }
    return best or {
        "threshold": None,
        "n_validation_low": 0,
        "n_validation_unsafe": 0,
        "empirical_validation_risk": None,
        "risk_upper_bound": None,
    }


def policy_decisions(
    scores: np.ndarray,
    coverage: np.ndarray,
    *,
    warning_threshold: float,
    low_threshold: float | None,
) -> np.ndarray:
    scores = np.asarray(scores, dtype=np.float64)
    coverage = np.asarray(coverage, dtype=str)
    decisions = np.full(len(scores), "DEFER", dtype=object)
    if low_threshold is not None:
        decisions[(coverage == "COMPLETE") & (scores <= low_threshold)] = (
            "LOW_OBSERVED_RISK"
        )
    decisions[scores >= warning_threshold] = "WARN"
    return decisions


def decision_metrics(labels: np.ndarray, decisions: np.ndarray) -> dict:
    labels = np.asarray(labels, dtype=np.int64)
    decisions = np.asarray(decisions, dtype=str)
    low = decisions == "LOW_OBSERVED_RISK"
    warn = decisions == "WARN"
    negative = labels == 0
    positive = labels == 1
    n_low = int(low.sum())
    n_low_unsafe = int((low & positive).sum())
    return {
        "n": int(len(labels)),
        "n_warn": int(warn.sum()),
        "n_low_observed_risk": n_low,
        "n_defer": int((decisions == "DEFER").sum()),
        "warn_recall": float((warn & positive).sum() / positive.sum()) if positive.any() else None,
        "warn_fpr": float((warn & negative).sum() / negative.sum()) if negative.any() else None,
        "low_coverage": n_low / len(labels) if len(labels) else 0.0,
        "low_unsafe_count": n_low_unsafe,
        "low_empirical_risk": n_low_unsafe / n_low if n_low else None,
        "low_risk_upper_bound_95pct": (
            clopper_pearson_upper(n_low_unsafe, n_low) if n_low else None
        ),
        "defer_rate": float((decisions == "DEFER").mean()) if len(labels) else 0.0,
    }


def _mean_optional(records: list[dict], key: str) -> float | None:
    values = [record[key] for record in records if record.get(key) is not None]
    return float(np.mean(values)) if values else None


def summarize(records: list[dict]) -> dict:
    keys = (
        "n_warn", "n_low_observed_risk", "n_defer", "warn_recall", "warn_fpr",
        "low_coverage", "low_unsafe_count", "low_empirical_risk",
        "low_risk_upper_bound_95pct", "defer_rate",
    )
    return {key: _mean_optional(records, key) for key in keys}


def _proxy_label_map() -> dict[str, int]:
    with open(PROXY_LABEL_PATH) as handle:
        payload = json.load(handle)
    if payload.get("STATUS") != "PROVISIONAL_PENDING_HUMAN_REVIEW":
        raise ValueError("unexpected Gold-Test proxy-label status")
    mapping = {}
    for row in payload["records"]:
        label = row.get("llm_provisional_label")
        if label in {"SAFE", "UNSAFE"}:
            mapping[str(row["item_id"])] = int(label == "UNSAFE")
    return mapping


def main() -> int:
    primary = load_primary_dataset()
    features = pd.read_csv(FEATURE_PATH)
    feature_names = list(FEATURE_GROUPS["dcrg_full"])
    merged = primary.merge(
        features[["sample_id", "coverage", *feature_names]],
        on="sample_id", how="left", validate="one_to_one",
    )
    if merged[feature_names].isna().any().any():
        raise ValueError("DCRG features are incomplete")
    proxy_labels = _proxy_label_map()
    prediction_rows = []
    threshold_rows = []
    for seed in SEEDS:
        for test_fold in range(5):
            train, validation, test = fold_split(merged, test_fold)
            validation_labels = validation["label"].to_numpy(dtype=np.int64)
            validation_scores, test_scores, _, _ = calibrated_context_scores(
                train[feature_names].to_numpy(dtype=np.float32),
                train["label"].to_numpy(dtype=np.int64),
                validation[feature_names].to_numpy(dtype=np.float32),
                validation_labels,
                test[feature_names].to_numpy(dtype=np.float32),
                seed,
            )
            warning_threshold = threshold_at_nominal_fpr(
                validation_scores, validation_labels, 0.05
            )
            validation_complete = validation["coverage"].eq("COMPLETE").to_numpy()
            threshold_by_target = {
                target: select_low_risk_threshold(
                    validation_scores,
                    validation_labels,
                    validation_complete,
                    risk_target=target,
                )
                for target in RISK_TARGETS
            }
            threshold_rows.append({
                "seed": seed,
                "test_fold": test_fold,
                "warning_threshold_5pct_fpr": float(warning_threshold),
                "low_thresholds": {
                    str(target): result for target, result in threshold_by_target.items()
                },
            })
            for position, row in enumerate(test.itertuples(index=False)):
                record = {
                    "seed": seed,
                    "test_fold": test_fold,
                    "sample_id": str(row.sample_id),
                    "family_id": str(row.family_id),
                    "source_label": int(row.label),
                    "proxy_label": proxy_labels.get(str(row.sample_id)),
                    "coverage": str(row.coverage),
                    "dcrg_score": float(test_scores[position]),
                    "warning_threshold_5pct_fpr": float(warning_threshold),
                }
                for target, result in threshold_by_target.items():
                    record[f"low_threshold_risk_{target}"] = result["threshold"]
                prediction_rows.append(record)
            print(f"[risk_policy] seed={seed} fold={test_fold} complete", flush=True)

    predictions = pd.DataFrame(prediction_rows)
    target_reports = {}
    for target in RISK_TARGETS:
        threshold_column = f"low_threshold_risk_{target}"
        source_records = []
        proxy_records = []
        for seed in SEEDS:
            seed_rows = predictions[predictions["seed"] == seed].copy()
            decisions = np.concatenate([
                policy_decisions(
                    fold_rows["dcrg_score"].to_numpy(),
                    fold_rows["coverage"].to_numpy(),
                    warning_threshold=float(fold_rows["warning_threshold_5pct_fpr"].iloc[0]),
                    low_threshold=(
                        None if fold_rows[threshold_column].isna().all()
                        else float(fold_rows[threshold_column].dropna().iloc[0])
                    ),
                )
                for _, fold_rows in seed_rows.groupby("test_fold", sort=True)
            ])
            # groupby concatenation follows fold order; align labels using the same ordering.
            ordered = pd.concat(
                [rows for _, rows in seed_rows.groupby("test_fold", sort=True)],
                ignore_index=True,
            )
            source_records.append({
                "seed": seed,
                **decision_metrics(ordered["source_label"].to_numpy(), decisions),
            })
            proxy_mask = ordered["proxy_label"].notna().to_numpy()
            proxy_records.append({
                "seed": seed,
                **decision_metrics(
                    ordered.loc[proxy_mask, "proxy_label"].to_numpy(dtype=np.int64),
                    decisions[proxy_mask],
                ),
            })
        target_reports[str(target)] = {
            "inherited_outer_test": {
                "per_seed": source_records,
                "mean_across_seeds": summarize(source_records),
            },
            "gold_test_proxy_distribution_shift": {
                "per_seed": proxy_records,
                "mean_across_seeds": summarize(proxy_records),
            },
        }

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    predictions.to_csv(
        PREDICTION_PATH, index=False,
        compression={"method": "gzip", "mtime": 0}, lineterminator="\n",
    )
    report = {
        "status": "DEVELOPMENT_ONLY_RISK_CONTROLLED_POLICY_EXPERIMENT",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "model": "dcrg_full",
        "risk_targets": list(RISK_TARGETS),
        "bound": {
            "method": "one-sided Clopper-Pearson upper confidence bound",
            "failure_probability": BOUND_FAILURE_PROBABILITY,
            "selection_population": "COMPLETE validation items only",
        },
        "warning_threshold": "validation-derived nominal 5% FPR",
        "threshold_fits": threshold_rows,
        "results": target_reports,
        "claim_boundary": (
            "Thresholds use inherited source-rule labels. Proxy labels are a post-selection "
            "distribution-shift diagnostic, not human evidence. A final claim requires a fresh, "
            "untouched independently labeled population."
        ),
    }
    with open(OUTPUT_PATH, "w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    print(json.dumps(report, indent=2, sort_keys=True), flush=True)
    print(f"wrote {OUTPUT_PATH}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
