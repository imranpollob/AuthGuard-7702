from __future__ import annotations

import pytest

from analysis.delegation_context import (
    DCRG_FEATURE_ORDER,
    CoverageStatus,
    build_delegation_context_graph,
)
from analysis.protocol_actors import ERC4337_ENTRYPOINTS


AUTHORITY = "0x1111111111111111111111111111111111111111"
OTHER = "0x2222222222222222222222222222222222222222"


def complete_report():
    return {
        "per_function": [{
            "selector": "0x12345678",
            "entry_pc": 12,
            "guard_status": "UNGUARDED_PATH",
            "analysis_incomplete": False,
            "unresolved_dynamic_jumps": 0,
            "stack_underflows": 0,
            "hit_exploration_cap": False,
            "n_reachable_sensitive": 2,
            "guards": [{
                "pc": 20,
                "kind": "strong",
                "condition_provenance": ["caller"],
                "compared_against_provenance": [],
                "compared_address_constant": OTHER,
                "semantics": "hardcoded_address_check (msg.sender compared against a fixed address literal)",
            }],
            "unguarded_sensitive": [
                {"pc": 40, "op": "CALL", "impact": "external_call_or_value_transfer",
                 "target_src": ["calldata"], "value_src": ["calldata"]},
                {"pc": 55, "op": "SSTORE", "impact": "storage_write",
                 "storage_slot": "0x0"},
            ],
        }],
        "fallback_receive_paths": {
            "source_rule_locally_reproduced": True,
            "unauthenticated_external_call_from_fallback_or_receive": True,
            "receive_path": {"analysis_incomplete": False},
            "fallback_path": {"analysis_incomplete": False},
        },
        "sensitive_opcodes_never_reached_by_analysis": {},
    }


def test_dcrg_distinguishes_fixed_third_party_from_authorizer():
    graph = build_delegation_context_graph(complete_report(), authority_address=AUTHORITY)
    assert graph.coverage is CoverageStatus.COMPLETE
    assert "FIXED_CALLER_DIFFERS_FROM_AUTHORITY" in graph.findings
    assert graph.features["n_hardcoded_authority_mismatches"] == 1
    assert graph.features["n_unguarded_call"] == 1
    assert graph.features["n_unguarded_sstore"] == 1
    assert graph.features["fallback_open_external_call"] == 1

    guard = next(node for node in graph.nodes if node.kind == "GUARD")
    assert guard.attributes["matches_authorizing_eoa"] is False


def test_dcrg_recognizes_authority_match_without_calling_it_proof_of_safety():
    report = complete_report()
    report["per_function"][0]["guards"][0]["compared_address_constant"] = AUTHORITY
    graph = build_delegation_context_graph(report, authority_address=AUTHORITY)
    assert "FIXED_CALLER_MATCHES_AUTHORITY" in graph.findings
    assert graph.features["n_hardcoded_authority_matches"] == 1
    assert "UNGUARDED_CALL" in graph.findings  # matching one guard does not erase open paths


def test_incomplete_analysis_is_partial_and_unreached_capability_is_preserved():
    report = complete_report()
    report["per_function"][0]["analysis_incomplete"] = True
    report["per_function"][0]["unresolved_dynamic_jumps"] = 2
    report["sensitive_opcodes_never_reached_by_analysis"] = {
        "DELEGATECALL": [90, 101]
    }
    graph = build_delegation_context_graph(report)
    assert graph.coverage is CoverageStatus.PARTIAL
    assert graph.features["coverage_partial"] == 1
    assert graph.features["n_unreached_sensitive_sites"] == 2
    assert "SENSITIVE_OPCODE_OUTSIDE_ANALYZED_PATHS" in graph.findings


def test_missing_analysis_is_unknown_not_safe():
    graph = build_delegation_context_graph(None)
    assert graph.coverage is CoverageStatus.UNKNOWN
    assert graph.features["coverage_unknown"] == 1
    assert graph.findings == ["ANALYSIS_UNKNOWN"]


def test_storage_guarded_capability_is_not_labeled_fully_unguarded():
    report = complete_report()
    report["per_function"][0]["unguarded_even_by_storage"] = []
    graph = build_delegation_context_graph(report)
    assert graph.features["n_unguarded_sensitive"] == 2
    assert graph.features["n_sensitive_without_any_recognized_guard"] == 0
    assert graph.features["n_storage_condition_guarded_sensitive"] == 2
    assert "UNGUARDED_CALL" not in graph.findings
    assert "STORAGE_CONDITION_GUARDED_CALL" in graph.findings


def test_canonical_entrypoint_guard_is_typed_separately_from_unknown_fixed_actor():
    report = complete_report()
    report["per_function"][0]["guards"][0]["compared_address_constant"] = (
        "0x0000000071727de22e5e9d8baf0edac6f37da032"
    )
    graph = build_delegation_context_graph(report)
    assert graph.features["n_erc4337_entrypoint_guards"] == 1
    assert graph.features["n_hardcoded_guards"] == 0
    guard = next(node for node in graph.nodes if node.kind == "GUARD")
    assert guard.attributes["delegation_guard_class"] == "ERC4337_ENTRYPOINT"


def test_protocol_actor_registry_is_versioned_and_source_attributed():
    assert {entry["version"] for entry in ERC4337_ENTRYPOINTS.values()} >= {
        "0.6", "0.7", "0.8", "0.9"
    }
    for address, entry in ERC4337_ENTRYPOINTS.items():
        assert address == address.lower() and address.startswith("0x") and len(address) == 42
        assert entry["source"].startswith(
            "https://github.com/eth-infinitism/account-abstraction/releases/"
        )


def test_feature_vector_has_stable_declared_order_and_serializes():
    graph = build_delegation_context_graph(complete_report())
    assert len(graph.feature_vector()) == len(DCRG_FEATURE_ORDER)
    payload = graph.to_dict()
    assert payload["feature_order"] == list(DCRG_FEATURE_ORDER)
    assert payload["feature_vector"] == graph.feature_vector()
    assert payload["coverage"] == "COMPLETE"


@pytest.mark.parametrize("bad", ["0xzz", "0x" + "11" * 21])
def test_invalid_authority_address_is_rejected(bad):
    with pytest.raises(ValueError):
        build_delegation_context_graph(complete_report(), authority_address=bad)
