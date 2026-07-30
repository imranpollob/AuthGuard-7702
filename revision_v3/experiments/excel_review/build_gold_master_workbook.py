"""Prepared (NOT executed as part of Phase 3A) generalization of build_master_workbook.py for
Gold-Dev / Gold-Test master adjudication workbooks. Not run in this phase -- see
build_gold_review_workbook.py's module docstring.

Usage (future):
    python3 revision_v3/experiments/excel_review/build_gold_master_workbook.py --sample-set gold_dev
    python3 revision_v3/experiments/excel_review/build_gold_master_workbook.py --sample-set gold_test
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_master_workbook import build_master_workbook  # noqa: E402
from build_gold_review_workbook import SAMPLE_SET_CONFIG  # noqa: E402

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
HUMAN_EVAL_DIR = os.path.join(REPO_ROOT, "revision_v3", "human_eval")

MASTER_OUT_NAMES = {
    "gold_dev": "Gold_Dev_Master_Adjudication.xlsx",
    "gold_test": "Gold_Test_Master_Adjudication.xlsx",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-set", required=True, choices=list(SAMPLE_SET_CONFIG))
    args = parser.parse_args()
    cfg = SAMPLE_SET_CONFIG[args.sample_set]

    build_master_workbook(
        manifest_path=os.path.join(HUMAN_EVAL_DIR, cfg["manifest"]),
        evidence_dump_path=os.path.join(HUMAN_EVAL_DIR, cfg["evidence_dump"]),
        llm_reviews_path=os.path.join(HUMAN_EVAL_DIR, cfg["llm_reviews"]),
        output_path=os.path.join(HUMAN_EVAL_DIR, MASTER_OUT_NAMES[args.sample_set]),
        review_set_name=args.sample_set.replace("_", "-").title(),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
