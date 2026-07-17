#!/usr/bin/env python3
"""Operational runtime benchmark for the selected AuthGuard sequence scorer."""
from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import sys
import time

import numpy as np
import pandas as pd
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
RV2 = os.path.abspath(os.path.join(HERE, "..", ".."))
ROOT = os.path.abspath(os.path.join(RV2, ".."))
sys.path.insert(0, RV2)

from authguard7702.scorer import AuthGuardScorer  # noqa: E402

DEFAULT_MODEL = os.path.join(RV2, "results", "authguard_fusion",
                             "model_sequence_only_s7702_f0.pt")
SOURCE = os.path.join(ROOT, "paper_build", "data_hygiene", "task_aligned_dataset_v1.csv")
OUT = os.path.join(RV2, "results", "authguard_fusion", "runtime_sequence.json")


def stats(values):
    values = np.asarray(values, dtype=float)
    return {
        "mean": float(values.mean()),
        "std": float(values.std()),
        "p50": float(np.percentile(values, 50)),
        "p95": float(np.percentile(values, 95)),
        "p99": float(np.percentile(values, 99)),
        "min": float(values.min()),
        "max": float(values.max()),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--sample-size", type=int, default=300)
    parser.add_argument("--passes", type=int, default=10)
    parser.add_argument("--warmup", type=int, default=30)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    frame = pd.read_csv(SOURCE)
    primary = frame[frame["class"].isin(["malicious", "benign_cleared"])]
    size = min(args.sample_size, len(primary))
    sample = primary.sample(size, random_state=7702)["bytecode"].astype(str).tolist()
    if args.validate_only:
        sample, args.passes, args.warmup = sample[:3], 1, 1

    load_started = time.perf_counter_ns()
    scorer = AuthGuardScorer(args.model, args.device)
    load_ms = (time.perf_counter_ns() - load_started) / 1e6
    for index in range(args.warmup):
        scorer.score_bytecode(sample[index % len(sample)])
    elapsed, internal = [], []
    for _ in range(args.passes):
        for bytecode in sample:
            started = time.perf_counter_ns()
            result = scorer.score_bytecode(bytecode)
            elapsed.append((time.perf_counter_ns() - started) / 1e6)
            internal.append(result["local_scorer_ms"])
    result = {
        "scope": "local sequence preprocessing, model prediction, policy, evidence, and JSON-ready result",
        "excludes": ["RPC", "network", "wallet UI", "process startup", "model loading"],
        "device": args.device,
        "environment": {
            "platform": platform.platform(),
            "processor": platform.processor(),
            "python": platform.python_version(),
            "torch": torch.__version__,
        },
        "model": os.path.relpath(args.model, ROOT),
        "model_bytes": os.path.getsize(args.model),
        "model_load_ms": float(load_ms),
        "sample_size": len(sample),
        "passes": args.passes,
        "timed_calls": len(elapsed),
        "wall_milliseconds": stats(elapsed),
        "internal_milliseconds": stats(internal),
        "bytecode_preloaded": True,
    }
    if args.validate_only:
        print(json.dumps(result, indent=2)); return
    with open(OUT, "w") as handle:
        json.dump(result, handle, indent=2)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

