from __future__ import annotations

import os
import sys

import torch


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "revision_v3", "src"))

from models.relational_dcrg import (  # noqa: E402
    NODE_FEATURE_DIM, RelationalDCRG, collate_graphs, encode_graph, parameter_count,
)


def _graph(edge_kind="HAS_GUARD"):
    return {
        "nodes": [
            {"node_id": "contract", "kind": "CONTRACT", "attributes": {}},
            {"node_id": "entry", "kind": "ENTRYPOINT",
             "attributes": {"guard_status": "GUARD_DOMINATED"}},
            {"node_id": "guard", "kind": "GUARD",
             "attributes": {"delegation_guard_class": "SELF_CALL",
                            "condition_provenance": ["caller"]}},
        ],
        "edges": [
            {"source": "contract", "target": "entry", "kind": "CONTAINS"},
            {"source": "entry", "target": "guard", "kind": edge_kind},
        ],
    }


def test_encoding_adds_reverse_relations_and_no_identifiers():
    graph = encode_graph(_graph())
    assert graph.x.shape == (3, NODE_FEATURE_DIM)
    assert graph.edge_index.shape == (2, 4)
    assert graph.edge_type.unique().numel() == 4


def test_untyped_control_collapses_relations_without_changing_parameters():
    typed = encode_graph(_graph(), typed_edges=True)
    untyped = encode_graph(_graph(), typed_edges=False)
    assert set(untyped.edge_type.tolist()) == {0}
    assert typed.x.equal(untyped.x)
    typed_model = RelationalDCRG()
    untyped_model = RelationalDCRG(collapse_relations=True)
    assert parameter_count(typed_model) == parameter_count(untyped_model)
    batch = collate_graphs([untyped])
    untyped_model(batch).sum().backward()
    # Averaging all matrices keeps the full parameter budget active.
    assert all(layer.relation_weight.grad.abs().sum() > 0 for layer in untyped_model.layers)


def test_batched_forward_and_backward():
    batch = collate_graphs([encode_graph(_graph()), encode_graph(_graph())])
    model = RelationalDCRG(hidden_dim=16)
    logits = model(batch)
    assert logits.shape == (2,)
    torch.nn.functional.binary_cross_entropy_with_logits(
        logits, torch.tensor([0.0, 1.0])
    ).backward()
    assert all(parameter.grad is not None for parameter in model.parameters())
