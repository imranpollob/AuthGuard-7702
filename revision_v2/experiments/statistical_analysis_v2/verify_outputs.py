#!/usr/bin/env python3
"""Completeness and integrity checks for statistical_analysis_v2 outputs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
MIRROR = HERE.parents[1] / "results" / "statistical_analysis_v2"
REQUIRED = [
    "STATISTICAL_ANALYSIS_REPORT.md",
    "paired_bootstrap_results.csv",
    "bootstrap_distributions.csv.gz",
    "statistical_analysis_config.json",
    "STATISTICAL_FINAL_SUMMARY.md",
]


def digest(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    missing = [name for name in REQUIRED if not (HERE / name).is_file()]
    assert not missing, f"missing outputs: {missing}"
    for name in REQUIRED:
        assert (MIRROR / name).is_file(), f"missing mirror: {name}"
        assert digest(HERE / name) == digest(MIRROR / name), f"mirror mismatch: {name}"

    config = json.load(open(HERE / "statistical_analysis_config.json"))
    assert config["bootstrap_replicates"] >= 10_000
    assert config["bootstrap_seed"] == 77022026
    assert config["seeds"] == [7702, 7703, 7704]
    assert config["folds"] == [0, 1, 2, 3, 4]
    assert config["statistical_unit"] == "frozen bytecode family"

    results = pd.read_csv(HERE / "paired_bootstrap_results.csv")
    assert len(results) == 22
    assert len(results[results["comparison_type"] == "primary_confirmatory"]) == 4
    assert len(results[results["comparison_type"] == "secondary_clean"]) == 6
    assert len(results[results["comparison_type"] == "supporting_robustness"]) == 8
    assert len(results[results["comparison_type"] ==
                               "supporting_clean_to_transformed"]) == 4
    assert (results["ci_lower_95"] <= results["ci_upper_95"]).all()
    assert results[["observed_model_a", "observed_model_b", "observed_delta",
                    "ci_lower_95", "ci_upper_95"]].notna().all().all()
    assert results["p_value"].isna().all() and results["adjusted_p_value"].isna().all()

    distributions = pd.read_csv(HERE / "bootstrap_distributions.csv.gz")
    expected = len(results) * int(config["bootstrap_replicates"])
    assert len(distributions) == expected
    sizes = distributions.groupby("comparison_id").size()
    assert len(sizes) == len(results) and sizes.eq(config["bootstrap_replicates"]).all()
    assert distributions[["model_a_value", "model_b_value", "delta"]].notna().all().all()

    checks = pd.read_csv(HERE / "descriptive_consistency_checks.csv")
    assert len(checks) == 60
    assert checks["difference"].abs().max() <= 1e-10
    print("statistical_analysis_v2 outputs: PASS")


if __name__ == "__main__":
    main()
