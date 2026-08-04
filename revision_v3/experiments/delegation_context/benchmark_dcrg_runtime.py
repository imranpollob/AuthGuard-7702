"""End-to-end CPU latency benchmark for bytecode -> CFG -> DCRG extraction."""
from __future__ import annotations

import json
import os
import platform
import resource
import statistics
import sys
import time

import numpy as np
import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
V3 = os.path.join(REPO_ROOT, "revision_v3")
sys.path.insert(0, os.path.join(V3, "src"))
sys.path.insert(0, os.path.join(V3, "experiments", "opus5_labeling"))

from analysis.delegation_context import build_delegation_context_graph  # noqa: E402
from data.loader import load_manifest, load_primary_dataset  # noqa: E402
from build_dossiers import cfg_analysis  # noqa: E402

OUT_DIR = os.path.join(V3, "results", "delegation_context")


def percentile(values, quantile: float) -> float:
    return float(np.percentile(np.asarray(values, dtype=np.float64), quantile))


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    primary = load_primary_dataset()
    unique = (primary.sort_values("sample_id").drop_duplicates("bytecode_sha256")
              [["bytecode_sha256", "runtime_bytecode", "code_bytes"]])

    # Import/cache warm-up is excluded; this runtime is analyzed again in the measured loop.
    warm_cfg = cfg_analysis(str(unique.iloc[0]["runtime_bytecode"]))
    build_delegation_context_graph(warm_cfg)

    records = []
    for position, row in enumerate(unique.itertuples(index=False), 1):
        start = time.perf_counter_ns()
        error = None
        try:
            graph = build_delegation_context_graph(cfg_analysis(str(row.runtime_bytecode)))
            coverage = graph.coverage.value
        except Exception as exc:
            coverage = "UNKNOWN"
            error = f"{type(exc).__name__}: {exc}"
        elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
        records.append({
            "bytecode_sha256": row.bytecode_sha256,
            "code_bytes": int(row.code_bytes),
            "elapsed_ms": elapsed_ms,
            "coverage": coverage,
            "analysis_error": error,
        })
        if position % 100 == 0 or position == len(unique):
            print(f"[dcrg_runtime] {position}/{len(unique)}", flush=True)

    frame = pd.DataFrame(records)
    raw_path = os.path.join(OUT_DIR, "dcrg_runtime_per_unique.csv.gz")
    frame.to_csv(raw_path, index=False, compression="gzip")
    latencies = frame["elapsed_ms"].tolist()
    report = {
        "status": "COMPLETE",
        "scope": "runtime bytecode -> bounded CFG/symbolic analysis -> dcrg-1.1 graph",
        "device": "CPU",
        "n_unique_runtimes": len(frame),
        "n_analysis_errors": int(frame["analysis_error"].notna().sum()),
        "latency_ms": {
            "mean": float(statistics.mean(latencies)),
            "median": float(statistics.median(latencies)),
            "p95": percentile(latencies, 95),
            "p99": percentile(latencies, 99),
            "max": float(max(latencies)),
        },
        "coverage_counts": frame["coverage"].value_counts().sort_index().to_dict(),
        "peak_process_rss_kib": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
        "environment": {
            "platform": platform.platform(),
            "processor": platform.processor(),
            "python": platform.python_version(),
        },
        "canonical_input_sha256": load_manifest()["sha256"]["benchmark_csv_gz"],
        "raw_artifact": os.path.relpath(raw_path, REPO_ROOT),
        "interpretation": (
            "This is semantic extraction latency, separate from neural forward-pass latency. "
            "PARTIAL coverage remains a defer signal even when extraction terminates quickly."
        ),
    }
    with open(os.path.join(OUT_DIR, "dcrg_runtime_report.json"), "w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    print(json.dumps(report, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
