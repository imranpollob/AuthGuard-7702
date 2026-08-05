from __future__ import annotations

import os
import sys


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "revision_v3", "src"))

from analysis.dcrg_motifs import extract_motifs  # noqa: E402


def test_motifs_preserve_entrypoint_local_guard_capability_relation():
    graph = {
        "nodes": [
            {"node_id": "e", "kind": "ENTRYPOINT",
             "attributes": {"guard_status": "UNGUARDED_PATH"}},
            {"node_id": "g", "kind": "GUARD",
             "attributes": {"delegation_guard_class": "SELF_CALL"}},
            {"node_id": "c", "kind": "CAPABILITY", "attributes": {"op": "CALL"}},
            {"node_id": "x", "kind": "COVERAGE_GAP", "attributes": {}},
        ],
        "edges": [
            {"source": "e", "target": "g", "kind": "HAS_GUARD"},
            {"source": "e", "target": "c",
             "kind": "REACHES_WITHOUT_ANY_RECOGNIZED_GUARD"},
            {"source": "e", "target": "x", "kind": "CONTAINS"},
        ],
    }
    features = extract_motifs(graph)
    assert features["motif_status_guard:UNGUARDED_PATH:SELF_CALL"] == 1
    assert features[
        "motif_guard_capability:SELF_CALL:REACHES_WITHOUT_ANY_RECOGNIZED_GUARD:CALL"
    ] == 1
    assert features["untyped_guard_capability_pair"] == 1
    assert features["motif_status_gap:UNGUARDED_PATH"] == 1


def test_motifs_do_not_pair_evidence_across_entrypoints():
    graph = {
        "nodes": [
            {"node_id": "e1", "kind": "ENTRYPOINT",
             "attributes": {"guard_status": "GUARD_DOMINATED"}},
            {"node_id": "e2", "kind": "ENTRYPOINT",
             "attributes": {"guard_status": "UNGUARDED_PATH"}},
            {"node_id": "g", "kind": "GUARD",
             "attributes": {"delegation_guard_class": "STORAGE"}},
            {"node_id": "c", "kind": "CAPABILITY", "attributes": {"op": "DELEGATECALL"}},
        ],
        "edges": [
            {"source": "e1", "target": "g", "kind": "HAS_GUARD"},
            {"source": "e2", "target": "c", "kind": "REACHES_WITHOUT_STRONG_GUARD"},
        ],
    }
    features = extract_motifs(graph)
    assert features[
        "motif_guard_capability:STORAGE:REACHES_WITHOUT_STRONG_GUARD:DELEGATECALL"
    ] == 0
