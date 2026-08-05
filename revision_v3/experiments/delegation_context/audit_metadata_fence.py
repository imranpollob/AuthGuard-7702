#!/usr/bin/env python3
"""Label-free audit of the adversarial fence around Solidity CBOR metadata exclusion."""
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
import sys


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
V3 = os.path.join(REPO_ROOT, "revision_v3")
sys.path.insert(0, os.path.join(V3, "src"))
sys.path.insert(0, os.path.join(V3, "experiments", "opus5_labeling"))

from analysis.solidity_metadata import validated_solidity_metadata_start  # noqa: E402
from data.loader import load_primary_dataset  # noqa: E402
from evm_cfg import SENSITIVE, disassemble, static_opcode_census  # noqa: E402


COUNTED = set(SENSITIVE) | {"STATICCALL", "CALLER", "ORIGIN", "ADDRESS"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    primary = (
        load_primary_dataset().sort_values("sample_id").drop_duplicates("bytecode_sha256")
    )
    outcomes = Counter()
    eliminated = Counter()
    format_valid = 0
    for row in primary.itertuples(index=False):
        raw = str(row.runtime_bytecode)
        code = bytes.fromhex(raw[2:] if raw.startswith("0x") else raw)
        format_start = validated_solidity_metadata_start(code)
        format_valid += int(format_start < len(code))
        census = static_opcode_census(code)
        if census["metadata_recognized"]:
            outcomes["jump_fenced_metadata_excluded"] += 1
            full_counts = Counter(
                name for _, name, _ in disassemble(code) if name in COUNTED
            )
            fenced_counts = Counter(census["counts"])
            eliminated.update(full_counts - fenced_counts)
        elif census["metadata_rejection_reason"]:
            outcomes[str(census["metadata_rejection_reason"])] += 1
        else:
            outcomes["no_format_valid_metadata"] += 1
    report = {
        "status": "LABEL_FREE_ADVERSARIAL_METADATA_FENCE_AUDIT",
        "n_unique_runtimes": int(len(primary)),
        "n_format_valid_known_shape_cbor": format_valid,
        "outcome_counts": dict(sorted(outcomes.items())),
        "excluded_sensitive_or_context_opcode_bytes": dict(sorted(eliminated.items())),
        "safety_boundary": (
            "A format-valid trailer is retained whenever it overlaps an instruction, can be "
            "reached by fallthrough, or contains a valid JUMPDEST instruction. This does not "
            "treat arbitrary post-STOP bytes as metadata."
        ),
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
