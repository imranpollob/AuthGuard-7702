"""Typed Delegation-Context Risk Graph (DCRG) for EIP-7702 screening.

This module deliberately does not claim to prove safety.  It converts the bounded CFG and
symbolic-stack evidence produced by ``experiments/opus5_labeling/evm_cfg.py`` into a stable,
machine-readable representation whose coverage gaps are first-class.  The graph is designed
for three consumers:

* an interpretable pre-authorization report,
* fixed-order scalar features for learned models, and
* a selective policy that defers when semantic evidence is incomplete.

The representation is EIP-7702-specific because caller checks are interpreted relative to an
optional *authorizing EOA*, while storage-derived authority, self-call checks, signature checks,
and fixed third-party checks remain distinct.  Generic opcode/CFG fusion collapses these cases.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence

from analysis.protocol_actors import ERC4337_ENTRYPOINT_ADDRESSES


class CoverageStatus(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"


class NodeKind(str, Enum):
    CONTRACT = "CONTRACT"
    ENTRYPOINT = "ENTRYPOINT"
    GUARD = "GUARD"
    CAPABILITY = "CAPABILITY"
    COVERAGE_GAP = "COVERAGE_GAP"


class EdgeKind(str, Enum):
    CONTAINS = "CONTAINS"
    HAS_GUARD = "HAS_GUARD"
    REACHES_WITHOUT_STRONG_GUARD = "REACHES_WITHOUT_STRONG_GUARD"
    REACHES_WITHOUT_ANY_RECOGNIZED_GUARD = "REACHES_WITHOUT_ANY_RECOGNIZED_GUARD"
    HAS_UNRESOLVED_CAPABILITY = "HAS_UNRESOLVED_CAPABILITY"


DCRG_FEATURE_ORDER = (
    "n_functions",
    "n_complete_functions",
    "n_incomplete_functions",
    "n_unguarded_sensitive",
    "n_unguarded_call",
    "n_unguarded_delegatecall",
    "n_unguarded_create",
    "n_unguarded_selfdestruct",
    "n_unguarded_sstore",
    "n_sensitive_without_any_recognized_guard",
    "n_storage_condition_guarded_sensitive",
    "n_guards",
    "n_self_call_guards",
    "n_signature_guards",
    "n_storage_guards",
    "n_hardcoded_guards",
    "n_erc4337_entrypoint_guards",
    "n_hardcoded_authority_matches",
    "n_hardcoded_authority_mismatches",
    "n_calldata_dependent_guards",
    "n_tx_origin_guards",
    "fallback_external_call_reachable",
    "fallback_open_external_call",
    "n_unreached_sensitive_sites",
    "coverage_complete",
    "coverage_partial",
    "coverage_unknown",
)


@dataclass(frozen=True)
class RiskNode:
    node_id: str
    kind: str
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RiskEdge:
    source: str
    target: str
    kind: str


@dataclass
class DelegationContextRiskGraph:
    schema_version: str
    authority_address: str | None
    coverage: CoverageStatus
    nodes: list[RiskNode]
    edges: list[RiskEdge]
    findings: list[str]
    features: dict[str, float]

    def feature_vector(self) -> list[float]:
        return [float(self.features[name]) for name in DCRG_FEATURE_ORDER]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "authority_address": self.authority_address,
            "coverage": self.coverage.value,
            "nodes": [asdict(node) for node in self.nodes],
            "edges": [asdict(edge) for edge in self.edges],
            "findings": list(self.findings),
            "feature_order": list(DCRG_FEATURE_ORDER),
            "features": dict(self.features),
            "feature_vector": self.feature_vector(),
        }


def _normalize_address(value: str | None) -> str | None:
    if not value:
        return None
    text = str(value).lower().strip()
    if text.startswith("0x"):
        text = text[2:]
    if not text or any(char not in "0123456789abcdef" for char in text):
        raise ValueError(f"invalid authority address {value!r}")
    if len(text) > 40:
        raise ValueError(f"authority address exceeds 20 bytes: {value!r}")
    return "0x" + text.rjust(40, "0")


def _empty_features() -> dict[str, float]:
    return {name: 0.0 for name in DCRG_FEATURE_ORDER}


def _as_list(value: Any) -> list:
    return list(value) if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) else []


def _guard_class(guard: Mapping[str, Any], authority: str | None) -> tuple[str, bool | None]:
    semantics = str(guard.get("semantics") or "")
    compared = guard.get("compared_address_constant")
    compared_norm = _normalize_address(compared) if compared else None
    authority_match = None if authority is None or compared_norm is None else compared_norm == authority
    if semantics.startswith("self_call_check"):
        return "SELF_CALL", authority_match
    if semantics.startswith("signature_authorization"):
        return "SIGNATURE", authority_match
    if semantics.startswith("storage_based_caller_check") or semantics.startswith("storage_condition"):
        return "STORAGE", authority_match
    if semantics.startswith("hardcoded_address_check"):
        if compared_norm in ERC4337_ENTRYPOINT_ADDRESSES:
            return "ERC4337_ENTRYPOINT", authority_match
        return "HARDCODED", authority_match
    if semantics.startswith("calldata_comparison"):
        return "CALLDATA_DEPENDENT", authority_match
    if semantics.startswith("tx.origin") or semantics.startswith("tx_origin"):
        return "TX_ORIGIN", authority_match
    return "OTHER", authority_match


def _capability_bucket(op: str) -> str:
    if op in {"CALL", "CALLCODE"}:
        return "n_unguarded_call"
    if op == "DELEGATECALL":
        return "n_unguarded_delegatecall"
    if op in {"CREATE", "CREATE2"}:
        return "n_unguarded_create"
    if op == "SELFDESTRUCT":
        return "n_unguarded_selfdestruct"
    if op == "SSTORE":
        return "n_unguarded_sstore"
    return "n_unguarded_sensitive"


def build_delegation_context_graph(
    cfg_report: Mapping[str, Any] | None,
    *,
    authority_address: str | None = None,
) -> DelegationContextRiskGraph:
    """Build a deterministic DCRG from one bounded CFG-analysis report.

    ``authority_address`` is optional because the historical benchmark records delegate
    addresses but not always the EOA that would authorize them.  In live pre-authorization
    use the authorizer is known and fixed-address guards can be classified as matching or not
    matching that authority.  Missing authority context remains explicit rather than guessed.
    """
    authority = _normalize_address(authority_address)
    features = _empty_features()
    nodes = [RiskNode("contract", NodeKind.CONTRACT.value,
                      {"authority_context_available": authority is not None})]
    edges: list[RiskEdge] = []
    findings: set[str] = set()

    if not cfg_report or cfg_report.get("error"):
        features["coverage_unknown"] = 1.0
        nodes.append(RiskNode("coverage:unknown", NodeKind.COVERAGE_GAP.value,
                              {"reason": (cfg_report or {}).get("error", "missing CFG report")}))
        edges.append(RiskEdge("contract", "coverage:unknown", EdgeKind.CONTAINS.value))
        return DelegationContextRiskGraph(
            "dcrg-1.1", authority, CoverageStatus.UNKNOWN, nodes, edges,
            ["ANALYSIS_UNKNOWN"], features,
        )

    functions = _as_list(cfg_report.get("per_function"))
    features["n_functions"] = float(len(functions))
    any_incomplete = False
    for fn_index, fn in enumerate(functions):
        fn_id = f"entry:{fn_index}"
        incomplete = bool(fn.get("analysis_incomplete"))
        any_incomplete |= incomplete
        features["n_incomplete_functions" if incomplete else "n_complete_functions"] += 1.0
        nodes.append(RiskNode(fn_id, NodeKind.ENTRYPOINT.value, {
            "selector": fn.get("selector"),
            "resolved_signature": fn.get("resolved_signature"),
            "entry_pc": fn.get("entry_pc"),
            "guard_status": fn.get("guard_status"),
            "analysis_incomplete": incomplete,
            "n_reachable_sensitive": int(fn.get("n_reachable_sensitive") or 0),
        }))
        edges.append(RiskEdge("contract", fn_id, EdgeKind.CONTAINS.value))

        for guard_index, guard in enumerate(_as_list(fn.get("guards"))):
            guard_id = f"{fn_id}:guard:{guard_index}"
            guard_class, authority_match = _guard_class(guard, authority)
            features["n_guards"] += 1.0
            feature_name = {
                "SELF_CALL": "n_self_call_guards",
                "SIGNATURE": "n_signature_guards",
                "STORAGE": "n_storage_guards",
                "HARDCODED": "n_hardcoded_guards",
                "ERC4337_ENTRYPOINT": "n_erc4337_entrypoint_guards",
                "CALLDATA_DEPENDENT": "n_calldata_dependent_guards",
                "TX_ORIGIN": "n_tx_origin_guards",
            }.get(guard_class)
            if feature_name:
                features[feature_name] += 1.0
            if guard_class == "HARDCODED" and authority_match is True:
                features["n_hardcoded_authority_matches"] += 1.0
                findings.add("FIXED_CALLER_MATCHES_AUTHORITY")
            elif guard_class == "HARDCODED" and authority_match is False:
                features["n_hardcoded_authority_mismatches"] += 1.0
                findings.add("FIXED_CALLER_DIFFERS_FROM_AUTHORITY")
            nodes.append(RiskNode(guard_id, NodeKind.GUARD.value, {
                **dict(guard),
                "delegation_guard_class": guard_class,
                "matches_authorizing_eoa": authority_match,
            }))
            edges.append(RiskEdge(fn_id, guard_id, EdgeKind.HAS_GUARD.value))

        without_strong = _as_list(fn.get("unguarded_sensitive"))
        if "unguarded_even_by_storage" in fn:
            without_any_keys = {
                (str(capability.get("op") or "UNKNOWN"), capability.get("pc"))
                for capability in _as_list(fn.get("unguarded_even_by_storage"))
            }
        else:
            # Backward-compatible conservative interpretation for pre-dcrg-1.1 reports.
            without_any_keys = {
                (str(capability.get("op") or "UNKNOWN"), capability.get("pc"))
                for capability in without_strong
            }
        for cap_index, capability in enumerate(without_strong):
            cap_id = f"{fn_id}:capability:{cap_index}"
            op = str(capability.get("op") or "UNKNOWN")
            lacks_any_guard = (op, capability.get("pc")) in without_any_keys
            features["n_unguarded_sensitive"] += 1.0
            bucket = _capability_bucket(op)
            if bucket != "n_unguarded_sensitive":
                features[bucket] += 1.0
            if lacks_any_guard:
                features["n_sensitive_without_any_recognized_guard"] += 1.0
                findings.add(f"UNGUARDED_{op}")
                edge_kind = EdgeKind.REACHES_WITHOUT_ANY_RECOGNIZED_GUARD.value
            else:
                features["n_storage_condition_guarded_sensitive"] += 1.0
                findings.add(f"STORAGE_CONDITION_GUARDED_{op}")
                edge_kind = EdgeKind.REACHES_WITHOUT_STRONG_GUARD.value
            nodes.append(RiskNode(cap_id, NodeKind.CAPABILITY.value, {
                **dict(capability),
                "reachable_without_strong_guard": True,
                "reachable_without_any_recognized_guard": lacks_any_guard,
            }))
            edges.append(RiskEdge(fn_id, cap_id, edge_kind))

        if incomplete:
            gap_id = f"{fn_id}:coverage-gap"
            nodes.append(RiskNode(gap_id, NodeKind.COVERAGE_GAP.value, {
                "unresolved_dynamic_jumps": int(fn.get("unresolved_dynamic_jumps") or 0),
                "stack_underflows": int(fn.get("stack_underflows") or 0),
                "hit_exploration_cap": bool(fn.get("hit_exploration_cap")),
                "used_state_widening": bool(fn.get("used_state_widening")),
            }))
            edges.append(RiskEdge(fn_id, gap_id, EdgeKind.CONTAINS.value))
            findings.add("INCOMPLETE_FUNCTION_ANALYSIS")

    fallback = cfg_report.get("fallback_receive_paths") or {}
    features["fallback_external_call_reachable"] = float(bool(
        fallback.get("source_rule_locally_reproduced")
    ))
    features["fallback_open_external_call"] = float(bool(
        fallback.get("unauthenticated_external_call_from_fallback_or_receive")
    ))
    if features["fallback_open_external_call"]:
        findings.add("OPEN_FALLBACK_OR_RECEIVE_EXTERNAL_CALL")
    for path_name in ("receive_path", "fallback_path"):
        path = fallback.get(path_name) or {}
        if path.get("analysis_incomplete"):
            any_incomplete = True
            findings.add("INCOMPLETE_FALLBACK_ANALYSIS")

    unreached = cfg_report.get("sensitive_opcodes_never_reached_by_analysis") or {}
    unreached_count = sum(len(_as_list(sites)) for sites in unreached.values())
    features["n_unreached_sensitive_sites"] = float(unreached_count)
    if unreached_count:
        any_incomplete = True
        findings.add("SENSITIVE_OPCODE_OUTSIDE_ANALYZED_PATHS")
        for op, sites in sorted(unreached.items()):
            gap_id = f"coverage:unreached:{op}"
            nodes.append(RiskNode(gap_id, NodeKind.COVERAGE_GAP.value,
                                  {"opcode": op, "pcs": _as_list(sites)}))
            edges.append(RiskEdge("contract", gap_id,
                                  EdgeKind.HAS_UNRESOLVED_CAPABILITY.value))

    if not functions:
        coverage = CoverageStatus.UNKNOWN
        features["coverage_unknown"] = 1.0
        findings.add("NO_ENTRYPOINT_ANALYSIS")
    elif any_incomplete:
        coverage = CoverageStatus.PARTIAL
        features["coverage_partial"] = 1.0
    else:
        coverage = CoverageStatus.COMPLETE
        features["coverage_complete"] = 1.0

    return DelegationContextRiskGraph(
        schema_version="dcrg-1.1",
        authority_address=authority,
        coverage=coverage,
        nodes=nodes,
        edges=edges,
        findings=sorted(findings),
        features=features,
    )
