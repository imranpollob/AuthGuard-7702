"""Prepared (NOT executed as part of Phase 3A) generalization of dump_pilot_evidence.py for
Gold-Dev / Gold-Test. Builds the evidence packet for every item in the requested sample set.
Not run in this phase -- see build_gold_review_workbook.py's module docstring.

Usage (future):
    python3 revision_v3/experiments/excel_review/dump_gold_evidence.py --sample-set gold_dev
    python3 revision_v3/experiments/excel_review/dump_gold_evidence.py --sample-set gold_test
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "revision_v3", "src"))

from evidence.packet_builder import build_evidence_packet  # noqa: E402
from features.selectors import build_sensitive_selector_set  # noqa: E402

HUMAN_EVAL_DIR = os.path.join(REPO_ROOT, "revision_v3", "human_eval")

MANIFESTS = {
    "gold_dev": ("gold_dev_manifest.csv", "gold_dev_evidence_dump.json", 60),
    "gold_test": ("gold_test_manifest.csv", "gold_test_evidence_dump.json", 150),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-set", required=True, choices=list(MANIFESTS))
    args = parser.parse_args()

    manifest_name, out_name, expected_n = MANIFESTS[args.sample_set]
    manifest_path = os.path.join(HUMAN_EVAL_DIR, manifest_name)
    out_path = os.path.join(HUMAN_EVAL_DIR, "llm_reviews", out_name)

    manifest = pd.read_csv(manifest_path)
    assert len(manifest) == expected_n, f"expected {expected_n} rows, found {len(manifest)}"

    sensitive_selectors = build_sensitive_selector_set()
    packets = []
    for _, row in manifest.iterrows():
        safe_row = {
            "sample_id": row["item_id"], "chain": row["chain"], "address": row["address"],
            "runtime_bytecode": row["runtime_bytecode"],
        }
        packet = build_evidence_packet(safe_row, sensitive_selectors=sensitive_selectors)
        packet_for_dump = {k: v for k, v in packet.items() if k != "opcode_disassembly"}
        packet_for_dump["opcode_disassembly_first_60"] = packet["opcode_disassembly"][:60]
        packet_for_dump["opcode_disassembly_full_length"] = len(packet["opcode_disassembly"])
        packets.append(packet_for_dump)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(packets, f, indent=2, default=str)
    print(f"wrote {len(packets)} evidence packets -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
