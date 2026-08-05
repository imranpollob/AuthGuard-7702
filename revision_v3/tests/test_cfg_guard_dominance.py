from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "revision_v3", "experiments", "opus5_labeling"))

from evm_cfg import analyze_function  # noqa: E402
from opus5_label import decide, summarize_functions  # noqa: E402


def test_storage_condition_status_is_reachable_and_not_called_unguarded():
    # sload(0) -> ISZERO -> guarded branch -> sstore(0, 0)
    code = bytes.fromhex("5f5415600757005b5f5f5500")
    result = analyze_function(code, 0)
    assert result["status"] == "GUARDED_BY_STORAGE_CONDITION"
    assert [hit["op"] for hit in result["unguarded_sensitive"]] == ["SSTORE"]
    assert result["unguarded_even_by_storage"] == []
    assert result["guards"][0]["kind"] == "medium"


def test_path_surviving_every_recognized_guard_is_unguarded():
    code = bytes.fromhex("5f5f5500")  # sstore(0, 0); stop
    result = analyze_function(code, 0)
    assert result["status"] == "UNGUARDED_PATH"
    assert [hit["op"] for hit in result["unguarded_even_by_storage"]] == ["SSTORE"]


def test_label_summary_does_not_promote_storage_gated_path_to_concrete_exploit():
    result = analyze_function(bytes.fromhex("5f5415600757005b5f5f5500"), 0)
    cfg = {
        "n_functions": 1,
        "per_function": [{
            "selector": "0x00000000",
            "resolved_signature": None,
            "guard_status": result["status"],
            "analysis_incomplete": result["analysis_incomplete"],
            "stack_underflows": result["stack_underflows"],
            "n_reachable_sensitive": len(result["reachable_sensitive"]),
            "guards": result["guards"],
            "unguarded_sensitive": result["unguarded_sensitive"],
            "unguarded_even_by_storage": result["unguarded_even_by_storage"],
        }],
    }
    summary = summarize_functions(cfg)
    assert summary["unguarded_authority_write"] == []
    assert summary["unresolved_guard_only"]


def test_opcode_census_without_reachable_path_cannot_create_unsafe_label():
    cfg = {
        "n_functions": 1,
        "per_function": [{
            "selector": "0x00000000", "resolved_signature": None,
            "guard_status": "NO_SENSITIVE_OP", "analysis_incomplete": False,
            "stack_underflows": 0, "n_reachable_sensitive": 0,
            "reaches_ecrecover": False, "guards": [],
            "unguarded_sensitive": [], "unguarded_even_by_storage": [],
        }],
        "static_opcode_census": {
            "CALL": 1, "CALLER": 0, "ORIGIN": 0,
        },
        "sensitive_opcodes_never_reached_by_analysis": {"CALL": [9]},
        "fallback_receive_paths": {},
    }
    result = decide({
        "cfg_guard_analysis_opus5": cfg,
        "identity": {"documented_project": None},
    })
    assert result["label"] == "UNCERTAIN"
    assert result["unsafe_paths"] == []
    assert any("opcode presence alone" in item for item in result["unresolved"])
