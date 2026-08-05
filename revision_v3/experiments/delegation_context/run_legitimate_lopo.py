"""Leave-one-project-out legitimate-control generalization for the DCRG model.

For each documented project, all its deployments and every known related canonical family are
held out. One exact-runtime-deduplicated example from each *other* project may augment the
primary training split as a benign row with ordinary unit weight. Evaluation uses all three
seeds and five primary outer folds. This experiment does not reuse the frozen sequence model,
whose checkpoints cannot retroactively remove project families from their training data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict

import numpy as np
import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
V3 = os.path.join(REPO_ROOT, "revision_v3")
sys.path.insert(0, os.path.join(V3, "src"))
sys.path.insert(0, os.path.join(V3, "experiments", "delegation_context"))

from analysis.delegation_context import DCRG_FEATURE_ORDER  # noqa: E402
from data.loader import fold_split, load_primary_dataset  # noqa: E402
from evaluation.metrics import full_metrics, threshold_at_nominal_fpr  # noqa: E402
from evaluation.selective_policy import (  # noqa: E402
    DEFER,
    LOW_OBSERVED_RISK,
    WARN,
    selective_decisions,
)
from training.harness import SEEDS  # noqa: E402
from run_dcrg_fusion import calibrated_context_scores  # noqa: E402
from run_legitimate_controls import load_controls  # noqa: E402

RESULTS_DIR = os.path.join(V3, "results", "delegation_context")


def runtime_hash(bytecode: str) -> str:
    text = bytecode[2:] if bytecode.startswith("0x") else bytecode
    return hashlib.sha256(bytes.fromhex(text)).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", default=RESULTS_DIR)
    parser.add_argument("--feature-path", default=os.path.join(
        RESULTS_DIR, "dcrg_primary_features.csv.gz"
    ))
    parser.add_argument("--project-weight-total", type=float, default=None,
                        help="fixed total benign weight assigned to each development project; "
                             "default preserves unit weight per exact runtime")
    args = parser.parse_args()
    os.makedirs(args.results_dir, exist_ok=True)
    primary = load_primary_dataset()
    features = pd.read_csv(args.feature_path)
    merged = primary.merge(
        features[["sample_id", "coverage", *DCRG_FEATURE_ORDER]],
        on="sample_id", how="left", validate="one_to_one"
    )
    controls = load_controls()
    for control in controls:
        control["runtime_hash"] = runtime_hash(control["runtime_bytecode"])
    projects = sorted({control["project"] for control in controls})
    votes = defaultdict(list)
    split_audit = []

    for heldout_project in projects:
        heldout = [control for control in controls if control["project"] == heldout_project]
        heldout_families = {control["family_id"] for control in heldout if control["family_id"]}
        heldout_hashes = {control["runtime_hash"] for control in heldout}

        development = [
            control for control in controls
            if control["project"] != heldout_project
            and control["runtime_hash"] not in heldout_hashes
            and control["family_id"] not in heldout_families
        ]
        deduplicated_development = {}
        for control in development:
            deduplicated_development.setdefault(control["runtime_hash"], control)
        development = list(deduplicated_development.values())
        dev_x = np.asarray([control["dcrg_features"] for control in development],
                           dtype=np.float32)
        heldout_x = np.asarray([control["dcrg_features"] for control in heldout],
                               dtype=np.float32)
        heldout_coverage = np.asarray([control["coverage"] for control in heldout], dtype=object)

        for seed in SEEDS:
            for test_fold in range(5):
                train_df, val_df, test_df = fold_split(merged, test_fold)
                train_df = train_df[~train_df["family_id"].isin(heldout_families)]
                val_df = val_df[~val_df["family_id"].isin(heldout_families)]
                test_df = test_df[~test_df["family_id"].isin(heldout_families)]
                primary_train_x = train_df[list(DCRG_FEATURE_ORDER)].to_numpy(dtype=np.float32)
                primary_train_y = train_df["label"].to_numpy(dtype=np.int64)
                if len(dev_x):
                    train_x = np.concatenate([primary_train_x, dev_x], axis=0)
                    train_y = np.concatenate([
                        primary_train_y, np.zeros(len(dev_x), dtype=np.int64)
                    ])
                else:
                    train_x, train_y = primary_train_x, primary_train_y
                sample_weight = np.ones(len(train_y), dtype=np.float64)
                if len(dev_x) and args.project_weight_total is not None:
                    project_counts = Counter(control["project"] for control in development)
                    for offset, control in enumerate(development, start=len(primary_train_y)):
                        sample_weight[offset] = (
                            args.project_weight_total / project_counts[control["project"]]
                        )
                val_x = val_df[list(DCRG_FEATURE_ORDER)].to_numpy(dtype=np.float32)
                val_y = val_df["label"].to_numpy(dtype=np.int64)
                test_x = test_df[list(DCRG_FEATURE_ORDER)].to_numpy(dtype=np.float32)
                test_y = test_df["label"].to_numpy(dtype=np.int64)
                context_val, test_scores, _, heldout_scores = calibrated_context_scores(
                    train_x, train_y, val_x, val_y, test_x, seed,
                    extra_x=heldout_x,
                    train_sample_weight=sample_weight,
                )
                threshold = threshold_at_nominal_fpr(context_val, val_y, 0.05)
                decisions = selective_decisions(
                    heldout_scores, threshold, heldout_coverage
                )
                for index, control in enumerate(heldout):
                    votes[control["item_id"]].append({
                        "seed": int(seed),
                        "test_fold": int(test_fold),
                        "score": float(heldout_scores[index]),
                        "threshold_5pct": float(threshold),
                        "decision": str(decisions[index]),
                    })
                split_audit.append({
                    "heldout_project": heldout_project,
                    "seed": int(seed),
                    "test_fold": int(test_fold),
                    "heldout_known_families": sorted(heldout_families),
                    "heldout_runtime_hashes": sorted(heldout_hashes),
                    "n_primary_train_after_project_family_holdout": len(train_df),
                    "n_primary_val_after_project_family_holdout": len(val_df),
                    "n_development_project_runtimes": len(development),
                    "development_projects": sorted({c["project"] for c in development}),
                    "project_weight_total": args.project_weight_total,
                    "primary_test_metrics": full_metrics(
                        test_y, test_scores, context_val, val_y
                    ),
                })
        print(f"[legitimate_lopo] held out {heldout_project}", flush=True)

    per_item = []
    for control in controls:
        item_votes = votes[control["item_id"]]
        if len(item_votes) != len(SEEDS) * 5:
            raise RuntimeError(f"incomplete LOPO votes for {control['item_id']}")
        distribution = Counter(vote["decision"] for vote in item_votes)
        warn_fraction = distribution[WARN] / len(item_votes)
        low_fraction = distribution[LOW_OBSERVED_RISK] / len(item_votes)
        consensus = (WARN if warn_fraction >= 0.5 else
                     LOW_OBSERVED_RISK if low_fraction >= 0.5 else DEFER)
        per_item.append({
            "item_id": control["item_id"],
            "project": control["project"],
            "family_id": control["family_id"],
            "coverage": control["coverage"],
            "n_votes": len(item_votes),
            "warn_fraction": warn_fraction,
            "low_observed_risk_fraction": low_fraction,
            "defer_fraction": distribution[DEFER] / len(item_votes),
            "consensus_decision": consensus,
        })
    distribution = Counter(item["consensus_decision"] for item in per_item)
    per_project = {}
    for project in projects:
        items = [item for item in per_item if item["project"] == project]
        per_project[project] = {
            "n": len(items),
            "consensus_warn": sum(item["consensus_decision"] == WARN for item in items),
            "mean_warn_fraction": float(np.mean([item["warn_fraction"] for item in items])),
        }
    report = {
        "status": "LEAVE_ONE_PROJECT_OUT_LEGITIMATE_CONTROL_EVALUATION",
        "protocol": "hold out all deployments and known canonical families for one project; "
                    "augment primary training with one exact-runtime-deduplicated unit-weight "
                    "benign row per runtime from other projects",
        "model": "DCRG-only XGBoost; frozen sequence checkpoints excluded because complete "
                 "project-family retraining is unavailable",
        "development_project_weight_total": args.project_weight_total,
        "n_projects": len(projects),
        "n_deployments": len(per_item),
        "consensus_distribution": dict(sorted(distribution.items())),
        "consensus_warn_rate": distribution[WARN] / len(per_item),
        "per_project": per_project,
        "per_item": per_item,
        "split_audit": split_audit,
        "limitations": [
            "Only eight legitimate projects are available; confidence intervals are wide.",
            f"Held-out control coverage is {dict(sorted(Counter(item['coverage'] for item in per_item).items()))}.",
            "This evaluation measures false-warning generalization only, not malicious recall.",
        ],
    }
    report["mean_primary_test_metrics_across_project_fold_seed_runs"] = {
        metric: float(np.mean([
            row["primary_test_metrics"][metric] for row in split_audit
        ]))
        for metric in ("auprc", "auroc", "recall_at_5pct", "observed_fpr_at_5pct")
    }
    with open(os.path.join(args.results_dir, "legitimate_lopo_report.json"), "w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    print(json.dumps({key: value for key, value in report.items()
                      if key not in {"per_item", "split_audit"}}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
