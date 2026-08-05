"""Strict human-final evaluation for the frozen AuthGuard review samples.

The command refuses partial releases, unknown labels, duplicate items, prediction gaps, and
single-class binary evaluations.  Scores and operating thresholds come from the already-frozen
family-held-out prediction artifact; human labels are never used for training, calibration, or
threshold selection.

Example (after annotation and adjudication are complete)::

    python3 revision_v3/experiments/human_label_evaluation/evaluate_against_human_labels.py \
        revision_v3/annotation_app/release_gold_test.json gold_test
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Iterable

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
V3 = os.path.join(REPO_ROOT, "revision_v3")
sys.path.insert(0, os.path.join(V3, "src"))
sys.path.insert(0, os.path.join(V3, "annotation_app"))

from constants import NEGATIVE_LABEL, POSITIVE_LABEL  # noqa: E402
from analysis.dcrg_feature_groups import FEATURE_GROUPS  # noqa: E402
from evaluation.bootstrap_v2 import seed_aware_paired_bootstrap_ci  # noqa: E402
from evaluation.gold_test_provenance import (  # noqa: E402
    validate_gold_test_scoring_provenance,
)
from evaluation.metrics import metrics_at_threshold  # noqa: E402
from evaluation.postcutoff_provenance import (  # noqa: E402
    validate_postcutoff_scoring_provenance,
)
from evaluation.selective_policy import selective_decisions, selective_policy_metrics  # noqa: E402

EXCLUDED_FROM_BINARY = {"INDETERMINATE", "NOT_BYTECODE_SCREENABLE"}
LABEL_TO_BINARY = {NEGATIVE_LABEL: 0, POSITIVE_LABEL: 1}
ALLOWED_FINAL_LABELS = set(LABEL_TO_BINARY) | EXCLUDED_FROM_BINARY
MODEL_COLUMNS = {
    "sequence": ("sequence_score", "sequence_threshold_5pct"),
    "dcrg": ("dcrg_score", "dcrg_threshold_5pct"),
    "dcrg_sequence_noisy_or": ("fusion_score", "fusion_threshold_5pct"),
}
OPTIONAL_MODEL_COLUMNS = {
    "hist_ngram_xgb": ("hist_ngram_xgb_score", "hist_ngram_xgb_threshold_5pct"),
    "dcrg_project_balanced": (
        "dcrg_project_balanced_score", "dcrg_project_balanced_threshold_5pct"
    ),
}
ABLATION_MODELS = tuple(FEATURE_GROUPS)


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_release(release_json_path: str) -> pd.DataFrame:
    with open(release_json_path) as handle:
        rows = json.load(handle)
    if not isinstance(rows, list) or not rows:
        raise ValueError(
            f"{release_json_path} contains zero finalized items -- do not fabricate or "
            "estimate a human-label result"
        )
    frame = pd.DataFrame(rows)
    required = {"item_id", "final_label"}
    missing_columns = required - set(frame.columns)
    if missing_columns:
        raise ValueError(f"human release is missing required columns: {sorted(missing_columns)}")
    if frame["item_id"].isna().any() or frame["item_id"].duplicated().any():
        raise ValueError("human release contains missing or duplicate item_id values")
    unknown = set(frame["final_label"].dropna().astype(str)) - ALLOWED_FINAL_LABELS
    if unknown:
        raise ValueError(f"human release contains unknown final labels: {sorted(unknown)}")
    return frame


def load_human_reference(
    release_json_path: str,
    *,
    expected_item_ids: Iterable[str] | None = None,
    require_complete: bool = False,
) -> pd.DataFrame:
    """Load finalized labels and optionally enforce the frozen sample manifest exactly."""
    frame = _read_release(release_json_path)
    if expected_item_ids is not None:
        expected = {str(value) for value in expected_item_ids}
        observed = set(frame["item_id"].astype(str))
        missing = sorted(expected - observed)
        unexpected = sorted(observed - expected)
        if missing or unexpected:
            raise ValueError(
                "human release does not exactly match the frozen manifest: "
                f"missing={len(missing)}, unexpected={len(unexpected)}"
            )
    unresolved = frame["final_label"].isna()
    if require_complete and unresolved.any():
        raise ValueError(
            f"human release has {int(unresolved.sum())} unresolved items; final evaluation "
            "requires adjudication or an explicit non-binary final label for every item"
        )
    if unresolved.any():
        print(
            f"[WARNING] excluding {int(unresolved.sum())} unresolved human items",
            file=sys.stderr,
        )
    frame = frame[~unresolved].copy()
    frame["binary_label"] = frame["final_label"].map(LABEL_TO_BINARY)
    frame["excluded_from_binary"] = frame["final_label"].isin(EXCLUDED_FROM_BINARY)
    return frame


def validate_review_protocol(human_df: pd.DataFrame, sample_set: str) -> None:
    """Enforce the predeclared dual-review rule where it is mandatory."""
    if sample_set not in {"pilot", "gold_test", "postcutoff"}:
        return
    required = {"n_primary_reviews", "resolution"}
    missing = required - set(human_df.columns)
    if missing:
        raise ValueError(
            f"{sample_set} release cannot prove dual review; missing {sorted(missing)}"
        )
    review_counts = pd.to_numeric(human_df["n_primary_reviews"], errors="coerce")
    insufficient = review_counts.isna() | (review_counts < 2)
    invalid_resolution = ~human_df["resolution"].isin({"unanimous", "adjudicated"})
    if insufficient.any() or invalid_resolution.any():
        raise ValueError(
            f"{sample_set} violates the dual-review/adjudication protocol: "
            f"insufficient_primary_reviews={int(insufficient.sum())}, "
            f"invalid_resolution={int(invalid_resolution.sum())}"
        )


def validate_agreement_report(
    agreement_report_path: str | None,
    *,
    expected_item_ids: Iterable[str],
    sample_set: str,
) -> dict | None:
    """Require a sample-bound reliability report for mandatory dual-review sets."""
    mandatory = sample_set in {"pilot", "gold_test", "postcutoff"}
    if not agreement_report_path:
        if mandatory:
            raise ValueError(f"{sample_set} requires a locked agreement/adjudication report")
        return None
    with open(agreement_report_path) as handle:
        report = json.load(handle)
    expected_ids = sorted(str(value) for value in expected_item_ids)
    expected_hash = hashlib.sha256("\n".join(expected_ids).encode()).hexdigest()
    if report.get("sample_set") != sample_set:
        raise ValueError("agreement report sample_set mismatch")
    if report.get("item_ids_sha256") != expected_hash:
        raise ValueError("agreement report item IDs do not match the frozen manifest")
    if int(report.get("n_manifest_items", -1)) != len(expected_ids):
        raise ValueError("agreement report manifest count mismatch")
    if mandatory:
        if report.get("status") != "COMPLETE_DUAL_REVIEW_AND_ADJUDICATION":
            raise ValueError(f"{sample_set} agreement/adjudication report is not complete")
        if int(report.get("n_exactly_dual_reviewed", -1)) != len(expected_ids):
            raise ValueError(f"{sample_set} does not have exactly two primary reviews per item")
        if int(report.get("n_pending_adjudications", -1)) != 0:
            raise ValueError(f"{sample_set} has pending adjudications")
        if int(report.get("n_primary_disagreements", -1)) != int(
            report.get("n_adjudicated_disagreements", -2)
        ):
            raise ValueError(f"{sample_set} disagreements are not all singly adjudicated")
    return {
        **report,
        "agreement_report_sha256": _sha256_file(agreement_report_path),
    }


def binary_rule_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    y_true = np.asarray(y_true, dtype=np.int64)
    y_pred = np.asarray(y_pred, dtype=np.int64)
    tp = int(((y_pred == 1) & (y_true == 1)).sum())
    fp = int(((y_pred == 1) & (y_true == 0)).sum())
    tn = int(((y_pred == 0) & (y_true == 0)).sum())
    fn = int(((y_pred == 0) & (y_true == 1)).sum())
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    specificity = tn / (tn + fp) if (tn + fp) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "n": int(len(y_true)),
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "specificity": specificity,
        "fpr": fpr,
        "f1": f1,
        "balanced_accuracy": (recall + specificity) / 2,
    }


def expected_calibration_error(y_true: np.ndarray, scores: np.ndarray, n_bins: int = 10) -> float:
    bins = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for index in range(n_bins):
        upper = scores < bins[index + 1] if index < n_bins - 1 else scores <= bins[index + 1]
        mask = (scores >= bins[index]) & upper
        if not mask.any():
            continue
        ece += (mask.sum() / len(y_true)) * abs(y_true[mask].mean() - scores[mask].mean())
    return float(ece)


def continuous_score_metrics(
    y_true: np.ndarray,
    scores: np.ndarray,
    threshold: float | np.ndarray,
) -> dict:
    y_true = np.asarray(y_true, dtype=np.int64)
    scores = np.asarray(scores, dtype=np.float64)
    if len(np.unique(y_true)) != 2:
        raise ValueError(
            "continuous human-label metrics require both bounded-negative and UNSAFE items"
        )
    operating = metrics_at_threshold(y_true, scores, threshold)
    return {
        "auprc": float(average_precision_score(y_true, scores)),
        "auroc": float(roc_auc_score(y_true, scores)),
        "brier": float(brier_score_loss(y_true, scores)),
        "expected_calibration_error": expected_calibration_error(y_true, scores),
        **operating,
    }


def evaluate_static_rule(human_df: pd.DataFrame, benchmark_path: str) -> dict:
    benchmark = pd.read_csv(benchmark_path, usecols=["sample_id", "label"])
    benchmark = benchmark.rename(columns={"label": "source_rule_label"})
    binary = human_df[~human_df["excluded_from_binary"]]
    merged = binary.merge(
        benchmark,
        left_on="item_id",
        right_on="sample_id",
        how="left",
        validate="one_to_one",
    )
    if merged["source_rule_label"].isna().any():
        raise ValueError("one or more frozen human-review items lack a source-rule label")
    return binary_rule_metrics(
        merged["binary_label"].to_numpy(), merged["source_rule_label"].to_numpy()
    )


def _mean_numeric(records: list[dict]) -> dict:
    keys = sorted(set.intersection(*(set(record) for record in records)))
    return {
        key: float(np.mean([record[key] for record in records]))
        for key in keys
        if key != "seed" and all(isinstance(record[key], (int, float)) for record in records)
    }


def _recall_from_flags(y_true, flags) -> float:
    y_true = np.asarray(y_true)
    flags = np.asarray(flags) >= 0.5
    positive = y_true == 1
    return float((flags & positive).sum() / positive.sum()) if positive.any() else 0.0


def _bootstrap_auprc(y_true, scores) -> float:
    """AP convention for rare degenerate family resamples, without sklearn warnings.

    Candidate and baseline receive the same resample, so an all-negative or all-positive draw
    contributes a paired delta of zero instead of being silently dropped.
    """
    y_true = np.asarray(y_true)
    if not (y_true == 1).any():
        return 0.0
    if not (y_true == 0).any():
        return 1.0
    return float(average_precision_score(y_true, scores))


def _fpr_from_flags(y_true, flags) -> float:
    y_true = np.asarray(y_true)
    flags = np.asarray(flags) >= 0.5
    negative = y_true == 0
    return float((flags & negative).sum() / negative.sum()) if negative.any() else 0.0


def evaluate_dcrg_predictions(
    human_df: pd.DataFrame,
    predictions: pd.DataFrame,
    *,
    bootstrap_replicates: int = 10000,
) -> dict:
    """Evaluate all three frozen views against binary human labels without refitting."""
    required = {
        "seed", "sample_id", "family_id", "coverage",
        *(column for pair in MODEL_COLUMNS.values() for column in pair),
    }
    missing = required - set(predictions.columns)
    if missing:
        raise ValueError(f"prediction artifact is missing columns: {sorted(missing)}")

    binary = human_df[~human_df["excluded_from_binary"]][["item_id", "binary_label"]].copy()
    if len(binary) == 0 or binary["binary_label"].nunique() != 2:
        raise ValueError(
            "human-final evaluation requires at least one bounded-negative and one UNSAFE item"
        )
    selected = predictions[predictions["sample_id"].isin(binary["item_id"])].copy()
    expected_ids = set(binary["item_id"])
    seeds = sorted(int(value) for value in selected["seed"].unique())
    if not seeds:
        raise ValueError("no frozen predictions match the binary human-label items")
    for seed in seeds:
        seed_rows = selected[selected["seed"] == seed]
        observed = set(seed_rows["sample_id"])
        if observed != expected_ids or seed_rows["sample_id"].duplicated().any():
            raise ValueError(
                f"prediction coverage mismatch for seed {seed}: expected {len(expected_ids)} "
                f"unique items, observed {len(observed)}"
            )

    selected = selected.merge(
        binary,
        left_on="sample_id",
        right_on="item_id",
        how="left",
        validate="many_to_one",
    ).drop(columns="item_id")
    selected = selected.sort_values(["sample_id", "seed"]).reset_index(drop=True)

    available_model_columns = dict(MODEL_COLUMNS)
    for model_name, columns in OPTIONAL_MODEL_COLUMNS.items():
        if all(column in predictions.columns for column in columns):
            available_model_columns[model_name] = columns
        elif any(column in predictions.columns for column in columns):
            raise ValueError(f"prediction artifact contains an incomplete {model_name} baseline")

    model_reports: dict[str, dict] = {}
    array_by_model: dict[str, dict[int, np.ndarray]] = {}
    flag_by_model: dict[str, dict[int, np.ndarray]] = {}
    for model_name, (score_column, threshold_column) in available_model_columns.items():
        per_seed = []
        array_by_model[model_name] = {}
        flag_by_model[model_name] = {}
        for seed in seeds:
            frame = selected[selected["seed"] == seed].sort_values("sample_id")
            scores = frame[score_column].to_numpy(dtype=np.float64)
            thresholds = frame[threshold_column].to_numpy(dtype=np.float64)
            labels = frame["binary_label"].to_numpy(dtype=np.int64)
            metrics = continuous_score_metrics(labels, scores, thresholds)
            per_seed.append({"seed": seed, **metrics})
            array_by_model[model_name][seed] = scores
            flag_by_model[model_name][seed] = (scores >= thresholds).astype(np.float64)
        model_reports[model_name] = {
            "per_seed": per_seed,
            "mean_across_seeds": _mean_numeric(per_seed),
            "threshold_provenance": "validation-derived, family-held-out, item-specific",
        }

    policy_per_seed = []
    for seed in seeds:
        frame = selected[selected["seed"] == seed].sort_values("sample_id")
        decisions = selective_decisions(
            frame["fusion_score"].to_numpy(),
            frame["fusion_threshold_5pct"].to_numpy(),
            frame["coverage"].to_numpy(),
        )
        metrics = selective_policy_metrics(frame["binary_label"].to_numpy(dtype=np.int64), decisions)
        low_mask = decisions == "LOW_OBSERVED_RISK"
        metrics["n_low_observed_risk"] = int(low_mask.sum())
        metrics["n_unsafe_within_low_observed_risk"] = int(
            ((frame["binary_label"].to_numpy(dtype=np.int64) == 1) & low_mask).sum()
        )
        policy_per_seed.append({"seed": seed, **metrics})

    meta = selected.drop_duplicates("sample_id").sort_values("sample_id")
    family_ids = meta["family_id"].to_numpy()
    labels = meta["binary_label"].to_numpy(dtype=np.int64)
    comparisons = []
    comparison_specs = []
    if "hist_ngram_xgb" in available_model_columns:
        comparison_specs.extend([
            ("dcrg", "hist_ngram_xgb", "SECONDARY_PERFORMANCE"),
            ("dcrg", "sequence", "SECONDARY_PERFORMANCE"),
        ])
    if "dcrg_project_balanced" in available_model_columns:
        comparison_specs.append(
            ("dcrg_project_balanced", "dcrg", "EXPLORATORY_TRAINING_INTERVENTION")
        )
    comparison_specs.extend([
        ("dcrg_sequence_noisy_or", "sequence", "EXPLORATORY_FUSION"),
        ("dcrg_sequence_noisy_or", "dcrg", "EXPLORATORY_FUSION"),
    ])
    for candidate, baseline, tier in comparison_specs:
        comparison = {"candidate": candidate, "baseline": baseline, "endpoint_tier": tier}
        for metric_name, candidate_arrays, baseline_arrays, metric_fn in (
            ("auprc", array_by_model[candidate], array_by_model[baseline], _bootstrap_auprc),
            ("recall_at_5pct", flag_by_model[candidate], flag_by_model[baseline], _recall_from_flags),
            ("observed_fpr_at_5pct", flag_by_model[candidate], flag_by_model[baseline], _fpr_from_flags),
        ):
            comparison[metric_name] = seed_aware_paired_bootstrap_ci(
                family_ids=family_ids,
                y_true=labels,
                scores_a_by_seed=candidate_arrays,
                scores_b_by_seed=baseline_arrays,
                metric_fn=metric_fn,
                n_replicates=bootstrap_replicates,
                seed=77032026,
            )
        comparisons.append(comparison)

    return {
        "models": model_reports,
        "coverage_aware_selective_policy": {
            "per_seed": policy_per_seed,
            "mean_across_seeds": _mean_numeric(policy_per_seed),
            "decision_semantics": (
                "WARN / LOW_OBSERVED_RISK / DEFER; incomplete coverage cannot produce LOW"
            ),
        },
        "paired_family_bootstrap": comparisons,
        "n_bootstrap_replicates": bootstrap_replicates,
    }


def _ablation_long_form(predictions: pd.DataFrame) -> pd.DataFrame:
    """Accept the historical long artifact or the locked post-cutoff wide artifact."""
    long_required = {"seed", "sample_id", "family_id", "model", "score", "threshold_5pct"}
    if long_required.issubset(predictions.columns):
        return predictions[list(long_required)].copy()
    wide_required = {
        "seed", "sample_id", "family_id",
        *(f"{model}_{suffix}" for model in ABLATION_MODELS for suffix in (
            "score", "threshold_5pct"
        )),
    }
    if missing := wide_required - set(predictions.columns):
        raise ValueError(f"ablation prediction artifact is missing columns: {sorted(missing)}")
    rows = []
    for model in ABLATION_MODELS:
        frame = predictions[[
            "seed", "sample_id", "family_id", f"{model}_score",
            f"{model}_threshold_5pct",
        ]].rename(columns={
            f"{model}_score": "score",
            f"{model}_threshold_5pct": "threshold_5pct",
        })
        frame["model"] = model
        rows.append(frame)
    return pd.concat(rows, ignore_index=True)


def evaluate_dcrg_ablation_predictions(
    human_df: pd.DataFrame,
    predictions: pd.DataFrame,
    *,
    bootstrap_replicates: int = 10000,
) -> dict:
    """Falsification test for DCRG representation novelty on independent labels."""
    binary = human_df[~human_df["excluded_from_binary"]][
        ["item_id", "binary_label"]
    ].copy()
    if len(binary) == 0 or binary["binary_label"].nunique() != 2:
        raise ValueError("DCRG ablation evaluation requires both human binary classes")
    long = _ablation_long_form(predictions)
    long = long[long["sample_id"].isin(binary["item_id"])].copy()
    expected_ids = set(binary["item_id"])
    models = set(long["model"].astype(str))
    if models != set(ABLATION_MODELS):
        raise ValueError(
            "ablation model coverage mismatch: "
            f"missing={sorted(set(ABLATION_MODELS)-models)}, "
            f"extra={sorted(models-set(ABLATION_MODELS))}"
        )
    seeds = sorted(int(value) for value in long["seed"].unique())
    if not seeds:
        raise ValueError("ablation predictions contain no seeds")
    for model in ABLATION_MODELS:
        for seed in seeds:
            frame = long[(long["model"] == model) & (long["seed"] == seed)]
            observed = set(frame["sample_id"])
            if observed != expected_ids or frame["sample_id"].duplicated().any():
                raise ValueError(f"ablation coverage mismatch for {model}/seed {seed}")

    merged = long.merge(
        binary, left_on="sample_id", right_on="item_id", how="left", validate="many_to_one"
    ).drop(columns="item_id")
    model_reports = {}
    score_arrays: dict[str, dict[int, np.ndarray]] = {}
    flag_arrays: dict[str, dict[int, np.ndarray]] = {}
    for model in ABLATION_MODELS:
        per_seed = []
        score_arrays[model] = {}
        flag_arrays[model] = {}
        for seed in seeds:
            frame = merged[
                (merged["model"] == model) & (merged["seed"] == seed)
            ].sort_values("sample_id")
            scores = frame["score"].to_numpy(dtype=np.float64)
            thresholds = frame["threshold_5pct"].to_numpy(dtype=np.float64)
            labels = frame["binary_label"].to_numpy(dtype=np.int64)
            per_seed.append({
                "seed": seed, **continuous_score_metrics(labels, scores, thresholds)
            })
            score_arrays[model][seed] = scores
            flag_arrays[model][seed] = (scores >= thresholds).astype(np.float64)
        model_reports[model] = {
            "per_seed": per_seed,
            "mean_across_seeds": _mean_numeric(per_seed),
            "feature_names": list(FEATURE_GROUPS[model]),
            "threshold_provenance": "validation-derived after applicable family holds",
        }

    meta = merged[merged["model"] == "dcrg_full"].drop_duplicates(
        "sample_id"
    ).sort_values("sample_id")
    family_ids = meta["family_id"].to_numpy()
    labels = meta["binary_label"].to_numpy(dtype=np.int64)
    comparisons = []
    for baseline in ABLATION_MODELS:
        if baseline == "dcrg_full":
            continue
        comparison = {"candidate": "dcrg_full", "baseline": baseline}
        for metric_name, full_arrays, baseline_arrays, metric_fn in (
            ("auprc", score_arrays["dcrg_full"], score_arrays[baseline], _bootstrap_auprc),
            ("recall_at_5pct", flag_arrays["dcrg_full"], flag_arrays[baseline], _recall_from_flags),
            ("observed_fpr_at_5pct", flag_arrays["dcrg_full"], flag_arrays[baseline], _fpr_from_flags),
        ):
            comparison[metric_name] = seed_aware_paired_bootstrap_ci(
                family_ids=family_ids,
                y_true=labels,
                scores_a_by_seed=full_arrays,
                scores_b_by_seed=baseline_arrays,
                metric_fn=metric_fn,
                n_replicates=bootstrap_replicates,
                seed=77032026,
            )
        comparisons.append(comparison)
    return {
        "status": "INDEPENDENT_LABEL_DCRG_REPRESENTATION_ABLATION",
        "models": model_reports,
        "paired_family_bootstrap": comparisons,
        "n_bootstrap_replicates": bootstrap_replicates,
        "novelty_decision_rule": (
            "Typed/authority-relative representation superiority may be claimed only for a "
            "predeclared endpoint whose full-minus-ablation interval supports the direction."
        ),
    }


def run_evaluation(
    release_json_path: str,
    sample_set: str,
    manifest_path: str,
    predictions_path: str,
    *,
    bootstrap_replicates: int = 10000,
    holdout_plan_path: str | None = None,
    training_manifest_path: str | None = None,
    sample_lock_path: str | None = None,
    agreement_report_path: str | None = None,
    ablation_predictions_path: str | None = None,
    gold_test_scoring_lock_path: str | None = None,
) -> dict:
    manifest = pd.read_csv(manifest_path, usecols=["item_id"])
    scoring_provenance = None
    if sample_set == "postcutoff":
        missing_paths = [
            name for name, value in (
                ("holdout_plan_path", holdout_plan_path),
                ("training_manifest_path", training_manifest_path),
                ("sample_lock_path", sample_lock_path),
            ) if not value
        ]
        if missing_paths:
            raise ValueError(
                "post-cutoff evaluation requires locked scoring provenance: "
                + ", ".join(missing_paths)
            )
        predictions, scoring_provenance = validate_postcutoff_scoring_provenance(
            review_manifest_path=manifest_path,
            predictions_path=predictions_path,
            holdout_plan_path=str(holdout_plan_path),
            training_manifest_path=str(training_manifest_path),
            sample_lock_path=str(sample_lock_path),
            preregistration_path=os.path.join(
                V3, "protocols", "final_evaluation_preregistration_v1.json"
            ),
            dependence_clusters_path=os.path.join(
                os.path.dirname(manifest_path), "postcutoff_dependence_clusters.csv"
            ),
            dependence_report_path=os.path.join(
                os.path.dirname(manifest_path), "postcutoff_dependence_clusters_report.json"
            ),
            canonical_dataset_path=os.path.join(
                REPO_ROOT, "revision_v2", "data", "authguardbench_7702_v2.csv.gz"
            ),
            artifact_root=REPO_ROOT,
        )
    elif sample_set == "gold_test":
        if not ablation_predictions_path or not gold_test_scoring_lock_path:
            raise ValueError(
                "Gold-Test evaluation requires its pre-label scoring lock and frozen ablations"
            )
        predictions, ablation_predictions, scoring_provenance = (
            validate_gold_test_scoring_provenance(
                manifest_path=manifest_path,
                fusion_predictions_path=predictions_path,
                ablation_predictions_path=ablation_predictions_path,
                lock_path=gold_test_scoring_lock_path,
                artifact_root=REPO_ROOT,
            )
        )
    else:
        predictions = pd.read_csv(predictions_path)
    if sample_set == "postcutoff":
        ablation_predictions = predictions
    elif sample_set == "gold_test":
        pass
    elif ablation_predictions_path:
        ablation_predictions = pd.read_csv(ablation_predictions_path)
    else:
        ablation_predictions = None
    agreement = validate_agreement_report(
        agreement_report_path,
        expected_item_ids=manifest["item_id"],
        sample_set=sample_set,
    )
    human = load_human_reference(
        release_json_path,
        expected_item_ids=manifest["item_id"],
        require_complete=True,
    )
    validate_review_protocol(human, sample_set)
    evaluation_human = human
    excluded_from_scoring: list[str] = []
    if sample_set == "postcutoff":
        excluded_from_scoring = list(scoring_provenance.get("excluded_item_ids", []))
        evaluation_human = human[~human["item_id"].isin(excluded_from_scoring)].copy()
        if set(evaluation_human["item_id"]) != set(predictions["sample_id"]):
            raise ValueError("post-cutoff scoring population differs from audited eligible labels")
    benchmark_path = os.path.join(V3, "..", "revision_v2", "data", "authguardbench_7702_v2.csv.gz")
    label_counts = human["final_label"].value_counts().sort_index().to_dict()
    return {
        "status": "HUMAN_FINAL_EVALUATION",
        "sample_set": sample_set,
        "n_manifest_items": int(len(manifest)),
        "n_finalized_items": int(len(human)),
        "n_scored_finalized_items": int(len(evaluation_human)),
        "n_binary_items": int((~evaluation_human["excluded_from_binary"]).sum()),
        "excluded_from_scoring_item_ids": excluded_from_scoring,
        "final_label_counts": {str(key): int(value) for key, value in label_counts.items()},
        "inter_rater_reliability": agreement,
        "label_exclusion_rule": (
            "INDETERMINATE and NOT_BYTECODE_SCREENABLE are reported but excluded "
            "from bounded-negative/UNSAFE metrics"
        ),
        "source_static_rule": (
            evaluate_static_rule(human, benchmark_path)
            if sample_set != "postcutoff"
            else {"status": "NOT_AVAILABLE_FOR_POSTCUTOFF_POPULATION"}
        ),
        "scoring_provenance": scoring_provenance,
        "dcrg_evaluation": evaluate_dcrg_predictions(
            evaluation_human, predictions, bootstrap_replicates=bootstrap_replicates
        ),
        "dcrg_representation_ablation": (
            evaluate_dcrg_ablation_predictions(
                evaluation_human, ablation_predictions, bootstrap_replicates=bootstrap_replicates
            )
            if ablation_predictions is not None else None
        ),
        "claim_boundary": (
            "Post-cutoff scores are valid only for the audited project-family population and "
            "the locked retraining protocol; they are not prevalence estimates."
            if sample_set == "postcutoff"
            else "Gold-Test is a frozen audit sample from the canonical corpus, not a post-cutoff "
            "population. Scores are family-held-out and labels are independent, but external "
            "validity still requires post-cutoff project families."
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release_json_path")
    parser.add_argument("sample_set", choices=("pilot", "gold_dev", "gold_test", "postcutoff"))
    parser.add_argument("--manifest")
    parser.add_argument(
        "--predictions",
        default=None,
    )
    parser.add_argument("--holdout-plan")
    parser.add_argument("--training-manifest")
    parser.add_argument("--sample-lock")
    parser.add_argument("--agreement-report")
    parser.add_argument("--ablation-predictions")
    parser.add_argument("--gold-test-scoring-lock")
    parser.add_argument("--output")
    parser.add_argument("--bootstrap-replicates", type=int, default=10000)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.sample_set == "postcutoff":
        postcutoff_dir = os.path.join(V3, "results", "postcutoff_snapshot")
        manifest_path = args.manifest or os.path.join(
            postcutoff_dir, "postcutoff_review_manifest.csv"
        )
        predictions_path = args.predictions
        if not predictions_path:
            raise ValueError(
                "post-cutoff evaluation requires --predictions from the locked retraining run"
            )
        holdout_plan_path = args.holdout_plan or os.path.join(
            postcutoff_dir, "postcutoff_family_holdout_plan.json"
        )
        sample_lock_path = args.sample_lock or os.path.join(
            postcutoff_dir, "postcutoff_review_lock.json"
        )
    elif args.sample_set == "gold_test":
        manifest_path = args.manifest or os.path.join(
            V3, "human_eval", "gold_test_manifest.csv"
        )
        predictions_path = args.predictions or os.path.join(
            V3, "results", "human_final", "gold_test_frozen_predictions.csv.gz"
        )
        holdout_plan_path = None
        sample_lock_path = None
    else:
        manifest_path = args.manifest or os.path.join(
            V3, "human_eval", f"{args.sample_set}_manifest.csv"
        )
        predictions_path = args.predictions or os.path.join(
            V3, "results", "delegation_context", "dcrg_fusion_predictions.csv.gz"
        )
        holdout_plan_path = None
        sample_lock_path = None
    agreement_report_path = args.agreement_report
    if agreement_report_path is None and args.sample_set in {"pilot", "gold_test", "postcutoff"}:
        agreement_report_path = os.path.join(
            V3, "annotation_app", f"agreement_{args.sample_set}.json"
        )
    output_path = args.output or os.path.join(
        V3, "results", "human_final", f"dcrg_{args.sample_set}_evaluation.json"
    )
    report = run_evaluation(
        args.release_json_path,
        args.sample_set,
        manifest_path,
        predictions_path,
        bootstrap_replicates=args.bootstrap_replicates,
        holdout_plan_path=holdout_plan_path,
        training_manifest_path=args.training_manifest,
        sample_lock_path=sample_lock_path,
        agreement_report_path=agreement_report_path,
        ablation_predictions_path=(
            args.ablation_predictions
            or (
                os.path.join(
                    V3, "results", "human_final",
                    "gold_test_frozen_ablation_predictions.csv.gz"
                )
                if args.sample_set == "gold_test" else None
            )
        ),
        gold_test_scoring_lock_path=(
            args.gold_test_scoring_lock
            or (
                os.path.join(
                    V3, "results", "human_final", "gold_test_scoring_lock.json"
                )
                if args.sample_set == "gold_test" else None
            )
        ),
    )
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    print(json.dumps(report, indent=2, sort_keys=True))
    print(f"wrote {output_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
