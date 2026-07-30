"""Builds the full evidence packet for every Pilot item (reusing Phase 2's evidence pipeline)
and writes a human/LLM-readable dump for analysis. Strictly excludes source_label,
pilot_reason, and every other forbidden field -- only chain/address/bytecode/family_id are
read from the manifest.
"""
from __future__ import annotations

import json
import os
import sys

import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "revision_v3", "src"))

from evidence.packet_builder import build_evidence_packet  # noqa: E402
from features.selectors import build_sensitive_selector_set  # noqa: E402

MANIFEST_PATH = os.path.join(REPO_ROOT, "revision_v3", "human_eval", "pilot_manifest.csv")
OUT_PATH = os.path.join(REPO_ROOT, "revision_v3", "human_eval", "llm_reviews", "pilot_evidence_dump.json")


def main() -> int:
    manifest = pd.read_csv(MANIFEST_PATH)
    sensitive_selectors = build_sensitive_selector_set()

    packets = []
    for _, row in manifest.iterrows():
        safe_row = {
            "sample_id": row["item_id"], "chain": row["chain"], "address": row["address"],
            "runtime_bytecode": row["runtime_bytecode"],
        }
        packet = build_evidence_packet(safe_row, sensitive_selectors=sensitive_selectors)
        # trim disassembly for the dump (kept in the workbook separately if needed); full
        # opcode list is large and not needed for manual LLM reading of this dump file.
        packet_for_dump = {k: v for k, v in packet.items() if k != "opcode_disassembly"}
        packet_for_dump["opcode_disassembly_first_60"] = packet["opcode_disassembly"][:60]
        packet_for_dump["opcode_disassembly_full_length"] = len(packet["opcode_disassembly"])
        packets.append(packet_for_dump)

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(packets, f, indent=2, default=str)
    print(f"wrote {len(packets)} evidence packets -> {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
