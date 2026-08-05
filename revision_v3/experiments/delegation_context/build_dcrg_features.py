"""Build reproducible DCRG artifacts for the frozen 2,190-item primary population.

The expensive bounded-CFG pass runs once per exact runtime hash and is resumable.  The output
keeps full graph evidence at the unique-runtime level and emits one fixed-order feature row per
benchmark sample for family-grouped modeling.  The historical dataset does not identify the
authorizing EOA, so authority-dependent fields remain explicitly unknown rather than using the
delegate implementation address as a substitute.

Usage:
    python3 revision_v3/experiments/delegation_context/build_dcrg_features.py
    python3 revision_v3/experiments/delegation_context/build_dcrg_features.py --limit 5
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import sys
from collections import Counter

import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
V3 = os.path.join(REPO_ROOT, "revision_v3")
sys.path.insert(0, os.path.join(V3, "src"))
sys.path.insert(0, os.path.join(V3, "experiments", "opus5_labeling"))

from analysis.delegation_context import (  # noqa: E402
    DCRG_FEATURE_ORDER,
    build_delegation_context_graph,
)
from data.loader import load_manifest, load_primary_dataset  # noqa: E402
from build_dossiers import cfg_analysis  # noqa: E402
from evm_cfg import Analyzer  # noqa: E402

DEFAULT_OUT = os.path.join(V3, "results", "delegation_context")


def file_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_completed(path: str) -> dict[str, dict]:
    completed = {}
    if not os.path.exists(path):
        return completed
    with open(path) as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise RuntimeError(f"invalid resume JSONL at line {line_number}: {error}") from error
            completed[record["bytecode_sha256"]] = record
    return completed


def analyze_runtime(bytecode_sha256: str, bytecode: str) -> dict:
    try:
        cfg = cfg_analysis(bytecode)
        graph = build_delegation_context_graph(cfg)
        error = None
    except Exception as exc:  # preserve the sample and make failure explicit, never infer safety
        cfg = {"error": f"{type(exc).__name__}: {exc}"}
        graph = build_delegation_context_graph(cfg)
        error = cfg["error"]
    return {
        "bytecode_sha256": bytecode_sha256,
        "authority_context": "UNKNOWN_IN_HISTORICAL_DATASET",
        "analysis_error": error,
        "cfg_summary": {
            "n_functions": cfg.get("n_functions"),
            "n_functions_using_state_widening": sum(
                bool(function.get("used_state_widening"))
                for function in (cfg.get("per_function") or [])
            ),
            "opcode_census_boundary": cfg.get("opcode_census_boundary"),
            "coverage_warning": cfg.get("coverage_warning"),
            "sensitive_opcodes_never_reached_by_analysis": (
                cfg.get("sensitive_opcodes_never_reached_by_analysis")
            ),
        },
        "dcrg": graph.to_dict(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default=DEFAULT_OUT)
    parser.add_argument("--limit", type=int, default=None,
                        help="analyze only the first N unique runtimes (smoke testing)")
    parser.add_argument("--force", action="store_true",
                        help="discard the resumable JSONL and recompute selected runtimes")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    suffix = f"_limit{args.limit}" if args.limit is not None else ""
    graph_path = os.path.join(args.out_dir, f"dcrg_unique_runtimes{suffix}.jsonl")
    feature_path = os.path.join(args.out_dir, f"dcrg_primary_features{suffix}.csv.gz")
    report_path = os.path.join(args.out_dir, f"dcrg_extraction_report{suffix}.json")
    if args.force and os.path.exists(graph_path):
        os.remove(graph_path)

    primary = load_primary_dataset()
    unique = (primary.sort_values("sample_id")
              .drop_duplicates("bytecode_sha256")
              [["bytecode_sha256", "runtime_bytecode"]])
    if args.limit is not None:
        unique = unique.head(args.limit)
    selected_hashes = set(unique["bytecode_sha256"])
    completed = load_completed(graph_path)

    mode = "a" if completed else "w"
    with open(graph_path, mode) as output:
        for position, row in enumerate(unique.itertuples(index=False), 1):
            bytecode_hash = str(row.bytecode_sha256)
            if bytecode_hash in completed:
                continue
            record = analyze_runtime(bytecode_hash, str(row.runtime_bytecode))
            output.write(json.dumps(record, sort_keys=True) + "\n")
            output.flush()
            completed[bytecode_hash] = record
            if position % 25 == 0 or position == len(unique):
                print(f"[dcrg] {position}/{len(unique)} unique runtimes", flush=True)

    missing = sorted(selected_hashes - set(completed))
    if missing:
        raise RuntimeError(f"extraction incomplete: {len(missing)} selected hashes missing")

    sample_rows = []
    selected_primary = primary[primary["bytecode_sha256"].isin(selected_hashes)].copy()
    for row in selected_primary.itertuples(index=False):
        record = completed[str(row.bytecode_sha256)]
        dcrg = record["dcrg"]
        feature_row = {
            "sample_id": row.sample_id,
            "family_id": row.family_id,
            "fold_id": int(row.fold_id),
            "bytecode_sha256": row.bytecode_sha256,
            "label": int(row.label),
            "coverage": dcrg["coverage"],
            "analysis_error": record["analysis_error"],
            "findings": "|".join(dcrg["findings"]),
        }
        feature_row.update({name: float(dcrg["features"][name])
                            for name in DCRG_FEATURE_ORDER})
        sample_rows.append(feature_row)
    feature_df = pd.DataFrame(sample_rows)
    feature_df.to_csv(feature_path, index=False, compression="gzip")

    coverage_by_unique = Counter(
        completed[h]["dcrg"]["coverage"] for h in selected_hashes
    )
    report = {
        "status": "COMPLETE" if args.limit is None else "SMOKE_TEST_LIMITED",
        "schema_version": "dcrg-1.1",
        "analysis_version": "bounded-cfg-1.3-jump-fenced-metadata-state-widening",
        "authority_context": "UNKNOWN_IN_HISTORICAL_DATASET",
        "canonical_input_sha256": load_manifest()["sha256"]["benchmark_csv_gz"],
        "extractor_sha256": {
            "build_dcrg_features.py": file_sha256(__file__),
            "build_dossiers.py": file_sha256(os.path.join(
                V3, "experiments", "opus5_labeling", "build_dossiers.py"
            )),
            "delegation_context.py": file_sha256(os.path.join(
                V3, "src", "analysis", "delegation_context.py"
            )),
            "protocol_actors.py": file_sha256(os.path.join(
                V3, "src", "analysis", "protocol_actors.py"
            )),
            "evm_cfg.py": file_sha256(os.path.join(
                V3, "experiments", "opus5_labeling", "evm_cfg.py"
            )),
            "solidity_metadata.py": file_sha256(os.path.join(
                V3, "src", "analysis", "solidity_metadata.py"
            )),
        },
        "analysis_parameters": {
            "max_states": Analyzer.MAX_STATES,
            "max_states_per_pc": Analyzer.MAX_PER_PC,
            "state_widen_after_visits": Analyzer.WIDEN_AFTER,
            "max_symbolic_stack_values": Analyzer.MAX_STACK,
            "metadata_exclusion_rule": (
                "exact known-shape Solidity CBOR; instruction-aligned start; terminal "
                "predecessor; no disassembled JUMPDEST in trailer"
            ),
        },
        "runtime_versions": {
            "python": platform.python_version(),
            "cbor2": importlib.metadata.version("cbor2"),
            "evmole": importlib.metadata.version("evmole"),
        },
        "n_primary_samples": int(len(selected_primary)),
        "n_unique_runtimes": int(len(selected_hashes)),
        "n_analysis_errors_unique": int(sum(
            completed[h]["analysis_error"] is not None for h in selected_hashes
        )),
        "coverage_unique_runtimes": dict(sorted(coverage_by_unique.items())),
        "coverage_primary_samples": dict(sorted(Counter(feature_df["coverage"]).items())),
        "feature_order": list(DCRG_FEATURE_ORDER),
        "artifacts": {
            "unique_runtime_graphs": os.path.relpath(graph_path, REPO_ROOT),
            "sample_features": os.path.relpath(feature_path, REPO_ROOT),
        },
        "limitations": [
            "Historical rows identify delegate implementations but not authorizing EOAs; "
            "authority-dependent comparisons remain unknown.",
            "PARTIAL and UNKNOWN coverage are retained as model inputs and must trigger "
            "selective-policy analysis rather than being interpreted as safe.",
            "Loop-state widening over-approximates varying non-control constants after eight "
            "visits; valid JUMPDEST constants remain concrete, and unresolved transfers still "
            "produce PARTIAL coverage.",
        ],
    }
    with open(report_path, "w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
