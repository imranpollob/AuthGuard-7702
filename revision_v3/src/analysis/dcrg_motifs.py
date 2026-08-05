"""Explicit entrypoint-local relational motifs for DCRG graphs.

The aggregate DCRG counts node categories globally.  These motifs retain which guard and
capability evidence co-occur under the same public entry point, a shallow structure that is more
data-efficient to learn than a generic GNN on the current benchmark size.
"""
from __future__ import annotations

from itertools import product
from typing import Mapping


STATUSES = (
    "NO_SENSITIVE_OP", "GUARD_DOMINATED", "GUARDED_BY_STORAGE_CONDITION", "UNGUARDED_PATH",
)
GUARDS = (
    "SELF_CALL", "SIGNATURE", "STORAGE", "HARDCODED", "ERC4337_ENTRYPOINT",
    "CALLDATA_DEPENDENT", "TX_ORIGIN", "OTHER",
)
CAPABILITIES = ("CALL", "CALLCODE", "DELEGATECALL", "CREATE", "CREATE2", "SELFDESTRUCT", "SSTORE")
CAPABILITY_EDGES = (
    "REACHES_WITHOUT_STRONG_GUARD", "REACHES_WITHOUT_ANY_RECOGNIZED_GUARD",
)

TYPED_MOTIF_FEATURES = (
    *(f"motif_entry_status:{status}" for status in STATUSES),
    *(f"motif_status_guard:{status}:{guard}" for status, guard in product(STATUSES, GUARDS)),
    *(f"motif_status_capability:{status}:{edge}:{op}"
      for status, edge, op in product(STATUSES, CAPABILITY_EDGES, CAPABILITIES)),
    *(f"motif_guard_capability:{guard}:{edge}:{op}"
      for guard, edge, op in product(GUARDS, CAPABILITY_EDGES, CAPABILITIES)),
    *(f"motif_status_gap:{status}" for status in STATUSES),
)
UNTYPED_MOTIF_FEATURES = (
    *(f"untyped_entry_status:{status}" for status in STATUSES),
    *(f"untyped_status_guard:{status}" for status in STATUSES),
    *(f"untyped_status_capability:{status}" for status in STATUSES),
    "untyped_guard_capability_pair",
    *(f"untyped_status_gap:{status}" for status in STATUSES),
)


def extract_motifs(graph: Mapping[str, object]) -> dict[str, float]:
    typed = {name: 0.0 for name in TYPED_MOTIF_FEATURES}
    untyped = {name: 0.0 for name in UNTYPED_MOTIF_FEATURES}
    nodes = {str(node["node_id"]): node for node in graph.get("nodes") or []}
    outgoing: dict[str, list[Mapping[str, object]]] = {}
    for edge in graph.get("edges") or []:
        outgoing.setdefault(str(edge.get("source")), []).append(edge)

    for entry_id, entry in nodes.items():
        if entry.get("kind") != "ENTRYPOINT":
            continue
        status = str((entry.get("attributes") or {}).get("guard_status") or "")
        if status not in STATUSES:
            continue
        typed[f"motif_entry_status:{status}"] += 1.0
        untyped[f"untyped_entry_status:{status}"] += 1.0
        guards: list[str] = []
        capabilities: list[tuple[str, str]] = []
        has_gap = False
        for edge in outgoing.get(entry_id, []):
            target = nodes.get(str(edge.get("target")))
            if target is None:
                continue
            attributes = target.get("attributes") or {}
            edge_kind = str(edge.get("kind") or "")
            if target.get("kind") == "GUARD":
                guard = str(attributes.get("delegation_guard_class") or "OTHER")
                guards.append(guard if guard in GUARDS else "OTHER")
            elif target.get("kind") == "CAPABILITY" and edge_kind in CAPABILITY_EDGES:
                op = str(attributes.get("op") or "")
                if op in CAPABILITIES:
                    capabilities.append((edge_kind, op))
            elif target.get("kind") == "COVERAGE_GAP":
                has_gap = True
        for guard in guards:
            typed[f"motif_status_guard:{status}:{guard}"] += 1.0
            untyped[f"untyped_status_guard:{status}"] += 1.0
        for edge_kind, op in capabilities:
            typed[f"motif_status_capability:{status}:{edge_kind}:{op}"] += 1.0
            untyped[f"untyped_status_capability:{status}"] += 1.0
        for guard, (edge_kind, op) in product(guards, capabilities):
            typed[f"motif_guard_capability:{guard}:{edge_kind}:{op}"] += 1.0
            untyped["untyped_guard_capability_pair"] += 1.0
        if has_gap:
            typed[f"motif_status_gap:{status}"] += 1.0
            untyped[f"untyped_status_gap:{status}"] += 1.0
    return {**typed, **untyped}
