"""Stage 6b: validate a completed human-review queue CSV and merge it into
data/human_reviews/{run_id}_completed.jsonl, preserving the original LLM label alongside the
final human-reviewed label and full provenance (evidence path, LLM response, human decision,
comment). Only the final human-reviewed label may be used as the gold label downstream.

Usage: python3 dataset_pipeline/scripts/07_merge_human_reviews.py [--queue path/to/queue.csv]
Refuses to merge rows with an invalid decision/label combination; reports exactly which rows
are still incomplete instead of silently skipping them.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "dataset_pipeline")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pandas as pd  # noqa: E402

from lib.config import load_config  # noqa: E402

VALID_DECISIONS = {"ACCEPT_LLM_LABEL", "CHANGE_LABEL", "UNRESOLVED"}
VALID_LABELS = {"R1", "R2", "B", "U"}
VALID_CONFIDENCE = {"high", "medium", "low"}


def main():
    cfg = load_config()
    run_id = cfg["run_id"]
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue", default=os.path.join(cfg["_resolved_paths"]["human_reviews"], f"{run_id}_queue.csv"))
    args = ap.parse_args()

    queue = pd.read_csv(args.queue, keep_default_na=False)
    completed, incomplete, invalid = [], [], []

    for _, r in queue.iterrows():
        decision = str(r["decision"]).strip()
        if decision == "":
            incomplete.append(r["address"])
            continue
        if decision not in VALID_DECISIONS:
            invalid.append((r["address"], f"unknown decision {decision!r}"))
            continue

        if decision == "ACCEPT_LLM_LABEL":
            final_label = r["llm_proposed_label"]
            final_confidence = r["final_confidence"].strip() or r["llm_confidence"]
        elif decision == "CHANGE_LABEL":
            final_label = str(r["final_label"]).strip()
            final_confidence = str(r["final_confidence"]).strip()
            if final_label not in VALID_LABELS or final_confidence not in VALID_CONFIDENCE:
                invalid.append((r["address"], "CHANGE_LABEL requires a valid final_label and final_confidence"))
                continue
        else:  # UNRESOLVED
            final_label = "U"
            final_confidence = str(r["final_confidence"]).strip() or "low"

        completed.append({
            "chain": r["chain"], "address": r["address"], "evidence_path": r["evidence_path"],
            "llm_proposed_label": r["llm_proposed_label"], "llm_confidence": r["llm_confidence"],
            "llm_risk_categories": r["llm_risk_categories"], "llm_summary": r["llm_summary"],
            "human_decision": decision,
            "final_label": final_label, "final_confidence": final_confidence,
            "corrected_risk_categories": r["corrected_risk_categories"],
            "comment": r["comment"],
        })

    out_dir = cfg["_resolved_paths"]["human_reviews"]
    out_path = os.path.join(out_dir, f"{run_id}_completed.jsonl")
    with open(out_path, "w") as f:
        for rec in completed:
            f.write(json.dumps(rec) + "\n")

    summary = {
        "n_completed": len(completed), "n_incomplete": len(incomplete), "n_invalid": len(invalid),
        "incomplete_addresses": incomplete[:20], "invalid": invalid[:20],
        "completed_jsonl": out_path,
    }
    print(json.dumps(summary, indent=2))
    if incomplete or invalid:
        print(f"\n{len(incomplete)} rows still need a decision, {len(invalid)} rows are invalid. "
              "Not all rows are merged; re-run after completing the queue.")


if __name__ == "__main__":
    main()
