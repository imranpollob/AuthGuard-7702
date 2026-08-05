from __future__ import annotations

import importlib.util

import pandas as pd
import pytest


def _load_module():
    path = __file__.replace(
        "tests/test_postcutoff_provenance_worklist.py",
        "experiments/temporal_v2/build_postcutoff_provenance_worklist.py",
    )
    spec = importlib.util.spec_from_file_location("postcutoff_provenance_worklist", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


worklist = _load_module()


def _inputs():
    snapshot = pd.DataFrame([
        {
            "delegate_address": "0xabc", "authority_address": "0x111",
            "first_tx_hash": "0xaaa", "first_block": 10, "first_timestamp_unix": 100,
            "last_block": 20, "last_timestamp_unix": 200, "authorization_count": 3,
            "historical_code_bytes": 100, "historical_bytecode_sha256": "hash-a",
            "postcutoff_exact_runtime_family": "T1", "matched_historical_family": "F1",
            "best_historical_family_similarity": 0.8,
            "runtime_changed_since_first_authorization": False,
        },
        {
            "delegate_address": "0xdef", "authority_address": "0x222",
            "first_tx_hash": "0xbbb", "first_block": 11, "first_timestamp_unix": 110,
            "last_block": 21, "last_timestamp_unix": 210, "authorization_count": 1,
            "historical_code_bytes": 100, "historical_bytecode_sha256": "hash-a",
            "postcutoff_exact_runtime_family": "T1", "matched_historical_family": "F1",
            "best_historical_family_similarity": 0.8,
            "runtime_changed_since_first_authorization": False,
        },
    ])
    manifest = pd.DataFrame([{
        "item_id": "ethereum:0xabc", "address": "0xabc",
        "bytecode_sha256": "hash-a", "family_id": "T1",
    }])
    return snapshot, manifest


def test_worklist_adds_reproducible_links_and_exact_runtime_peers():
    snapshot, manifest = _inputs()
    result = worklist.build_worklist(snapshot, manifest)
    assert len(result) == 1
    assert result.iloc[0]["delegate_explorer_url"] == "https://etherscan.io/address/0xabc"
    assert result.iloc[0]["exact_runtime_peer_count"] == 2
    assert result.iloc[0]["exact_runtime_peer_addresses"] == "0xabc;0xdef"
    assert not any("bytecode" in column and column == "runtime_bytecode" for column in result)


def test_worklist_refuses_label_or_model_output_columns():
    snapshot, manifest = _inputs()
    snapshot["model_score"] = 0.5
    with pytest.raises(ValueError, match="refuses label/model/review columns"):
        worklist.build_worklist(snapshot, manifest)


def test_worklist_rejects_manifest_snapshot_hash_disagreement():
    snapshot, manifest = _inputs()
    manifest.loc[0, "bytecode_sha256"] = "different"
    with pytest.raises(ValueError, match="bytecode hash differs"):
        worklist.build_worklist(snapshot, manifest)
