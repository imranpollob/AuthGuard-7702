from __future__ import annotations

import hashlib
import json

import pandas as pd

from revision_v3.experiments.temporal_v2 import build_postcutoff_dcrg as extractor


def test_postcutoff_dcrg_retains_real_authority_context(tmp_path, monkeypatch):
    runtime = bytes.fromhex("60006000f3")
    snapshot_path = tmp_path / "snapshot.csv.gz"
    feature_path = tmp_path / "features.csv.gz"
    graph_path = tmp_path / "graphs.jsonl"
    report_path = tmp_path / "report.json"
    snapshot_report_path = tmp_path / "snapshot_report.json"
    pd.DataFrame([{
        "delegate_address": "0x" + "11" * 20,
        "authority_address": "0x" + "22" * 20,
        "historical_runtime_bytecode": "0x" + runtime.hex(),
        "historical_bytecode_sha256": hashlib.sha256(runtime).hexdigest(),
        "historical_code_bytes": len(runtime),
        "postcutoff_exact_runtime_family": "T0001",
        "fetch_error": None,
    }]).to_csv(snapshot_path, index=False, compression="gzip")
    snapshot_report_path.write_text(json.dumps({
        "status": "FROZEN_POSTCUTOFF_CANDIDATE_SNAPSHOT_UNLABELED",
        "snapshot_sha256": hashlib.sha256(snapshot_path.read_bytes()).hexdigest(),
    }))

    monkeypatch.setattr(extractor, "SNAPSHOT_PATH", str(snapshot_path))
    monkeypatch.setattr(extractor, "FEATURE_PATH", str(feature_path))
    monkeypatch.setattr(extractor, "GRAPH_PATH", str(graph_path))
    monkeypatch.setattr(extractor, "REPORT_PATH", str(report_path))
    monkeypatch.setattr(extractor, "SNAPSHOT_REPORT_PATH", str(snapshot_report_path))

    assert extractor.main() == 0
    report = json.loads(report_path.read_text())
    graph = json.loads(graph_path.read_text())
    features = pd.read_csv(feature_path)
    assert report["status"] == "UNLABELED_AUTHORITY_AWARE_DCRG_EXTRACTION"
    assert report["n_authority_delegate_pairs"] == 1
    assert report["n_runtime_analysis_errors"] == 0
    assert graph["authority_address"] == "0x" + "22" * 20
    assert features.iloc[0]["authority_address"] == "0x" + "22" * 20

    first_feature_hash = report["features_sha256"]
    assert extractor.main() == 0
    rerun_report = json.loads(report_path.read_text())
    assert rerun_report["features_sha256"] == first_feature_hash
