from __future__ import annotations

import pandas as pd

from revision_v3.experiments.temporal_v2.build_postcutoff_dependence_clusters import (
    build_dependence_clusters,
)


def _worklist() -> pd.DataFrame:
    return pd.DataFrame([
        {"item_id": "i1", "authority_address": "0x" + "11" * 20},
        {"item_id": "i2", "authority_address": "0x" + "11" * 20},
        {"item_id": "i3", "authority_address": "0x" + "33" * 20},
        {"item_id": "i4", "authority_address": "0x" + "44" * 20},
        {"item_id": "i5", "authority_address": "0x" + "55" * 20},
    ])


def test_shared_authority_and_eoa_deployer_form_transitive_cluster():
    creators = {
        "i1": "0x" + "a1" * 20,
        "i2": "0x" + "a2" * 20,
        "i3": "0x" + "a2" * 20,
        "i4": "0x" + "a4" * 20,
        "i5": "0x" + "a5" * 20,
    }
    kinds = {
        value: {"retrieval_status": "COMPLETE", "is_contract": False}
        for value in creators.values()
    }
    output, report = build_dependence_clusters(_worklist(), creators, kinds)
    clusters = output.set_index("item_id")["dependence_cluster_id"]
    assert clusters["i1"] == clusters["i2"] == clusters["i3"]
    assert report["n_dependence_clusters"] == 3
    assert report["max_cluster_size"] == 3


def test_shared_contract_factory_does_not_link_unrelated_items():
    creator = "0x" + "aa" * 20
    creators = {item_id: creator for item_id in _worklist()["item_id"]}
    kinds = {creator: {"retrieval_status": "COMPLETE", "is_contract": True}}
    output, _ = build_dependence_clusters(_worklist(), creators, kinds)
    clusters = output.set_index("item_id")["dependence_cluster_id"]
    assert clusters["i3"] != clusters["i4"]


def test_confirmed_project_family_adds_must_link_without_changing_labels():
    creators = {item_id: "" for item_id in _worklist()["item_id"]}
    audit = pd.DataFrame([
        {"item_id": item_id, "provenance_status": "CONFIRMED",
         "postcutoff_project_family_id": "PF_ONE" if item_id in {"i4", "i5"} else f"PF_{item_id}"}
        for item_id in _worklist()["item_id"]
    ])
    output, _ = build_dependence_clusters(_worklist(), creators, {}, audit)
    clusters = output.set_index("item_id")["dependence_cluster_id"]
    assert clusters["i4"] == clusters["i5"]
    assert "label" not in output.columns
