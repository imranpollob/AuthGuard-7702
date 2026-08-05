"""Prepared (NOT executed as part of Phase 3A) generator for Gold-Dev / Gold-Test review
workbooks and their master adjudication workbooks. Generalizes build_pilot_workbook.py /
build_master_workbook.py to any sample set via --sample-set.

Per the Phase 3A instructions: do not generate LLM reviews for Gold-Test yet unless
explicitly instructed after the Pilot, and do not begin Gold-Dev or Gold-Test review. This
script is written and tested for import-time correctness (see
revision_v3/tests/test_phase3a_excel_review.py::test_gold_exporters_importable) but has NOT
been run to produce Gold_Dev_Review.xlsx or Gold_Test_Review.xlsx -- no such files exist in
this repository as of Phase 3A. If no LLM-review file exists yet for the requested sample set,
the LLM columns are left explicitly blank (never fabricated).

Usage (future, once explicitly instructed):
    python3 revision_v3/experiments/excel_review/build_gold_review_workbook.py --sample-set gold_dev
    python3 revision_v3/experiments/excel_review/build_gold_review_workbook.py --sample-set gold_test
"""
from __future__ import annotations

import argparse
import os
import sys

from openpyxl import Workbook

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from excel_builder import (  # noqa: E402
    build_checklist_sheet, build_examples_sheet, build_guide_sheet, build_items_sheet,
    build_start_here_sheet, load_manifest_rows, load_packets_by_item_id,
    protect_lead_author_columns,
)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
HUMAN_EVAL_DIR = os.path.join(REPO_ROOT, "revision_v3", "human_eval")

SAMPLE_SET_CONFIG = {
    "gold_dev": {
        "manifest": "gold_dev_manifest.csv",
        "evidence_dump": os.path.join("llm_reviews", "gold_dev_evidence_dump.json"),
        "llm_reviews": os.path.join("llm_reviews", "gold_dev_llm_reviews.json"),
        "workbook_out": "Gold_Dev_Review.xlsx",
        "items_sheet": "GOLD_DEV_ITEMS",
        "expected_n_items": 60,
    },
    "gold_test": {
        "manifest": "gold_test_manifest.csv",
        "evidence_dump": os.path.join("llm_reviews", "gold_test_evidence_dump.json"),
        "llm_reviews": os.path.join("llm_reviews", "gold_test_llm_reviews.json"),
        "workbook_out": "Gold_Test_Review.xlsx",
        "items_sheet": "GOLD_TEST_ITEMS",
        "expected_n_items": 150,
    },
}


def load_llm_reviews_if_present(path: str) -> dict:
    if not os.path.exists(path):
        print(f"[build_gold_review_workbook] no LLM review file at {path} yet -- "
              "LLM columns will be left blank, not fabricated.")
        return {}
    import json
    with open(path) as f:
        return json.load(f)["reviews"]


def build(sample_set: str) -> str:
    if sample_set not in SAMPLE_SET_CONFIG:
        raise ValueError(f"unknown sample_set {sample_set!r}, expected one of {list(SAMPLE_SET_CONFIG)}")
    cfg = SAMPLE_SET_CONFIG[sample_set]

    manifest_path = os.path.join(HUMAN_EVAL_DIR, cfg["manifest"])
    evidence_dump_path = os.path.join(HUMAN_EVAL_DIR, cfg["evidence_dump"])
    llm_reviews_path = os.path.join(HUMAN_EVAL_DIR, cfg["llm_reviews"])
    out_path = os.path.join(HUMAN_EVAL_DIR, cfg["workbook_out"])

    manifest_rows = load_manifest_rows(manifest_path)
    assert len(manifest_rows) == cfg["expected_n_items"], (
        f"expected {cfg['expected_n_items']} {sample_set} items, found {len(manifest_rows)} "
        "-- refusing to build (the frozen sample must not have changed)"
    )

    if not os.path.exists(evidence_dump_path):
        raise FileNotFoundError(
            f"{evidence_dump_path} does not exist -- run the equivalent of "
            "dump_pilot_evidence.py for this sample set first (not done automatically here, "
            "per the instruction not to begin Gold-Dev/Gold-Test review yet)"
        )
    packets_by_item = load_packets_by_item_id(evidence_dump_path, manifest_rows)
    llm_reviews = load_llm_reviews_if_present(llm_reviews_path)

    wb = Workbook()
    wb.remove(wb.active)
    build_start_here_sheet(wb, review_set_name=sample_set.replace("_", "-").title(), n_items=len(manifest_rows))
    build_guide_sheet(wb)
    build_checklist_sheet(wb)
    build_examples_sheet(wb)
    build_items_sheet(wb, cfg["items_sheet"], manifest_rows, packets_by_item, llm_reviews)
    protect_lead_author_columns(wb[cfg["items_sheet"]], n_rows=len(manifest_rows))
    wb.active = 0

    os.makedirs(HUMAN_EVAL_DIR, exist_ok=True)
    wb.save(out_path)
    print(f"wrote {out_path} ({len(manifest_rows)} items, "
          f"{'with' if llm_reviews else 'WITHOUT (none generated yet)'} LLM reviews)")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-set", required=True, choices=list(SAMPLE_SET_CONFIG))
    args = parser.parse_args()
    build(args.sample_set)
    return 0


if __name__ == "__main__":
    sys.exit(main())
