"""Stage 7: assemble the final dataset deliverables.

Writes, unconditionally (these don't require human review):
  - data/gold_dataset/{run_id}_complete_population.csv       (all delegates, incl. NOTSCREENABLE)
  - data/gold_dataset/{run_id}_notscreenable.csv              (NOTSCREENABLE subset)
  - data/gold_dataset/{run_id}_huang_weak_labels.csv          (Huang/USENIX weak-label dataset)

Writes, only if data/human_reviews/{run_id}_completed.jsonl covers every screenable delegate:
  - data/gold_dataset/{run_id}_gold_reviewed.csv              (human-reviewed gold labels)
  - data/split_manifests/{run_id}_{train,val,test}.csv        (family-disjoint, temporal split)
  - reports/leakage_check.md

Refuses to fabricate a split from an incomplete review -- reports exactly how many contracts are
still unreviewed instead.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "dataset_pipeline")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pandas as pd  # noqa: E402

from lib.config import load_config  # noqa: E402
from lib.families import assert_no_family_leakage  # noqa: E402
from lib.huang_loader import build_huang_weak_label_dataset  # noqa: E402
from lib.repo_paths import REPO_ROOT  # noqa: E402
from lib.splits import assign_temporal_family_splits  # noqa: E402


def main():
    cfg = load_config()
    run_id = cfg["run_id"]
    gold_dir = cfg["_resolved_paths"]["gold_dataset"]
    split_dir = cfg["_resolved_paths"]["split_manifests"]
    os.makedirs(gold_dir, exist_ok=True)
    os.makedirs(split_dir, exist_ok=True)

    # --- complete population + NOTSCREENABLE (always available) ---
    pop_frames = []
    for chain in cfg["chains"]:
        pop_path = os.path.join(cfg["_resolved_paths"]["collected_delegates"], f"{run_id}_{chain}_population.csv")
        if os.path.exists(pop_path):
            pop_frames.append(pd.read_csv(pop_path))
    if not pop_frames:
        print(f"[gold] no population files found for run_id={run_id}; run Stage 2 first")
        return
    population = pd.concat(pop_frames, ignore_index=True)
    population.to_csv(os.path.join(gold_dir, f"{run_id}_complete_population.csv"), index=False)
    notscreenable = population[population["retrieval_status"] != "OK"]
    notscreenable.to_csv(os.path.join(gold_dir, f"{run_id}_notscreenable.csv"), index=False)
    print(f"[gold] population: {len(population)} total, {len(notscreenable)} NOTSCREENABLE")

    # --- Huang weak-label dataset (always available, independent of this run's collection) ---
    huang_cfg = cfg["huang_source"]
    huang = build_huang_weak_label_dataset(
        os.path.join(REPO_ROOT, huang_cfg["contracts_xlsx"]),
        os.path.join(REPO_ROOT, huang_cfg["detect_result_jsonl"]),
    )
    huang.to_csv(os.path.join(gold_dir, f"{run_id}_huang_weak_labels.csv"), index=False)
    print(f"[gold] Huang weak-label dataset: {len(huang)} rows, {int(huang['label'].sum())} positive")

    # --- human-reviewed gold dataset + splits (needs completed review) ---
    completed_path = os.path.join(cfg["_resolved_paths"]["human_reviews"], f"{run_id}_completed.jsonl")
    fam_path = os.path.join(cfg["_resolved_paths"]["bytecode_families"], f"{run_id}_family_assignment.csv")
    families = pd.read_csv(fam_path)
    screenable = families[families["retrieval_status"] == "OK"]

    if not os.path.exists(completed_path) or os.path.getsize(completed_path) == 0:
        print(f"[gold] {completed_path} does not exist or is empty -- human review has not "
              "started. Gold dataset and splits NOT written.")
        return

    reviews = pd.read_json(completed_path, lines=True)
    reviewed_addresses = set(reviews["address"])
    screenable_addresses = set(screenable["delegate_address"])
    missing = screenable_addresses - reviewed_addresses
    if missing:
        print(f"[gold] {len(missing)}/{len(screenable_addresses)} screenable delegates are not yet "
              f"in {completed_path}. Gold dataset and splits NOT written until review is complete. "
              f"Missing (first 10): {sorted(missing)[:10]}")
        return

    gold = families.merge(
        reviews[["address", "final_label", "final_confidence", "human_decision",
                 "llm_proposed_label", "llm_confidence", "corrected_risk_categories", "comment"]],
        left_on="delegate_address", right_on="address", how="inner",
    )
    gold_path = os.path.join(gold_dir, f"{run_id}_gold_reviewed.csv")
    gold.to_csv(gold_path, index=False)
    print(f"[gold] gold_reviewed: {len(gold)} rows -> {gold_path}")
    print(f"[gold] final_label distribution: {gold['final_label'].value_counts().to_dict()}")

    split_assignment = assign_temporal_family_splits(gold)
    gold["split"] = split_assignment

    crossing = assert_no_family_leakage(gold, "bytecode_family_id", "split")
    leakage_report_path = os.path.join(REPO_ROOT, "reports", "leakage_check.md")
    with open(leakage_report_path, "w") as f:
        f.write("# Leakage Check\n\n")
        f.write(f"Run: `{run_id}`. Split unit: `bytecode_family_id` (families assigned to the "
                "split containing their earliest first-observed member; see "
                "`dataset_pipeline/lib/splits.py`).\n\n")
        if crossing:
            f.write(f"**FAILED**: {len(crossing)} bytecode families cross more than one split: "
                    f"{crossing}\n")
        else:
            f.write("**PASSED**: no bytecode family appears in more than one split.\n\n")
        for split in ["train", "val", "test"]:
            sub = gold[gold["split"] == split]
            if len(sub) == 0:
                f.write(f"- `{split}`: 0 rows\n")
                continue
            f.write(f"- `{split}`: {len(sub)} rows, {sub['bytecode_family_id'].nunique()} families, "
                    f"first_observed_block range [{int(sub['first_observed_block'].min())}, "
                    f"{int(sub['first_observed_block'].max())}]\n")
    print(f"[gold] wrote {leakage_report_path} (leakage={'FAILED' if crossing else 'PASSED'})")

    for split in ["train", "val", "test"]:
        sub = gold[gold["split"] == split]
        sub.to_csv(os.path.join(split_dir, f"{run_id}_{split}.csv"), index=False)

    if crossing:
        raise SystemExit(f"[gold] REFUSING to report success: {len(crossing)} families leak across splits")


if __name__ == "__main__":
    main()
