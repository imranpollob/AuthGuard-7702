"""Extract authority-aware DCRG artifacts for the frozen post-cutoff candidate snapshot.

No labels are read and no classifier is fit or scored.  CFG analysis is cached per exact
runtime; DCRG construction is repeated per authority/delegate pair so authority-match features
retain their intended EIP-7702 semantics.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
V3 = os.path.join(REPO_ROOT, "revision_v3")
sys.path.insert(0, os.path.join(V3, "src"))
sys.path.insert(0, os.path.join(V3, "experiments", "opus5_labeling"))

from analysis.delegation_context import (  # noqa: E402
    DCRG_FEATURE_ORDER,
    build_delegation_context_graph,
)
from build_dossiers import cfg_analysis  # noqa: E402

RESULTS_DIR = os.path.join(V3, "results", "postcutoff_snapshot")
SNAPSHOT_PATH = os.path.join(RESULTS_DIR, "ethereum_candidates.csv.gz")
SNAPSHOT_REPORT_PATH = os.path.join(RESULTS_DIR, "ethereum_snapshot_report.json")
FEATURE_PATH = os.path.join(RESULTS_DIR, "postcutoff_authority_dcrg_features.csv.gz")
GRAPH_PATH = os.path.join(RESULTS_DIR, "postcutoff_authority_dcrg_graphs.jsonl")
REPORT_PATH = os.path.join(RESULTS_DIR, "postcutoff_authority_dcrg_report.json")


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    with open(SNAPSHOT_REPORT_PATH) as handle:
        snapshot_report = json.load(handle)
    snapshot_hash = _sha256_file(SNAPSHOT_PATH)
    if snapshot_report.get("status") != "FROZEN_POSTCUTOFF_CANDIDATE_SNAPSHOT_UNLABELED":
        raise RuntimeError("snapshot report does not preserve the required unlabeled status")
    if snapshot_report.get("snapshot_sha256") != snapshot_hash:
        raise RuntimeError("snapshot artifact hash does not match its frozen report")
    snapshot = pd.read_csv(SNAPSHOT_PATH)
    eligible = snapshot[
        snapshot["fetch_error"].isna() & (snapshot["historical_code_bytes"] > 0)
    ].copy()
    cfg_by_hash = {}
    analysis_error_by_hash: dict[str, str | None] = {}
    feature_rows = []
    coverage_counts: dict[str, int] = {}
    graph_tmp = GRAPH_PATH + ".tmp"
    feature_tmp = FEATURE_PATH + ".tmp"
    with open(graph_tmp, "w") as graph_handle:
        for position, row in enumerate(eligible.itertuples(index=False), 1):
            bytecode_hash = row.historical_bytecode_sha256
            if bytecode_hash not in cfg_by_hash:
                try:
                    cfg_by_hash[bytecode_hash] = cfg_analysis(
                        row.historical_runtime_bytecode
                    )
                    analysis_error_by_hash[bytecode_hash] = None
                except Exception as error:  # preserve the pair and make uncertainty explicit
                    message = f"{type(error).__name__}: {error}"
                    cfg_by_hash[bytecode_hash] = {"error": message}
                    analysis_error_by_hash[bytecode_hash] = message
            graph = build_delegation_context_graph(
                cfg_by_hash[bytecode_hash], authority_address=row.authority_address
            )
            payload = graph.to_dict()
            payload.update({
                "sample_id": f"ethereum:{row.delegate_address}",
                "delegate_address": row.delegate_address,
                "authority_address": row.authority_address,
                "bytecode_sha256": bytecode_hash,
                "postcutoff_exact_runtime_family": row.postcutoff_exact_runtime_family,
            })
            graph_handle.write(json.dumps(payload, sort_keys=True) + "\n")
            feature_rows.append({
                "sample_id": payload["sample_id"],
                "delegate_address": row.delegate_address,
                "authority_address": row.authority_address,
                "bytecode_sha256": bytecode_hash,
                "postcutoff_exact_runtime_family": row.postcutoff_exact_runtime_family,
                "coverage": graph.coverage.value,
                "analysis_error": analysis_error_by_hash[bytecode_hash],
                **graph.features,
            })
            coverage_counts[graph.coverage.value] = coverage_counts.get(graph.coverage.value, 0) + 1
            if position % 50 == 0 or position == len(eligible):
                print(f"[postcutoff_dcrg] {position}/{len(eligible)}", flush=True)

    features = pd.DataFrame(feature_rows)
    os.replace(graph_tmp, GRAPH_PATH)
    features.to_csv(
        feature_tmp,
        index=False,
        compression={"method": "gzip", "mtime": 0},
        lineterminator="\n",
    )
    os.replace(feature_tmp, FEATURE_PATH)
    report = {
        "status": "UNLABELED_AUTHORITY_AWARE_DCRG_EXTRACTION",
        "schema": "dcrg-1.1",
        "snapshot_sha256": snapshot_hash,
        "features_sha256": _sha256_file(FEATURE_PATH),
        "graphs_sha256": _sha256_file(GRAPH_PATH),
        "builder_sha256": _sha256_file(__file__),
        "dcrg_source_sha256": _sha256_file(os.path.join(
            V3, "src", "analysis", "delegation_context.py"
        )),
        "cfg_source_sha256": _sha256_file(os.path.join(
            V3, "experiments", "opus5_labeling", "evm_cfg.py"
        )),
        "n_authority_delegate_pairs": int(len(features)),
        "n_unique_runtimes": int(len(cfg_by_hash)),
        "n_runtime_analysis_errors": int(sum(
            error is not None for error in analysis_error_by_hash.values()
        )),
        "coverage_counts": coverage_counts,
        "n_pairs_with_authority_match": int(
            (features["n_hardcoded_authority_matches"] > 0).sum()
        ),
        "n_pairs_with_authority_mismatch": int(
            (features["n_hardcoded_authority_mismatches"] > 0).sum()
        ),
        "n_pairs_with_entrypoint_guard": int(
            (features["n_erc4337_entrypoint_guards"] > 0).sum()
        ),
        "feature_order": list(DCRG_FEATURE_ORDER),
        "features_artifact": os.path.relpath(FEATURE_PATH, REPO_ROOT),
        "graphs_artifact": os.path.relpath(GRAPH_PATH, REPO_ROOT),
        "claim_boundary": (
            "This extraction establishes that real authority context is represented. It does "
            "not establish that authority features improve correct decisions; independent "
            "labels, project-family holds, retraining, and paired evaluation remain mandatory."
        ),
    }
    report_tmp = REPORT_PATH + ".tmp"
    with open(report_tmp, "w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    os.replace(report_tmp, REPORT_PATH)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
