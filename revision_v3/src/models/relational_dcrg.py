"""Small dependency-free relational GNN for Delegation-Context Risk Graphs.

This module intentionally uses only PyTorch rather than PyG/DGL so the paper artifact has a
compact dependency surface.  Node features are security categories and bounded numeric evidence;
addresses, sample IDs, bytecode hashes, folds, and labels are never encoded.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Mapping, Sequence

import torch
from torch import nn


NODE_KINDS = ("CONTRACT", "ENTRYPOINT", "GUARD", "CAPABILITY", "COVERAGE_GAP")
ENTRY_STATUSES = (
    "NO_SENSITIVE_OP", "GUARD_DOMINATED", "GUARDED_BY_STORAGE_CONDITION", "UNGUARDED_PATH",
)
CAPABILITY_OPS = ("CALL", "CALLCODE", "DELEGATECALL", "CREATE", "CREATE2", "SELFDESTRUCT", "SSTORE")
GUARD_CLASSES = (
    "SELF_CALL", "SIGNATURE", "STORAGE", "HARDCODED", "ERC4337_ENTRYPOINT",
    "CALLDATA_DEPENDENT", "TX_ORIGIN", "OTHER",
)
PROVENANCE = (
    "caller", "origin", "address", "sload", "tload", "ecrecover", "calldata", "memory",
    "returndata", "callvalue",
)
EDGE_KINDS = (
    "CONTAINS", "HAS_GUARD", "REACHES_WITHOUT_STRONG_GUARD",
    "REACHES_WITHOUT_ANY_RECOGNIZED_GUARD", "HAS_UNRESOLVED_CAPABILITY",
)
RELATIONS = EDGE_KINDS + tuple(f"REVERSE_{name}" for name in EDGE_KINDS)


def _one_hot(value: object, choices: Sequence[str]) -> list[float]:
    text = str(value) if value is not None else ""
    return [float(text == choice) for choice in choices]


def _sources(attributes: Mapping[str, object]) -> set[str]:
    out: set[str] = set()
    for field in (
        "condition_provenance", "compared_against_provenance", "target_src", "value_src",
        "data_src",
    ):
        values = attributes.get(field) or []
        if isinstance(values, str):
            values = [values]
        out.update(str(value) for value in values)
    return out


def node_features(node: Mapping[str, object]) -> list[float]:
    attributes = node.get("attributes") or {}
    kind = str(node.get("kind") or "")
    sources = _sources(attributes)
    opcode = attributes.get("op") or attributes.get("opcode")
    numeric = [
        float(bool(attributes.get("analysis_incomplete"))),
        math.log1p(float(attributes.get("n_reachable_sensitive") or 0)),
        float(bool(attributes.get("reachable_without_strong_guard"))),
        float(bool(attributes.get("reachable_without_any_recognized_guard"))),
        float(bool(attributes.get("matches_authorizing_eoa"))),
        float(bool(attributes.get("hit_exploration_cap"))),
        math.log1p(float(attributes.get("unresolved_dynamic_jumps") or 0)),
        math.log1p(float(attributes.get("stack_underflows") or 0)),
    ]
    return [
        *_one_hot(kind, NODE_KINDS),
        *_one_hot(attributes.get("guard_status"), ENTRY_STATUSES),
        *_one_hot(opcode, CAPABILITY_OPS),
        *_one_hot(attributes.get("delegation_guard_class"), GUARD_CLASSES),
        *[float(source in sources) for source in PROVENANCE],
        *numeric,
    ]


NODE_FEATURE_DIM = len(node_features({"kind": "CONTRACT", "attributes": {}}))


@dataclass(frozen=True)
class EncodedGraph:
    x: torch.Tensor
    edge_index: torch.Tensor
    edge_type: torch.Tensor


@dataclass(frozen=True)
class GraphBatch:
    x: torch.Tensor
    edge_index: torch.Tensor
    edge_type: torch.Tensor
    graph_index: torch.Tensor
    n_graphs: int

    def to(self, device: torch.device) -> "GraphBatch":
        return GraphBatch(
            x=self.x.to(device), edge_index=self.edge_index.to(device),
            edge_type=self.edge_type.to(device), graph_index=self.graph_index.to(device),
            n_graphs=self.n_graphs,
        )


def encode_graph(graph: Mapping[str, object], *, typed_edges: bool = True,
                 capability_only: bool = False) -> EncodedGraph:
    nodes = list(graph.get("nodes") or [])
    if capability_only:
        keep = {
            str(node["node_id"]) for node in nodes
            if node.get("kind") in {"CONTRACT", "CAPABILITY", "COVERAGE_GAP"}
        }
        # Retain entry points that directly connect to a retained capability/gap so graph
        # topology is not replaced by a disconnected bag of nodes.
        for edge in graph.get("edges") or []:
            if str(edge.get("target")) in keep:
                keep.add(str(edge.get("source")))
        nodes = [node for node in nodes if str(node["node_id"]) in keep]
    node_ids = {str(node["node_id"]): index for index, node in enumerate(nodes)}
    x = torch.tensor([node_features(node) for node in nodes], dtype=torch.float32)
    sources: list[int] = []
    targets: list[int] = []
    relations: list[int] = []
    relation_index = {name: index for index, name in enumerate(RELATIONS)}
    for edge in graph.get("edges") or []:
        source = str(edge.get("source"))
        target = str(edge.get("target"))
        if source not in node_ids or target not in node_ids:
            continue
        kind = str(edge.get("kind"))
        if kind not in EDGE_KINDS:
            continue
        forward = relation_index[kind] if typed_edges else 0
        reverse = relation_index[f"REVERSE_{kind}"] if typed_edges else 0
        sources.extend((node_ids[source], node_ids[target]))
        targets.extend((node_ids[target], node_ids[source]))
        relations.extend((forward, reverse))
    edge_index = torch.tensor([sources, targets], dtype=torch.long)
    edge_type = torch.tensor(relations, dtype=torch.long)
    return EncodedGraph(x=x, edge_index=edge_index, edge_type=edge_type)


def collate_graphs(graphs: Iterable[EncodedGraph]) -> GraphBatch:
    graphs = list(graphs)
    if not graphs:
        raise ValueError("cannot collate an empty graph batch")
    xs: list[torch.Tensor] = []
    edges: list[torch.Tensor] = []
    types: list[torch.Tensor] = []
    graph_ids: list[torch.Tensor] = []
    offset = 0
    for graph_id, graph in enumerate(graphs):
        xs.append(graph.x)
        edges.append(graph.edge_index + offset)
        types.append(graph.edge_type)
        graph_ids.append(torch.full((len(graph.x),), graph_id, dtype=torch.long))
        offset += len(graph.x)
    return GraphBatch(
        x=torch.cat(xs), edge_index=torch.cat(edges, dim=1), edge_type=torch.cat(types),
        graph_index=torch.cat(graph_ids), n_graphs=len(graphs),
    )


class RelationalLayer(nn.Module):
    def __init__(self, hidden_dim: int, n_relations: int, collapse_relations: bool = False):
        super().__init__()
        self.collapse_relations = collapse_relations
        self.self_linear = nn.Linear(hidden_dim, hidden_dim)
        self.relation_weight = nn.Parameter(
            torch.empty(n_relations, hidden_dim, hidden_dim)
        )
        nn.init.xavier_uniform_(self.relation_weight)
        self.norm = nn.LayerNorm(hidden_dim)

    def forward(self, h: torch.Tensor, edge_index: torch.Tensor,
                edge_type: torch.Tensor) -> torch.Tensor:
        aggregate = torch.zeros_like(h)
        degree = torch.zeros((len(h), 1), dtype=h.dtype, device=h.device)
        if edge_type.numel():
            source, target = edge_index
            if self.collapse_relations:
                # All relation matrices remain active (through their mean), but edge labels
                # carry no information.  This gives the untyped control the same trainable
                # parameter count and capacity budget as the typed model.
                weight = self.relation_weight.mean(dim=0).expand(len(source), -1, -1)
            else:
                weight = self.relation_weight[edge_type]
            messages = torch.bmm(h[source].unsqueeze(1), weight).squeeze(1)
            aggregate.index_add_(0, target, messages)
            degree.index_add_(0, target, torch.ones((len(target), 1), device=h.device))
        updated = self.self_linear(h) + aggregate / degree.clamp_min(1.0)
        return torch.relu(self.norm(updated))


class RelationalDCRG(nn.Module):
    def __init__(self, hidden_dim: int = 48, n_layers: int = 2, dropout: float = 0.2,
                 collapse_relations: bool = False):
        super().__init__()
        self.input = nn.Linear(NODE_FEATURE_DIM, hidden_dim)
        self.layers = nn.ModuleList(
            RelationalLayer(hidden_dim, len(RELATIONS), collapse_relations)
            for _ in range(n_layers)
        )
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Sequential(
            nn.Linear(2 * hidden_dim, hidden_dim), nn.ReLU(), nn.Dropout(dropout),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, batch: GraphBatch) -> torch.Tensor:
        h = torch.relu(self.input(batch.x))
        for layer in self.layers:
            h = self.dropout(layer(h, batch.edge_index, batch.edge_type))
        pooled = []
        for graph_id in range(batch.n_graphs):
            current = h[batch.graph_index == graph_id]
            pooled.append(torch.cat((current.mean(dim=0), current.max(dim=0).values)))
        return self.classifier(torch.stack(pooled)).squeeze(-1)


def parameter_count(model: nn.Module) -> int:
    return sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
