from __future__ import annotations

import pandas as pd
import pytest

from revision_v3.experiments.temporal_v2.sample_postcutoff_review import select_review_sample


def _row(index: int, **updates):
    row = {
        "delegate_address": "0x" + f"{index:040x}",
        "authority_address": "0x" + f"{index + 100:040x}",
        "historical_runtime_bytecode": "0x6000",
        "historical_bytecode_sha256": f"{index:064x}",
        "postcutoff_exact_runtime_family": f"T{index:04d}",
        "is_candidate_unseen_family": True,
        "is_exact_historical_duplicate": False,
        "fetch_error": None,
        "historical_code_bytes": 2,
        "authorization_count": index,
        "first_block": 1000 + index,
        "first_tx_hash": "0x" + f"{index:064x}",
        "runtime_changed_since_first_authorization": False,
        "best_historical_family_similarity": 0.2,
    }
    row.update(updates)
    return row


def test_postcutoff_sampling_is_score_blind_deterministic_and_family_deduplicated():
    frame = pd.DataFrame([
        _row(1),
        _row(2),
        _row(3),
        _row(4, postcutoff_exact_runtime_family="T0001", authorization_count=999),
        _row(5, is_candidate_unseen_family=False),
        _row(6, fetch_error="rpc failed"),
    ])
    first, report = select_review_sample(frame, sample_size=3, seed=7)
    second, _ = select_review_sample(frame, sample_size=3, seed=7)
    pd.testing.assert_frame_equal(first, second)
    assert len(first) == 3
    assert first["family_id"].nunique() == 3
    assert "ethereum:" in first.iloc[0]["item_id"]
    assert report["n_eligible_exact_runtime_families"] == 3


def test_postcutoff_sampling_rejects_model_or_label_columns():
    frame = pd.DataFrame([_row(1, model_score=0.9)])
    with pytest.raises(ValueError, match="score-blind sampler"):
        select_review_sample(frame, sample_size=1, seed=7)


def test_postcutoff_sampling_excludes_development_families():
    frame = pd.DataFrame([_row(index) for index in range(1, 7)])
    selected, report = select_review_sample(
        frame,
        sample_size=3,
        seed=7,
        excluded_family_ids={"T0001", "T0002"},
        sample_set="confirmatory",
    )
    assert set(selected["family_id"]).isdisjoint({"T0001", "T0002"})
    assert set(selected["sample_set"]) == {"confirmatory"}
    assert report["n_excluded_supplied_families"] == 2
