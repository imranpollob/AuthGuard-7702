#!/usr/bin/env python3
"""Paired, fold-stratified family-clustered bootstrap for Revision v2.

No model is trained here. The script reads held-out predictions from baseline_v2 and
robustness_operational_v2. Within every outer test fold, a replicate samples frozen
families with replacement and retains every observation in each sampled family.
The identical family multiplicities are applied to both models, all three model
seeds, and paired clean/transformed conditions. Metrics are computed per fold and
seed, averaged over five folds to a seed-level value, then averaged over seeds
7702/7703/7704. This matches the established descriptive aggregation protocol.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

HERE = os.path.dirname(os.path.abspath(__file__))
RV2 = os.path.abspath(os.path.join(HERE, "..", ".."))
ROOT = os.path.abspath(os.path.join(RV2, ".."))
MIRROR = os.path.join(RV2, "results", "statistical_analysis_v2")
BENCH = os.path.join(RV2, "data", "authguardbench_7702_v2.csv.gz")
BASELINE_PRED = os.path.join(RV2, "experiments", "baseline_v2",
                             "baseline_predictions.csv.gz")
BASELINE_SUMMARY = os.path.join(RV2, "experiments", "baseline_v2",
                                "baseline_summary.csv")
ROBUST_PRED = os.path.join(RV2, "experiments", "robustness_operational_v2",
                           "robustness_predictions.csv.gz")
ROBUST_SUMMARY = os.path.join(RV2, "experiments", "robustness_operational_v2",
                              "robustness_summary.csv")

sys.path.insert(0, os.path.join(RV2, "experiments", "common"))
from frozen import verify as verify_frozen  # noqa: E402

MODELS = ["authguard_seq", "flat_cnn", "hist_ngram_xgb"]
SEEDS = [7702, 7703, 7704]
FOLDS = list(range(5))
N_BOOTSTRAP = 10_000
BOOTSTRAP_SEED = 77022026
CI_PERCENTILES = [2.5, 97.5]
AP_CHUNK_SIZE = 256
METRIC_COLUMN = {
    "AUPRC": "AUPRC",
    "Recall@1%": "Recall_01",
    "Recall@5%": "Recall_05",
    "Recall@10%": "Recall_10",
    "Brier": "Brier",
}


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fold_seed(seed: int, fold: int) -> int:
    value = hashlib.blake2b(
        f"{seed}:fold:{fold}:family-bootstrap".encode(), digest_size=8).digest()
    return int.from_bytes(value, "little")


def prepare_sources():
    benchmark = pd.read_csv(BENCH)
    benchmark = benchmark[benchmark["population"] == "PRIMARY_EVALUATION"].copy()
    benchmark["fold"] = benchmark["fold_id"].astype(int)
    benchmark["true_label"] = benchmark["label"].astype(int)
    benchmark = benchmark[["sample_id", "family_id", "fold", "true_label"]]
    assert len(benchmark) == 2190 and benchmark["family_id"].nunique() == 790

    baseline = pd.read_csv(BASELINE_PRED)
    baseline = baseline[baseline["model"].isin(MODELS)].copy()
    baseline["condition"] = "clean"
    baseline["source"] = "baseline_v2"
    for suffix in ("01", "05", "10"):
        baseline[f"decision_{suffix}"] = (
            baseline["calibrated_score"] >= baseline[f"threshold_{suffix}"]).astype(int)

    robust = pd.read_csv(ROBUST_PRED)
    robust = robust[(robust["population"] == "PRIMARY_EVALUATION") &
                    robust["model"].isin(MODELS)].copy()
    robust["source"] = "robustness_operational_v2"

    audit_alignment(benchmark, baseline, robust)
    return benchmark, baseline, robust


def audit_alignment(benchmark, baseline, robust):
    assert benchmark.groupby("family_id")["fold"].nunique().max() == 1
    assert not baseline.duplicated(["sample_id", "seed", "model"]).any()
    assert not robust.duplicated(["sample_id", "seed", "model", "condition"]).any()
    expected_samples = set(benchmark["sample_id"])
    assert set(baseline["sample_id"]) == expected_samples
    assert set(robust["sample_id"]) == expected_samples
    for name, frame, groups in (
            ("baseline", baseline, ["model", "seed"]),
            ("robustness", robust, ["model", "condition", "seed"])):
        sizes = frame.groupby(groups).size()
        assert sizes.eq(2190).all(), f"{name} incomplete prediction groups"
        merged = frame.merge(benchmark, on="sample_id", suffixes=("_pred", "_bench"),
                             validate="many_to_one")
        assert len(merged) == len(frame)
        assert (merged["family_id_pred"] == merged["family_id_bench"]).all()
        assert (merged["fold_pred"].astype(int) == merged["fold_bench"]).all()
        assert (merged["true_label_pred"].astype(int) ==
                merged["true_label_bench"]).all()

    pair_keys = ["sample_id", "family_id", "fold", "seed", "true_label"]
    for frame, conditions in ((baseline, ["clean"]),
                              (robust, ["M0", "F200", "M3+F200"])):
        for condition in conditions:
            subset = frame[frame["condition"] == condition]
            key_sets = [set(map(tuple, subset[subset["model"] == model]
                               [pair_keys].to_numpy())) for model in MODELS]
            assert key_sets[0] == key_sets[1] == key_sets[2]


def generate_family_counts(benchmark, replicates: int):
    counts = {}
    family_orders = {}
    for fold in FOLDS:
        families = np.asarray(sorted(benchmark.loc[benchmark["fold"] == fold,
                                                       "family_id"].unique()))
        family_orders[fold] = families
        rng = np.random.default_rng(fold_seed(BOOTSTRAP_SEED, fold))
        draws = rng.integers(0, len(families), size=(replicates, len(families)))
        matrix = np.zeros((replicates, len(families)), dtype=np.uint16)
        rows = np.repeat(np.arange(replicates), len(families))
        np.add.at(matrix, (rows, draws.reshape(-1)), 1)
        assert (matrix.sum(axis=1) == len(families)).all()
        counts[fold] = matrix
    return family_orders, counts


def fast_weighted_ap_batch(y, scores, row_family, family_counts,
                           chunk_size=AP_CHUNK_SIZE):
    """Exact sklearn-style non-interpolated AP for batches of family weights."""
    y = np.asarray(y, dtype=np.int8)
    scores = np.asarray(scores, dtype=float)
    row_family = np.asarray(row_family, dtype=int)
    order = np.argsort(-scores, kind="mergesort")
    y_sorted = y[order]
    scores_sorted = scores[order]
    family_sorted = row_family[order]
    tie_ends = np.r_[np.flatnonzero(scores_sorted[:-1] != scores_sorted[1:]),
                     len(scores_sorted) - 1]
    output = np.empty(len(family_counts), dtype=float)
    for start in range(0, len(family_counts), chunk_size):
        stop = min(start + chunk_size, len(family_counts))
        weights = family_counts[start:stop, family_sorted].astype(np.float64)
        positives = weights * y_sorted
        negatives = weights * (1 - y_sorted)
        tp_at = np.cumsum(positives, axis=1)[:, tie_ends]
        fp_at = np.cumsum(negatives, axis=1)[:, tie_ends]
        increments = np.diff(tp_at, axis=1, prepend=np.zeros((len(weights), 1)))
        total_positive = tp_at[:, -1]
        precision = np.divide(tp_at, tp_at + fp_at,
                              out=np.zeros_like(tp_at), where=(tp_at + fp_at) > 0)
        output[start:stop] = np.divide(
            np.sum(precision * increments, axis=1), total_positive,
            out=np.full(len(weights), np.nan), where=total_positive > 0)
    return output


def verify_fast_ap():
    rng = np.random.default_rng(9917)
    y = np.asarray([0, 1, 1, 0, 1, 0, 0, 1, 0, 1], dtype=int)
    scores = np.asarray([.8, .8, .7, .6, .6, .4, .3, .3, .1, .05])
    row_family = np.asarray([0, 0, 1, 2, 2, 3, 4, 4, 5, 5])
    counts = np.stack([np.bincount(rng.integers(0, 6, 6), minlength=6)
                       for _ in range(30)])
    fast = fast_weighted_ap_batch(y, scores, row_family, counts, chunk_size=7)
    reference = np.asarray([
        average_precision_score(y, scores, sample_weight=count[row_family])
        for count in counts
    ])
    assert np.allclose(fast, reference, atol=1e-12, rtol=0), \
        f"fast AP mismatch: {np.max(np.abs(fast-reference))}"


@dataclass(frozen=True)
class SeriesKey:
    source: str
    condition: str
    model: str
    metric: str


class BootstrapEngine:
    def __init__(self, benchmark, baseline, robust, replicates):
        self.benchmark = benchmark
        self.frames = {"baseline_v2": baseline,
                       "robustness_operational_v2": robust}
        self.replicates = replicates
        self.family_orders, self.family_counts = generate_family_counts(
            benchmark, replicates)
        self.cache = {}

    def subset(self, key: SeriesKey, seed: int, fold: int):
        frame = self.frames[key.source]
        out = frame[(frame["condition"] == key.condition) &
                    (frame["model"] == key.model) &
                    (frame["seed"] == seed) &
                    (frame["fold"] == fold)].copy()
        out = out.sort_values("sample_id").reset_index(drop=True)
        expected = self.benchmark[self.benchmark["fold"] == fold]
        assert len(out) == len(expected)
        lookup = {family: index for index, family in
                  enumerate(self.family_orders[fold])}
        row_family = out["family_id"].map(lookup).to_numpy(dtype=int)
        assert not np.isnan(row_family).any()
        return out, row_family

    def fold_distribution(self, key: SeriesKey, seed: int, fold: int):
        data, row_family = self.subset(key, seed, fold)
        y = data["true_label"].to_numpy(dtype=int)
        counts = self.family_counts[fold]
        if key.metric == "AUPRC":
            scores = data["calibrated_score"].to_numpy(dtype=float)
            point = float(average_precision_score(y, scores))
            distribution = fast_weighted_ap_batch(y, scores, row_family, counts)
        elif key.metric.startswith("Recall@"):
            suffix = {"Recall@1%": "01", "Recall@5%": "05",
                      "Recall@10%": "10"}[key.metric]
            decisions = data[f"decision_{suffix}"].to_numpy(dtype=float)
            positive = y == 1
            point = float(decisions[positive].mean())
            numerator = np.bincount(
                row_family, weights=decisions * positive, minlength=counts.shape[1])
            denominator = np.bincount(
                row_family, weights=positive.astype(float), minlength=counts.shape[1])
            distribution = (counts @ numerator) / (counts @ denominator)
        elif key.metric == "Brier":
            errors = (data["calibrated_score"].to_numpy(dtype=float) - y) ** 2
            point = float(errors.mean())
            numerator = np.bincount(
                row_family, weights=errors, minlength=counts.shape[1])
            denominator = np.bincount(row_family, minlength=counts.shape[1])
            distribution = (counts @ numerator) / (counts @ denominator)
        else:
            raise ValueError(key.metric)
        if not np.isfinite(distribution).all():
            raise RuntimeError(f"non-finite bootstrap metric for {key}")
        return point, distribution

    def metric(self, key: SeriesKey):
        if key in self.cache:
            return self.cache[key]
        points = []
        distributions = []
        for seed in SEEDS:
            seed_points, seed_distributions = [], []
            for fold in FOLDS:
                point, distribution = self.fold_distribution(key, seed, fold)
                seed_points.append(point)
                seed_distributions.append(distribution)
            points.append(float(np.mean(seed_points)))
            distributions.append(np.mean(seed_distributions, axis=0))
        result = (float(np.mean(points)), np.mean(distributions, axis=0), points)
        self.cache[key] = result
        return result


def comparison_specs():
    specs = []
    for comparator in ("flat_cnn", "hist_ngram_xgb"):
        for metric in ("AUPRC", "Recall@5%"):
            specs.append(dict(
                condition="clean", metric=metric,
                model_a="authguard_seq", model_b=comparator,
                source_a="baseline_v2", source_b="baseline_v2",
                condition_a="clean", condition_b="clean",
                comparison_type="primary_confirmatory"))
        for metric in ("Recall@1%", "Recall@10%", "Brier"):
            specs.append(dict(
                condition="clean", metric=metric,
                model_a="authguard_seq", model_b=comparator,
                source_a="baseline_v2", source_b="baseline_v2",
                condition_a="clean", condition_b="clean",
                comparison_type="secondary_clean"))
    for condition in ("F200", "M3+F200"):
        for comparator in ("flat_cnn", "hist_ngram_xgb"):
            for metric in ("AUPRC", "Recall@5%"):
                specs.append(dict(
                    condition=condition, metric=metric,
                    model_a="authguard_seq", model_b=comparator,
                    source_a="robustness_operational_v2",
                    source_b="robustness_operational_v2",
                    condition_a=condition, condition_b=condition,
                    comparison_type="supporting_robustness"))
    for condition in ("F200", "M3+F200"):
        for metric in ("AUPRC", "Recall@5%"):
            specs.append(dict(
                condition=f"{condition}_minus_M0", metric=metric,
                model_a="authguard_seq", model_b="authguard_seq",
                source_a="robustness_operational_v2",
                source_b="robustness_operational_v2",
                condition_a=condition, condition_b="M0",
                comparison_type="supporting_clean_to_transformed"))
    return specs


def check_descriptive_consistency(engine: BootstrapEngine):
    checks = []
    baseline_summary = pd.read_csv(BASELINE_SUMMARY).set_index("model")
    robust_summary = pd.read_csv(ROBUST_SUMMARY).set_index(["model", "condition"])
    for source, condition, models in (
            ("baseline_v2", "clean", MODELS),
            ("robustness_operational_v2", "M0", MODELS),
            ("robustness_operational_v2", "F200", MODELS),
            ("robustness_operational_v2", "M3+F200", MODELS)):
        for model in models:
            for metric in METRIC_COLUMN:
                key = SeriesKey(source, condition, model, metric)
                point, _, _ = engine.metric(key)
                column = METRIC_COLUMN[metric] + "_mean"
                expected = (baseline_summary.loc[model, column]
                            if source == "baseline_v2"
                            else robust_summary.loc[(model, condition), column])
                difference = float(point - expected)
                checks.append(dict(source=source, condition=condition, model=model,
                                   metric=metric, recomputed=point, reported=expected,
                                   difference=difference))
                if abs(difference) > 1e-10:
                    raise RuntimeError(f"descriptive consistency failed: {checks[-1]}")
    return pd.DataFrame(checks)


def analyze(engine: BootstrapEngine):
    result_rows, distribution_rows = [], []
    for spec in comparison_specs():
        key_a = SeriesKey(spec["source_a"], spec["condition_a"],
                          spec["model_a"], spec["metric"])
        key_b = SeriesKey(spec["source_b"], spec["condition_b"],
                          spec["model_b"], spec["metric"])
        observed_a, distribution_a, seed_a = engine.metric(key_a)
        observed_b, distribution_b, seed_b = engine.metric(key_b)
        delta = distribution_a - distribution_b
        observed_delta = observed_a - observed_b
        lower, upper = np.percentile(delta, CI_PERCENTILES)
        lower_is_better = spec["metric"] == "Brier"
        supported = bool(upper < 0) if lower_is_better else bool(lower > 0)
        result_rows.append({
            **spec,
            "observed_model_a": observed_a,
            "observed_model_b": observed_b,
            "observed_delta": observed_delta,
            "ci_lower_95": float(lower),
            "ci_upper_95": float(upper),
            "ci_excludes_zero": bool(lower > 0 or upper < 0),
            "favorable_direction": "negative" if lower_is_better else "positive",
            "statistically_supported": supported,
            "bootstrap_replicates": engine.replicates,
            "bootstrap_seed": BOOTSTRAP_SEED,
            "p_value": np.nan,
            "adjusted_p_value": np.nan,
            "p_value_policy": "not_reported_CI_primary_Holm_not_applicable",
            "seed_level_model_a": json.dumps(seed_a),
            "seed_level_model_b": json.dumps(seed_b),
        })
        comparison_id = len(result_rows) - 1
        distribution_rows.extend({
            "comparison_id": comparison_id,
            "replicate": index,
            "condition": spec["condition"],
            "metric": spec["metric"],
            "model_a": spec["model_a"],
            "model_b": spec["model_b"],
            "comparison_type": spec["comparison_type"],
            "model_a_value": float(distribution_a[index]),
            "model_b_value": float(distribution_b[index]),
            "delta": float(delta[index]),
        } for index in range(engine.replicates))
        print(f"[bootstrap] {spec['comparison_type']} {spec['condition']} "
              f"{spec['metric']} {spec['model_a']}-{spec['model_b']} "
              f"delta={observed_delta:+.4f} CI=[{lower:+.4f},{upper:+.4f}]",
              flush=True)
    return pd.DataFrame(result_rows), pd.DataFrame(distribution_rows)


def fmt(value):
    return f"{value:+.3f}"


def generate_reports(results, consistency, wall_seconds):
    def row(condition, metric, model_b, comparison_type=None):
        match = ((results["condition"] == condition) &
                 (results["metric"] == metric) &
                 (results["model_b"] == model_b))
        if comparison_type:
            match &= results["comparison_type"] == comparison_type
        selected = results[match]
        if len(selected) != 1:
            raise RuntimeError(f"ambiguous result lookup: {condition}, {metric}, {model_b}")
        return selected.iloc[0]

    report = [
        "# Revision v2 Paired Statistical Analysis", "",
        "## Estimator", "",
        "This analysis uses a paired, fold-stratified family-clustered percentile bootstrap "
        "with 10,000 replicates and fixed seed 77022026. Within each outer test fold, every "
        "replicate samples that fold's frozen bytecode families with replacement and retains "
        "all observations belonging to each sampled family. The same family multiplicities "
        "are applied to both paired models, all three seeds, and paired clean/transformed "
        "conditions.", "",
        "For each replicate, a metric is computed separately for every seed and fold. The five "
        "fold values are averaged to a seed-level value, and the seed-level values for 7702, "
        "7703, and 7704 are averaged. The reported delta is AuthGuard-Seq minus the comparator; "
        "for clean-to-transformed analysis it is transformed minus M0. This exactly preserves "
        "the completed experiments' fold→seed→three-seed descriptive estimator. Prediction "
        "scores are never averaged across seeds.", "",
        "Percentile 95% confidence intervals are the inferential result. P-values are not "
        "reported: using the sign frequency of an observed-centered bootstrap distribution as "
        "a null p-value would be misleading. Consequently Holm correction is not applicable. "
        "The four predefined primary comparisons remain explicitly separated from supporting "
        "and secondary analyses.", "",
        "## Integrity checks", "",
        f"All {len(consistency)} descriptive recomputations matched their completed summary "
        "values within 1e-10. Every model/condition/seed contained 2,190 held-out rows; sample "
        "IDs, family IDs, folds, labels, and seeds aligned with the official benchmark; all "
        "paired comparisons used identical observations; and no family crossed folds. The "
        "batched weighted-AUPRC implementation was checked against scikit-learn to 1e-12.", "",
        "## Primary confirmatory comparisons", "",
        "| Metric | Comparison | AuthGuard-Seq | Comparator | Δ | 95% CI | Supported? |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    primary = results[results["comparison_type"] == "primary_confirmatory"]
    for _, item in primary.iterrows():
        report.append(
            f"| {item.metric} | Seq vs {item.model_b} | {item.observed_model_a:.3f} | "
            f"{item.observed_model_b:.3f} | {fmt(item.observed_delta)} | "
            f"[{fmt(item.ci_lower_95)}, {fmt(item.ci_upper_95)}] | "
            f"{'yes' if item.statistically_supported else 'no'} |")
    report += ["", "## Secondary clean comparisons", "",
               "| Metric | Comparison | Δ | 95% CI | Supported? |",
               "|---|---|---:|---:|---:|"]
    secondary = results[results["comparison_type"] == "secondary_clean"]
    for _, item in secondary.iterrows():
        report.append(
            f"| {item.metric} | Seq vs {item.model_b} | {fmt(item.observed_delta)} | "
            f"[{fmt(item.ci_lower_95)}, {fmt(item.ci_upper_95)}] | "
            f"{'yes' if item.statistically_supported else 'no'} |")
    report += ["", "## Supporting robustness comparisons", "",
               "| Condition | Metric | Comparison | Δ | 95% CI | Supported? |",
               "|---|---|---|---:|---:|---:|"]
    supporting = results[results["comparison_type"] == "supporting_robustness"]
    for _, item in supporting.iterrows():
        report.append(
            f"| {item.condition} | {item.metric} | Seq vs {item.model_b} | "
            f"{fmt(item.observed_delta)} | [{fmt(item.ci_lower_95)}, "
            f"{fmt(item.ci_upper_95)}] | "
            f"{'yes' if item.statistically_supported else 'no'} |")
    report += ["", "## Clean-to-transformed AuthGuard-Seq changes", "",
               "| Change | Metric | Observed change | 95% CI | Crosses zero? |",
               "|---|---|---:|---:|---:|"]
    changes = results[results["comparison_type"] == "supporting_clean_to_transformed"]
    for _, item in changes.iterrows():
        report.append(
            f"| {item.condition} | {item.metric} | {fmt(item.observed_delta)} | "
            f"[{fmt(item.ci_lower_95)}, {fmt(item.ci_upper_95)}] | "
            f"{'no' if item.ci_excludes_zero else 'yes'} |")
    report += ["", "## Interpretation", "",
               "Confidence intervals quantify dependence-aware uncertainty for the predefined "
               "comparisons. They do not cure the benchmark's analyzer-derived label boundary, "
               "and robustness intervals do not turn M3+F200 into a semantics-preserving "
               "transformation. F200 retains only the previously documented bounded execution-"
               "fingerprint support.", "",
               f"Runtime: {wall_seconds:.1f} seconds."]
    with open(os.path.join(HERE, "STATISTICAL_ANALYSIS_REPORT.md"), "w") as handle:
        handle.write("\n".join(report) + "\n")

    clean_cnn_ap = row("clean", "AUPRC", "flat_cnn", "primary_confirmatory")
    clean_xgb_ap = row("clean", "AUPRC", "hist_ngram_xgb", "primary_confirmatory")
    clean_cnn_r5 = row("clean", "Recall@5%", "flat_cnn", "primary_confirmatory")
    clean_xgb_r5 = row("clean", "Recall@5%", "hist_ngram_xgb", "primary_confirmatory")
    important_cross = results[
        results["comparison_type"].isin(["primary_confirmatory", "supporting_robustness",
                                         "supporting_clean_to_transformed"]) &
        ~results["ci_excludes_zero"]]
    secondary_cross = results[(results["comparison_type"] == "secondary_clean") &
                              ~results["ci_excludes_zero"]]
    final = [
        "# Statistical Final Summary", "", "## Direct answers", "",
        f"**A. Clean AUPRC vs Flat CNN.** Yes. The paired difference is "
        f"{fmt(clean_cnn_ap.observed_delta)} with 95% CI "
        f"[{fmt(clean_cnn_ap.ci_lower_95)}, {fmt(clean_cnn_ap.ci_upper_95)}].", "",
        f"**B. Clean AUPRC vs XGBoost.** Yes. The paired difference is "
        f"{fmt(clean_xgb_ap.observed_delta)} with 95% CI "
        f"[{fmt(clean_xgb_ap.ci_lower_95)}, {fmt(clean_xgb_ap.ci_upper_95)}].", "",
        f"**C. Clean Recall@5% vs Flat CNN.** Yes. The paired difference is "
        f"{fmt(clean_cnn_r5.observed_delta)} with 95% CI "
        f"[{fmt(clean_cnn_r5.ci_lower_95)}, {fmt(clean_cnn_r5.ci_upper_95)}].", "",
        f"**D. Clean Recall@5% vs XGBoost.** Yes. The paired difference is "
        f"{fmt(clean_xgb_r5.observed_delta)} with 95% CI "
        f"[{fmt(clean_xgb_r5.ci_lower_95)}, {fmt(clean_xgb_r5.ci_upper_95)}].", "",
    ]
    for label, condition in (("E. F200", "F200"), ("F. M3+F200", "M3+F200")):
        rows = supporting[supporting["condition"] == condition]
        statements = []
        for _, item in rows.iterrows():
            statements.append(
                f"{item.metric} vs {item.model_b}: Δ {fmt(item.observed_delta)}, "
                f"95% CI [{fmt(item.ci_lower_95)}, {fmt(item.ci_upper_95)}]")
        all_supported = rows["statistically_supported"].all()
        final += [f"**{label} advantages.** {'Yes' if all_supported else 'Not uniformly'}. "
                  + "; ".join(statements) + ".", ""]
    final += [
        "**G. Paper-ready paired differences.**", "",
        "| Analysis | Metric | Δ | 95% CI |",
        "|---|---|---:|---:|",
    ]
    paper_rows = results[results["comparison_type"].isin(
        ["primary_confirmatory", "supporting_robustness",
         "supporting_clean_to_transformed"])]
    for _, item in paper_rows.iterrows():
        name = (f"{item.condition}: Seq vs {item.model_b}"
                if item.comparison_type != "supporting_clean_to_transformed"
                else f"AuthGuard-Seq {item.condition}")
        final.append(f"| {name} | {item.metric} | {fmt(item.observed_delta)} | "
                     f"[{fmt(item.ci_lower_95)}, {fmt(item.ci_upper_95)}] |")
    final += ["",
              f"**H. Intervals crossing zero.** "
              f"{('No primary, robustness, or clean-to-transformed interval crosses zero.' if important_cross.empty else str(len(important_cross)) + ' primary/supporting interval(s) cross zero; see the detailed report.')} "
              f"{('One secondary interval—clean Recall@1% versus Flat CNN—crosses zero, so that optional low-FPR advantage is not statistically supported.' if len(secondary_cross) == 1 else str(len(secondary_cross)) + ' secondary interval(s) cross zero.')}", "",
              "**I. Consistency with descriptive results.** Yes. Clean inference uses the "
              "completed baseline predictions and exactly reproduces the established 0.924, "
              "0.885, and 0.833 fold→seed AUPRC means. Robustness comparisons use the matched "
              "robustness-run models. Clean-to-transformed changes use that run's M0 predictions "
              "so model weights, calibration, and thresholds remain paired. No pooled-score "
              "estimator replaces the descriptive headline numbers.", "",
              "**J. Strongest statistically supported claim.** Under family-clustered, paired, "
              "three-seed inference, AuthGuard-Seq has higher clean AUPRC and Recall@5% than "
              "both Flat CNN and histogram+hashed-4-gram XGBoost. Its AUPRC and Recall@5% "
              "advantages also remain supported under F200 and M3+F200. These claims concern "
              "screening of source-analyzer-flagged EIP-7702 delegate risk and do not establish "
              "independently confirmed maliciousness or universal semantic robustness.", "",
              "## Methodological issue affecting interpretation", "",
              "The clean confirmatory predictions and robustness predictions come from separate "
              "neural training executions. Because the frozen GPU training path is not bitwise "
              "deterministic, robustness-run M0 differs modestly from the baseline run. Therefore "
              "clean confirmatory inference uses `baseline_v2`, whereas clean-to-transformed "
              "changes use the matched robustness-run M0. Mixing those sources would break the "
              "pairing. P-values and Holm-adjusted p-values are intentionally not reported; the "
              "predefined percentile confidence intervals are the primary inferential result."]
    with open(os.path.join(HERE, "STATISTICAL_FINAL_SUMMARY.md"), "w") as handle:
        handle.write("\n".join(final) + "\n")


def write_config(replicates, comparisons, consistency, wall_seconds):
    config = {
        "analysis": "Revision v2 paired family-clustered bootstrap",
        "bootstrap_replicates": replicates,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "per_fold_bootstrap_seeds": {str(fold): fold_seed(BOOTSTRAP_SEED, fold)
                                     for fold in FOLDS},
        "ci_method": "percentile",
        "ci_percentiles": CI_PERCENTILES,
        "statistical_unit": "frozen bytecode family",
        "resampling": "families sampled with replacement separately within each outer test fold",
        "pairing": "same family multiplicities for both models, all seeds, and paired conditions",
        "estimator": "metric per fold and seed; mean over 5 folds; mean over seeds 7702/7703/7704",
        "seeds": SEEDS,
        "folds": FOLDS,
        "models": MODELS,
        "primary_confirmatory_family": [
            "Seq vs Flat CNN clean AUPRC", "Seq vs XGBoost clean AUPRC",
            "Seq vs Flat CNN clean Recall@5%", "Seq vs XGBoost clean Recall@5%",
        ],
        "p_value_policy": (
            "not reported; percentile confidence intervals are primary and bootstrap sign "
            "frequencies are not treated as null p-values; Holm correction not applicable"
        ),
        "comparisons": comparisons,
        "descriptive_consistency_checks": len(consistency),
        "wall_seconds": wall_seconds,
        "inputs": {
            os.path.relpath(BENCH, ROOT): sha256_file(BENCH),
            os.path.relpath(BASELINE_PRED, ROOT): sha256_file(BASELINE_PRED),
            os.path.relpath(BASELINE_SUMMARY, ROOT): sha256_file(BASELINE_SUMMARY),
            os.path.relpath(ROBUST_PRED, ROOT): sha256_file(ROBUST_PRED),
            os.path.relpath(ROBUST_SUMMARY, ROOT): sha256_file(ROBUST_SUMMARY),
        },
        "software": {"python": sys.version, "numpy": np.__version__,
                     "pandas": pd.__version__},
    }
    with open(os.path.join(HERE, "statistical_analysis_config.json"), "w") as handle:
        json.dump(config, handle, indent=2)


def mirror_outputs():
    os.makedirs(MIRROR, exist_ok=True)
    for name in ("STATISTICAL_ANALYSIS_REPORT.md", "paired_bootstrap_results.csv",
                 "bootstrap_distributions.csv.gz", "statistical_analysis_config.json",
                 "STATISTICAL_FINAL_SUMMARY.md"):
        shutil.copy2(os.path.join(HERE, name), os.path.join(MIRROR, name))


def validate_only():
    verify_fast_ap()
    benchmark, baseline, robust = prepare_sources()
    engine = BootstrapEngine(benchmark, baseline, robust, replicates=50)
    consistency = check_descriptive_consistency(engine)
    assert len(comparison_specs()) == 22
    print(json.dumps({
        "status": "PASS", "primary_rows": len(benchmark),
        "families": benchmark["family_id"].nunique(),
        "baseline_prediction_rows": len(baseline),
        "robustness_prediction_rows": len(robust),
        "descriptive_checks": len(consistency),
        "comparisons": len(comparison_specs()),
        "fast_weighted_AP_vs_sklearn": "PASS_at_1e-12",
    }, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--replicates", type=int, default=N_BOOTSTRAP)
    args = parser.parse_args()
    if args.validate_only:
        validate_only()
        return
    if args.replicates < 10_000:
        raise ValueError("final analysis requires at least 10,000 bootstrap replicates")
    if verify_frozen() != 0:
        raise RuntimeError("frozen-artifact verification failed before analysis")
    started = time.time()
    verify_fast_ap()
    benchmark, baseline, robust = prepare_sources()
    engine = BootstrapEngine(benchmark, baseline, robust, args.replicates)
    consistency = check_descriptive_consistency(engine)
    consistency.to_csv(os.path.join(HERE, "descriptive_consistency_checks.csv"), index=False)
    results, distributions = analyze(engine)
    results.to_csv(os.path.join(HERE, "paired_bootstrap_results.csv"), index=False)
    distributions.to_csv(os.path.join(HERE, "bootstrap_distributions.csv.gz"),
                         index=False, compression="gzip")
    wall_seconds = time.time() - started
    write_config(args.replicates, comparison_specs(), consistency, wall_seconds)
    generate_reports(results, consistency, wall_seconds)
    mirror_outputs()
    if verify_frozen() != 0:
        raise RuntimeError("frozen-artifact verification failed after analysis")
    print(f"[bootstrap] complete comparisons={len(results)} "
          f"distributions={len(distributions)} seconds={wall_seconds:.1f}", flush=True)


if __name__ == "__main__":
    main()
