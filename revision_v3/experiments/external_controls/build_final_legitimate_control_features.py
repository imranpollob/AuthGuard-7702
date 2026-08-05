"""Freeze score-blind DCRG features for the final external legitimate controls.

Observed Ethereum controls use the recovered EOA from the first authorization in the frozen
post-cutoff snapshot.  A deployment-only control has no signer context and is marked for an
operational DEFER; the delegate address is never substituted for the missing authority.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
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
from evm_cfg import Analyzer  # noqa: E402

REGISTRY = os.path.join(V3, "external_controls", "final_new_legitimate_projects.csv")
REGISTRY_REPORT = os.path.join(
    V3, "external_controls", "final_new_legitimate_projects_report.json"
)
POSTCUTOFF = os.path.join(V3, "results", "postcutoff_snapshot", "ethereum_candidates.csv.gz")
PROTOCOL = os.path.join(V3, "protocols", "external_legitimate_control_protocol_v1.json")
OUT_DIR = os.path.join(V3, "results", "external_legitimate_controls_features")
FEATURES = os.path.join(OUT_DIR, "external_legitimate_control_dcrg_features.csv.gz")
GRAPHS = os.path.join(OUT_DIR, "external_legitimate_control_dcrg_graphs.jsonl")
REPORT = os.path.join(OUT_DIR, "external_legitimate_control_dcrg_report.json")


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path: str) -> dict:
    with open(path) as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _runtime_from_registry_row(row: dict) -> str:
    path = os.path.join(REPO_ROOT, str(row["frozen_bytecode_path"]))
    if sha256_file(path) != str(row["frozen_bytecode_file_sha256"]):
        raise ValueError(f"frozen bytecode file hash mismatch for {row['control_id']}")
    with open(path) as handle:
        runtime = handle.read().strip().lower()
    normalized = runtime[2:] if runtime.startswith("0x") else runtime
    runtime_hash = hashlib.sha256(bytes.fromhex(normalized)).hexdigest()
    if runtime_hash != str(row["runtime_bytecode_sha256"]):
        raise ValueError(f"runtime hash mismatch for {row['control_id']}")
    return runtime if runtime.startswith("0x") else "0x" + runtime


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if any(os.path.exists(path) for path in [FEATURES, GRAPHS, REPORT]) and not args.overwrite:
        raise FileExistsError("external DCRG features are already frozen")
    protocol = _json(PROTOCOL)
    registry_report = _json(REGISTRY_REPORT)
    if protocol.get("status") != "EXTERNAL_LEGITIMATE_CONTROLS_PREREGISTERED_BEFORE_SCORING":
        raise ValueError("external-control protocol is not frozen")
    if protocol["registry"]["sha256"] != sha256_file(REGISTRY):
        raise ValueError("registry differs from the preregistered artifact")
    if registry_report["input_locks"][os.path.relpath(POSTCUTOFF, REPO_ROOT)] != sha256_file(
        POSTCUTOFF
    ):
        raise ValueError("post-cutoff snapshot differs from the registry audit input")

    registry = pd.read_csv(REGISTRY).sort_values("control_id", kind="mergesort")
    postcutoff = pd.read_csv(POSTCUTOFF)
    postcutoff["delegate_address"] = postcutoff["delegate_address"].astype(str).str.lower()
    feature_rows = []
    coverage_counts: dict[str, int] = {}
    authority_counts: dict[str, int] = {}
    os.makedirs(OUT_DIR, exist_ok=True)
    graph_tmp = GRAPHS + ".tmp"
    with open(graph_tmp, "w") as graph_handle:
        for row in registry.to_dict("records"):
            address = str(row["address"]).lower()
            observed = postcutoff.loc[postcutoff["delegate_address"].eq(address)]
            if len(observed) > 1:
                raise ValueError(f"duplicate post-cutoff rows for {address}")
            if observed.empty:
                authority = None
                authority_status = "UNAVAILABLE_DEPLOYMENT_ONLY"
            else:
                authority = str(observed.iloc[0]["authority_address"]).lower()
                if not authority.startswith("0x") or len(authority) != 42:
                    raise ValueError(f"malformed recovered authority for {address}")
                authority_status = "RECOVERED_FROM_FIRST_OBSERVED_AUTHORIZATION"
            runtime = _runtime_from_registry_row(row)
            try:
                cfg = cfg_analysis(runtime)
                analysis_error = None
            except Exception as error:
                analysis_error = f"{type(error).__name__}: {error}"
                cfg = {"error": analysis_error}
            graph = build_delegation_context_graph(cfg, authority_address=authority)
            payload = graph.to_dict()
            payload.update({
                "control_id": row["control_id"],
                "project": row["project"],
                "chain": row["chain"],
                "delegate_address": address,
                "authority_address": authority,
                "authority_context_status": authority_status,
                "bytecode_sha256": row["runtime_bytecode_sha256"],
            })
            graph_handle.write(json.dumps(payload, sort_keys=True) + "\n")
            feature_rows.append({
                "control_id": row["control_id"],
                "project": row["project"],
                "classification": row["classification"],
                "chain": row["chain"],
                "delegate_address": address,
                "authority_address": authority or "",
                "authority_context_status": authority_status,
                "operational_defer_required": authority is None,
                "bytecode_sha256": row["runtime_bytecode_sha256"],
                "coverage": graph.coverage.value,
                "analysis_error": analysis_error,
                **graph.features,
            })
            coverage_counts[graph.coverage.value] = coverage_counts.get(graph.coverage.value, 0) + 1
            authority_counts[authority_status] = authority_counts.get(authority_status, 0) + 1
    os.replace(graph_tmp, GRAPHS)
    features = pd.DataFrame(feature_rows)
    feature_tmp = FEATURES + ".tmp"
    features.to_csv(
        feature_tmp,
        index=False,
        compression={"method": "gzip", "mtime": 0},
        lineterminator="\n",
    )
    os.replace(feature_tmp, FEATURES)
    report = {
        "status": "FROZEN_SCORE_BLIND_EXTERNAL_CONTROL_DCRG_FEATURES",
        "schema": "dcrg-1.1-external-controls",
        "analysis_version": "bounded-cfg-1.3-jump-fenced-metadata-state-widening",
        "protocol_sha256": sha256_file(PROTOCOL),
        "registry_sha256": sha256_file(REGISTRY),
        "registry_report_sha256": sha256_file(REGISTRY_REPORT),
        "postcutoff_snapshot_sha256": sha256_file(POSTCUTOFF),
        "features_sha256": sha256_file(FEATURES),
        "graphs_sha256": sha256_file(GRAPHS),
        "builder_sha256": sha256_file(__file__),
        "dcrg_source_sha256": sha256_file(
            os.path.join(V3, "src", "analysis", "delegation_context.py")
        ),
        "cfg_source_sha256": sha256_file(
            os.path.join(V3, "experiments", "opus5_labeling", "evm_cfg.py")
        ),
        "cfg_wrapper_source_sha256": sha256_file(
            os.path.join(V3, "experiments", "opus5_labeling", "build_dossiers.py")
        ),
        "feature_order": list(DCRG_FEATURE_ORDER),
        "analysis_parameters": {
            "max_states": Analyzer.MAX_STATES,
            "max_states_per_pc": Analyzer.MAX_PER_PC,
            "state_widen_after_visits": Analyzer.WIDEN_AFTER,
            "max_symbolic_stack_values": Analyzer.MAX_STACK,
        },
        "runtime_versions": {
            "python": platform.python_version(),
            "cbor2": importlib.metadata.version("cbor2"),
            "evmole": importlib.metadata.version("evmole"),
        },
        "n_controls": len(features),
        "n_unique_runtimes": int(features["bytecode_sha256"].nunique()),
        "n_analysis_errors": int(features["analysis_error"].notna().sum()),
        "coverage_counts": coverage_counts,
        "authority_context_counts": authority_counts,
        "n_operational_defer_required": int(features["operational_defer_required"].sum()),
        "n_pairs_with_authority_match": int(
            (features["n_hardcoded_authority_matches"] > 0).sum()
        ),
        "n_pairs_with_authority_mismatch": int(
            (features["n_hardcoded_authority_mismatches"] > 0).sum()
        ),
        "claim_boundary": (
            "Features are score-blind. Recovered authority context comes only from the first "
            "frozen observed authorization. Startale is deployment-only, has no substituted "
            "authority, and requires operational DEFER."
        ),
    }
    with open(REPORT, "w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
