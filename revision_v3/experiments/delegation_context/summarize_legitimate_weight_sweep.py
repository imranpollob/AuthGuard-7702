#!/usr/bin/env python3
"""Summarize exploratory project-balanced legitimate-control weight sensitivity."""
from __future__ import annotations

import argparse
import json
import os

import numpy as np


def load(path: str) -> dict:
    with open(path) as handle:
        return json.load(handle)


def project_cluster_delta(a: dict, b: dict, n_replicates: int = 10000) -> dict:
    by_project_a = {name: values for name, values in a["per_project"].items()}
    by_project_b = {name: values for name, values in b["per_project"].items()}
    projects = sorted(by_project_a)
    if projects != sorted(by_project_b):
        raise ValueError("weight reports do not contain the same projects")
    rng = np.random.default_rng(77032026)

    def rate(report, sampled):
        warnings = sum(report["per_project"][name]["consensus_warn"] for name in sampled)
        total = sum(report["per_project"][name]["n"] for name in sampled)
        return warnings / total if total else 0.0

    point = rate(a, projects) - rate(b, projects)
    deltas = []
    for _ in range(n_replicates):
        sampled = rng.choice(projects, size=len(projects), replace=True).tolist()
        deltas.append(rate(a, sampled) - rate(b, sampled))
    low, high = np.percentile(deltas, [2.5, 97.5])
    return {
        "point_delta": float(point), "ci_low": float(low), "ci_high": float(high),
        "excludes_zero": bool(low > 0 or high < 0),
        "method": "paired project-cluster bootstrap over eight documented projects",
        "n_replicates": n_replicates,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--unit", required=True)
    parser.add_argument("--weight8", required=True)
    parser.add_argument("--weight32", required=True)
    parser.add_argument("--weight64", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    reports = {
        "unit_runtime_weight": load(args.unit),
        "project_total_weight_8": load(args.weight8),
        "project_total_weight_32": load(args.weight32),
        "project_total_weight_64": load(args.weight64),
    }
    summary = {}
    for name, report in reports.items():
        summary[name] = {
            "consensus_distribution": report["consensus_distribution"],
            "deployment_warn_rate": report["consensus_warn_rate"],
            "n_projects_with_any_consensus_warning": int(sum(
                values["consensus_warn"] > 0 for values in report["per_project"].values()
            )),
            "mean_primary_test_metrics": report.get(
                "mean_primary_test_metrics_across_project_fold_seed_runs"
            ),
        }
    report = {
        "status": "EXPLORATORY_DEVELOPMENT_PROJECT_WEIGHT_SENSITIVITY",
        "summary": summary,
        "weight8_minus_unit_warn_rate": project_cluster_delta(
            reports["project_total_weight_8"], reports["unit_runtime_weight"]
        ),
        "selection": (
            "Weight 8 is the smallest tested project-balanced value with the stable 1/30 "
            "warning outcome and the highest primary Recall@5% FPR among weights 8, 32, and 64."
        ),
        "fatal_validity_warning": (
            "These eight projects were used to explore and select the weighting rule. They are "
            "development controls, not final evidence; evaluate on newly collected projects."
        ),
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
