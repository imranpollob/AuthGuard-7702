"""Evaluate the DCRG+sequence selective policy on documented legitimate deployments.

Controls mapping to a canonical family are scored only by that family's held-out outer-fold
model (three seed votes). Provenance-verified unseen families are scored by all five folds per
seed (fifteen votes). Each vote uses its own validation-derived operating threshold.
"""
from __future__ import annotations

import csv
import glob
import json
import os
import sys
from collections import Counter, defaultdict

import numpy as np
import pandas as pd
import torch

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
V3 = os.path.join(REPO_ROOT, "revision_v3")
sys.path.insert(0, os.path.join(V3, "src"))
sys.path.insert(0, os.path.join(V3, "experiments", "delegation_context"))
sys.path.insert(0, os.path.join(V3, "experiments", "opus5_labeling"))

from analysis.delegation_context import (  # noqa: E402
    DCRG_FEATURE_ORDER,
    build_delegation_context_graph,
)
from data.loader import (  # noqa: E402
    canonical_family_ids,
    family_to_fold_map,
    fold_split,
    load_primary_dataset,
)
from evaluation.metrics import threshold_at_nominal_fpr  # noqa: E402
from evaluation.model_runtime import score_dataset_single_checkpoint  # noqa: E402
from evaluation.selective_policy import (  # noqa: E402
    DEFER,
    LOW_OBSERVED_RISK,
    WARN,
    risk_union,
    selective_decisions,
)
from training.harness import SEEDS  # noqa: E402
from build_dossiers import cfg_analysis  # noqa: E402
from run_dcrg_fusion import calibrated_context_scores  # noqa: E402

RESULTS_DIR = os.path.join(V3, "results", "delegation_context")
CONTROL_CSV = os.path.join(V3, "external_controls", "verified_legitimate_controls.csv")
CACHE_DIR = os.path.join(V3, "external_controls", "bytecode_cache")


def load_controls() -> list[dict]:
    with open(CONTROL_CSV) as handle:
        rows = list(csv.DictReader(handle))
    cache = {}
    for path in glob.glob(os.path.join(CACHE_DIR, "*.hex")):
        cache[os.path.basename(path).rsplit(".", 1)[0].lower()] = open(path).read().strip()
    controls = []
    missing = []
    for row in rows:
        address = row["address"].lower()
        bytecode = next((value for key, value in cache.items() if address[2:] in key), None)
        if not bytecode:
            missing.append(f"{row['chain']}:{row['address']}")
            continue
        cfg = cfg_analysis(bytecode)
        graph = build_delegation_context_graph(cfg)
        controls.append({
            **row,
            "item_id": f"{row['chain']}:{row['address'].lower()}",
            "runtime_bytecode": bytecode if bytecode.startswith("0x") else "0x" + bytecode,
            "family_id": row.get("bytecode_family") or None,
            "coverage": graph.coverage.value,
            "dcrg_features": graph.feature_vector(),
            "dcrg_findings": graph.findings,
        })
    if missing:
        print(f"[legitimate_controls] {len(missing)} controls lack cached bytecode", flush=True)
    return controls


def main() -> int:
    feature_path = os.path.join(RESULTS_DIR, "dcrg_primary_features.csv.gz")
    if not os.path.exists(feature_path):
        raise SystemExit("full DCRG feature artifact missing")
    primary = load_primary_dataset()
    feature_df = pd.read_csv(feature_path)
    merged = primary.merge(
        feature_df[["sample_id", "coverage", *DCRG_FEATURE_ORDER]],
        on="sample_id", how="left", validate="one_to_one"
    )
    controls = load_controls()
    if not controls:
        raise SystemExit("no legitimate controls with cached runtime bytecode")
    canonical = family_to_fold_map(primary)
    all_canonical_families = canonical_family_ids()
    unknown_named = sorted({control["family_id"] for control in controls
                            if control["family_id"] and
                            control["family_id"] not in all_canonical_families})
    if unknown_named:
        raise KeyError(f"unknown non-empty control family IDs: {unknown_named}")

    control_x = np.asarray([control["dcrg_features"] for control in controls], dtype=np.float32)
    control_bytecodes = [control["runtime_bytecode"] for control in controls]
    coverage = np.asarray([control["coverage"] for control in controls], dtype=object)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    votes = defaultdict(list)
    vote_records = []

    for seed in SEEDS:
        for test_fold in range(5):
            train_df, val_df, _ = fold_split(merged, test_fold)
            train_x = train_df[list(DCRG_FEATURE_ORDER)].to_numpy(dtype=np.float32)
            val_x = val_df[list(DCRG_FEATURE_ORDER)].to_numpy(dtype=np.float32)
            train_y = train_df["label"].to_numpy(dtype=np.int64)
            val_y = val_df["label"].to_numpy(dtype=np.int64)
            context_val, _, _, context_control = calibrated_context_scores(
                train_x, train_y, val_x, val_y, val_x[:1], seed, extra_x=control_x
            )
            sequence_val, _ = score_dataset_single_checkpoint(
                "authguard_sequence_dense", seed, test_fold,
                val_df["runtime_bytecode"].tolist(), device=device
            )
            sequence_control, _ = score_dataset_single_checkpoint(
                "authguard_sequence_dense", seed, test_fold, control_bytecodes, device=device
            )
            fusion_val = risk_union(sequence_val, context_val)
            fusion_control = risk_union(sequence_control, context_control)
            threshold = threshold_at_nominal_fpr(fusion_val, val_y, 0.05)
            decisions = selective_decisions(fusion_control, threshold, coverage)

            for index, control in enumerate(controls):
                family_id = control["family_id"]
                eligible = family_id not in canonical or canonical[family_id] == test_fold
                if not eligible:
                    continue
                vote = {
                    "seed": int(seed),
                    "test_fold": int(test_fold),
                    "sequence_score": float(sequence_control[index]),
                    "dcrg_score": float(context_control[index]),
                    "fusion_score": float(fusion_control[index]),
                    "threshold_5pct": float(threshold),
                    "decision": str(decisions[index]),
                }
                votes[control["item_id"]].append(vote)
                vote_records.append({"item_id": control["item_id"], **vote})
        print(f"[legitimate_controls] seed={seed} complete", flush=True)

    per_item = []
    for control in controls:
        item_votes = votes[control["item_id"]]
        expected_votes = (len(SEEDS) if control["family_id"] in canonical
                          else len(SEEDS) * 5)
        if len(item_votes) != expected_votes:
            raise RuntimeError(
                f"{control['item_id']} has {len(item_votes)} eligible votes, expected {expected_votes}"
            )
        distribution = Counter(vote["decision"] for vote in item_votes)
        warn_fraction = distribution[WARN] / len(item_votes)
        low_fraction = distribution[LOW_OBSERVED_RISK] / len(item_votes)
        if warn_fraction >= 0.5:
            consensus = WARN
        elif low_fraction >= 0.5:
            consensus = LOW_OBSERVED_RISK
        else:
            consensus = DEFER
        per_item.append({
            "item_id": control["item_id"],
            "project": control.get("project"),
            "category": control.get("category"),
            "provenance_confidence": control.get("provenance_confidence"),
            "family_id": control["family_id"],
            "score_provenance": (
                f"canonical_family_oof:test_fold={canonical[control['family_id']]}"
                if control["family_id"] in canonical else (
                    "canonical_non_primary:all_five_outer_folds"
                    if control["family_id"] else "verified_external:all_five_outer_folds"
                )
            ),
            "coverage": control["coverage"],
            "dcrg_findings": control["dcrg_findings"],
            "n_eligible_checkpoint_votes": len(item_votes),
            "warn_fraction": warn_fraction,
            "low_observed_risk_fraction": low_fraction,
            "defer_fraction": distribution[DEFER] / len(item_votes),
            "consensus_decision": consensus,
        })

    consensus_distribution = Counter(item["consensus_decision"] for item in per_item)
    report = {
        "status": "DOCUMENTED_LEGITIMATE_CONTROL_EVALUATION",
        "n_controls": len(per_item),
        "n_primary_family_controls_scored_oof": sum(
            item["family_id"] in canonical for item in per_item
        ),
        "n_canonical_non_primary_controls": sum(
            item["family_id"] in all_canonical_families and item["family_id"] not in canonical
            for item in per_item
        ),
        "n_verified_external_controls": sum(item["family_id"] is None for item in per_item),
        "consensus_distribution": dict(sorted(consensus_distribution.items())),
        "consensus_warn_rate": consensus_distribution[WARN] / len(per_item),
        "decision_rule": "majority over eligible checkpoint-specific decisions",
        "authority_context": "UNKNOWN; delegate address is not substituted for authorizing EOA",
        "per_item": per_item,
        "limitations": [
            "Documentation establishes legitimate deployment provenance, not universal safety.",
            "Controls measure false-warning behavior only and contain no malicious positives.",
            "Previously observed canonical families use only their held-out-fold checkpoints.",
        ],
        "vote_artifact": "revision_v3/results/delegation_context/legitimate_control_votes.csv.gz",
    }
    pd.DataFrame(vote_records).to_csv(
        os.path.join(RESULTS_DIR, "legitimate_control_votes.csv.gz"),
        index=False, compression="gzip"
    )
    with open(os.path.join(RESULTS_DIR, "legitimate_control_report.json"), "w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    print(json.dumps({key: value for key, value in report.items() if key != "per_item"},
                     indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
