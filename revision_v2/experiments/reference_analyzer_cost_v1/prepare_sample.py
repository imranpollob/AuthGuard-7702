#!/usr/bin/env python3
"""Prepare the frozen family-distinct Gigahorse timing sample."""
from __future__ import annotations

import argparse
import hashlib
import json
import os

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RV2 = os.path.abspath(os.path.join(HERE, "..", ".."))
BENCH = os.path.join(RV2, "data", "authguardbench_7702_v2.csv.gz")
DEFAULT_OUT = os.path.join(HERE, "sample")
SALT = "AUTHGUARD_REFERENCE_ANALYZER_COST_V1"


def deterministic_key(sample_id: str) -> str:
    return hashlib.sha256(f"{SALT}:{sample_id}".encode()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=DEFAULT_OUT)
    parser.add_argument("--per-cell", type=int, default=2)
    args = parser.parse_args()
    output = os.path.abspath(args.output_dir)
    input_dir = os.path.join(output, "inputs")
    os.makedirs(input_dir, exist_ok=True)

    frame = pd.read_csv(BENCH)
    frame = frame[frame["population"] == "PRIMARY_EVALUATION"].copy()
    frame["length_stratum"] = pd.cut(
        frame["opcode_count"],
        bins=[-1, 2_048, 4_096, float("inf")],
        labels=["le_2048", "2049_4096", "gt_4096"],
    )
    frame["selection_key"] = frame["sample_id"].astype(str).map(deterministic_key)
    frame = frame.sort_values("selection_key")

    selected = []
    used_families = set()
    # Select rare long programs first so globally unique families cannot starve a cell.
    for stratum in ("gt_4096", "2049_4096", "le_2048"):
        for label in (0, 1):
            for fold in range(5):
                candidates = frame[
                    (frame["label"] == label)
                    & (frame["length_stratum"].astype(str) == stratum)
                    & (frame["fold_id"] == fold)
                ]
                cell = []
                for _, row in candidates.iterrows():
                    family = str(row["family_id"])
                    if family in used_families:
                        continue
                    used_families.add(family)
                    cell.append(row)
                    if len(cell) == args.per_cell:
                        break
                if len(cell) != args.per_cell:
                    raise RuntimeError(
                        f"insufficient unique families label={label} "
                        f"stratum={stratum} fold={fold}")
                selected.extend(cell)

    manifest_rows = []
    for index, row in enumerate(selected):
        sample_name = f"sample_{index:03d}.hex"
        bytecode = str(row["runtime_bytecode"])
        normalized = bytecode[2:] if bytecode.startswith("0x") else bytecode
        if not normalized or len(normalized) % 2:
            raise ValueError(f"invalid bytecode for {row['sample_id']}")
        with open(os.path.join(input_dir, sample_name), "w", encoding="ascii") as handle:
            handle.write(normalized.lower() + "\n")
        manifest_rows.append({
            "sample_file": sample_name,
            "sample_id": row["sample_id"],
            "chain": row["chain"],
            "address": row["address"],
            "family_id": row["family_id"],
            "fold_id": int(row["fold_id"]),
            "label": int(row["label"]),
            "label_semantics": row["label_semantics"],
            "length_stratum": str(row["length_stratum"]),
            "opcode_count": int(row["opcode_count"]),
            "code_bytes": int(row["code_bytes"]),
            "bytecode_sha256": row["bytecode_sha256"],
            "selection_key": row["selection_key"],
        })

    manifest = pd.DataFrame(manifest_rows)
    if manifest["family_id"].nunique() != len(manifest):
        raise AssertionError("sample families are not globally unique")
    manifest.to_csv(os.path.join(output, "sample_manifest.csv"), index=False)
    with open(os.path.join(output, "sample_summary.json"), "w", encoding="utf-8") as handle:
        json.dump({
            "sample_rows": len(manifest),
            "families": int(manifest["family_id"].nunique()),
            "per_cell": args.per_cell,
            "selection_salt": SALT,
            "cells": (
                manifest.groupby(["label", "length_stratum", "fold_id"])
                .size()
                .rename("rows")
                .reset_index()
                .to_dict("records")
            ),
        }, handle, indent=2)
    print(
        f"REFERENCE_ANALYZER_SAMPLE_READY rows={len(manifest)} "
        f"families={manifest['family_id'].nunique()} output={output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
