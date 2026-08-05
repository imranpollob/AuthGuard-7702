from __future__ import annotations

import json

from revision_v3.experiments.human_label_evaluation import (
    run_current_label_oracle_what_if as what_if,
)


def test_current_label_oracle_mapping_is_explicit_and_isolated():
    proxy = what_if.load_proxy_labels()
    assert proxy["llm_provisional_label"].value_counts().to_dict() == {
        "UNSAFE": 88,
        "UNCERTAIN": 42,
        "SAFE": 20,
    }
    human = what_if.human_view(proxy, uncertain_assignment=None)
    assert int((~human["excluded_from_binary"]).sum()) == 108
    assert int(human["excluded_from_binary"].sum()) == 42
    assert "what_if_current_labels_as_human" in what_if.OUTPUT
    assert "human_final" not in what_if.OUTPUT


def test_current_label_oracle_output_remains_marked_nonhuman():
    with open(what_if.OUTPUT) as handle:
        report = json.load(handle)
    assert report["status"] == "WHAT_IF_ONLY_NOT_HUMAN_EVIDENCE"
    assert "cannot support submission claims" in report["fatal_validity_warning"]
    assert report["n_binary"] == 108
    assert report["n_excluded_uncertain"] == 42
