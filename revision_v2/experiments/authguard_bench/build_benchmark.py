#!/usr/bin/env python3
"""Build the AuthGuardBench-7702 manifest and compact opcode cache.

The frozen task-aligned dataset is read-only. Every generated artifact is written beneath
revision_v2/results/authguard_bench.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RV2 = os.path.abspath(os.path.join(HERE, "..", ".."))
ROOT = os.path.abspath(os.path.join(RV2, ".."))
sys.path.insert(0, RV2)
sys.path.insert(0, os.path.join(RV2, "experiments", "common"))

from authguard7702.features import (AUXILIARY_FACTORS, TOKEN_TO_ID, UNK_ID,
                                    auxiliary_targets)  # noqa: E402
from frozen import verify as verify_frozen  # noqa: E402

OUT = os.path.join(RV2, "results", "authguard_bench")
SOURCE = os.path.join(ROOT, "paper_build", "data_hygiene", "task_aligned_dataset_v1.csv")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def build(validate_only: bool = False):
    if verify_frozen() != 0:
        raise RuntimeError("frozen-artifact verification failed")
    frame = pd.read_csv(SOURCE)
    required = {"chain", "address", "bytecode", "class", "family_id",
                "outer_fold_primary", "outer_fold_secondary"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"missing source columns: {sorted(missing)}")

    from authguard7702.features import disasm, normalize_bytecode
    rows, token_rows, auxiliary_rows = [], [], []
    selected = frame.head(32) if validate_only else frame
    for _, row in selected.iterrows():
        bytecode = normalize_bytecode(row["bytecode"])
        ops, _, _ = disasm(bytecode)
        tokens = np.asarray([TOKEN_TO_ID.get(op, UNK_ID) for op in ops], dtype=np.uint16)
        if not len(tokens):
            tokens = np.asarray([UNK_ID], dtype=np.uint16)
        auxiliary, evidence = auxiliary_targets(bytecode)
        sid = f"{row['chain']}:{row['address']}"
        rows.append({
            "sid": sid,
            "chain": row["chain"],
            "address": row["address"],
            "bytecode_sha256": sha256_text(bytecode),
            "code_bytes": evidence["code_bytes"],
            "opcode_count": evidence["opcode_count"],
            "label": int(row["class"] == "malicious"),
            "class": row["class"],
            "family_id": row["family_id"],
            "outer_fold_primary": row["outer_fold_primary"],
            "outer_fold_secondary": row["outer_fold_secondary"],
            "label_provenance": "task_aligned_dataset_v1",
            **{name: int(value) for name, value in zip(AUXILIARY_FACTORS, auxiliary)},
        })
        token_rows.append(tokens)
        auxiliary_rows.append(auxiliary)

    manifest = pd.DataFrame(rows)
    assert manifest["sid"].is_unique
    duplicate_sizes = manifest.groupby("bytecode_sha256")["sid"].transform("size")
    manifest["exact_duplicate_count"] = duplicate_sizes.astype(int)
    manifest["bytecode_group_id"] = manifest["bytecode_sha256"].map(
        lambda value: "B" + value[:16])
    primary = manifest[manifest["class"].isin(["malicious", "benign_cleared"])]
    if not validate_only:
        assert len(primary) == 2280
        assert primary["outer_fold_primary"].notna().all()
        assert primary.groupby("family_id")["outer_fold_primary"].nunique().max() == 1
        assert primary.groupby("bytecode_group_id")["outer_fold_primary"].nunique().max() == 1, \
            "exact duplicate bytecode crosses primary folds"
        assert primary.groupby("bytecode_group_id")["label"].nunique().max() == 1, \
            "exact duplicate bytecode has conflicting primary labels"

    offsets = np.zeros(len(token_rows) + 1, dtype=np.int64)
    offsets[1:] = np.cumsum([len(tokens) for tokens in token_rows])
    concatenated = np.concatenate(token_rows) if token_rows else np.empty(0, dtype=np.uint16)
    summary = {
        "name": "AuthGuardBench-7702",
        "version": "0.1.0",
        "source": os.path.relpath(SOURCE, ROOT),
        "rows": int(len(manifest)),
        "primary_rows": int(len(primary)),
        "class_counts": manifest["class"].value_counts().to_dict(),
        "primary_family_count": int(primary["family_id"].nunique()),
        "unique_bytecode_count": int(manifest["bytecode_group_id"].nunique()),
        "rows_in_exact_duplicate_groups": int(
            (manifest["exact_duplicate_count"] > 1).sum()),
        "exact_duplicate_group_count": int(
            manifest.loc[manifest["exact_duplicate_count"] > 1,
                         "bytecode_group_id"].nunique()),
        "factor_prevalence": {
            name: float(manifest[name].mean()) for name in AUXILIARY_FACTORS
        },
        "split_policy": "frozen family-disjoint outer folds",
        "primary_metric": "Recall at validation-matched 5% FPR",
        "threshold_free_metric": "AUPRC",
        "scope": {
            "auxiliary_factors": "bytecode-observable surfaces, not reachability or intent",
            "transformations": "bounded protocol transformations only",
            "runtime": "report scorer, loading, RPC, and CLI stages separately",
        },
    }
    if validate_only:
        print(json.dumps({"validation_rows": len(manifest), **summary}, indent=2))
        if verify_frozen() != 0:
            raise RuntimeError("frozen-artifact verification failed")
        return

    os.makedirs(OUT, exist_ok=True)
    manifest.to_csv(os.path.join(OUT, "manifest.csv"), index=False)
    np.savez_compressed(os.path.join(OUT, "opcode_tokens.npz"),
                        tokens=concatenated, offsets=offsets,
                        auxiliary=np.stack(auxiliary_rows).astype(np.float32))
    with open(os.path.join(OUT, "benchmark_summary.json"), "w") as handle:
        json.dump(summary, handle, indent=2)
    schema = {
        "manifest_columns": {column: str(dtype) for column, dtype in manifest.dtypes.items()},
        "auxiliary_factor_order": list(AUXILIARY_FACTORS),
        "token_cache": {
            "tokens": "concatenated uint16 opcode token IDs",
            "offsets": "int64 row boundaries, length rows+1",
            "auxiliary": "float32 observable-factor targets",
        },
    }
    with open(os.path.join(OUT, "schema.json"), "w") as handle:
        json.dump(schema, handle, indent=2)
    if verify_frozen() != 0:
        raise RuntimeError("frozen-artifact verification failed")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    started = time.time()
    build(args.validate_only)
    print(f"[authguard-bench] elapsed={time.time() - started:.2f}s")
