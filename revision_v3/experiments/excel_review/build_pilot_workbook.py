"""Builds revision_v3/human_eval/Pilot_Review.xlsx from the existing (unmodified) 20-item
Pilot manifest, the evidence dump, and the LLM preliminary reviews.
"""
from __future__ import annotations

import os
import sys

from openpyxl import Workbook

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from excel_builder import (  # noqa: E402
    build_checklist_sheet, build_examples_sheet, build_guide_sheet, build_items_sheet,
    build_start_here_sheet, load_llm_reviews, load_manifest_rows, load_packets_by_item_id,
    protect_lead_author_columns,
)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
HUMAN_EVAL_DIR = os.path.join(REPO_ROOT, "revision_v3", "human_eval")

MANIFEST_PATH = os.path.join(HUMAN_EVAL_DIR, "pilot_manifest.csv")
EVIDENCE_DUMP_PATH = os.path.join(HUMAN_EVAL_DIR, "llm_reviews", "pilot_evidence_dump.json")
LLM_REVIEWS_PATH = os.path.join(HUMAN_EVAL_DIR, "llm_reviews", "pilot_llm_reviews.json")
OUT_PATH = os.path.join(HUMAN_EVAL_DIR, "Pilot_Review.xlsx")


def main() -> int:
    manifest_rows = load_manifest_rows(MANIFEST_PATH)
    assert len(manifest_rows) == 20, f"expected 20 Pilot items, found {len(manifest_rows)}"

    packets_by_item = load_packets_by_item_id(EVIDENCE_DUMP_PATH, manifest_rows)
    llm_reviews = load_llm_reviews(LLM_REVIEWS_PATH)

    wb = Workbook()
    wb.remove(wb.active)  # drop the default empty sheet; build_start_here_sheet inserts at index 0

    build_start_here_sheet(wb, review_set_name="Pilot", n_items=len(manifest_rows))
    build_guide_sheet(wb)
    build_checklist_sheet(wb)
    build_examples_sheet(wb)
    build_items_sheet(wb, "PILOT_ITEMS", manifest_rows, packets_by_item, llm_reviews)

    ws_items = wb["PILOT_ITEMS"]
    protect_lead_author_columns(ws_items, n_rows=len(manifest_rows))

    wb.active = 0
    os.makedirs(HUMAN_EVAL_DIR, exist_ok=True)
    wb.save(OUT_PATH)
    print(f"wrote {OUT_PATH} ({len(manifest_rows)} items)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
