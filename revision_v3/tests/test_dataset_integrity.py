"""Canonical input hashes, row/label/family/fold counts, and leakage/isolation invariants."""
import os

import numpy as np
import pytest

from data.loader import (
    CanonicalInputChanged, assert_no_conflicting_exact_bytecode_label,
    assert_no_exact_bytecode_cross_fold, assert_no_family_cross_fold, fold_split,
    load_config, load_manifest, load_primary_dataset,
)


def test_manifest_hash_matches_current_file():
    manifest = load_manifest()
    df = load_primary_dataset(verify_hash=True)  # raises if mismatched
    assert len(df) > 0


def test_row_counts():
    df = load_primary_dataset()
    config = load_config()
    exp = config["expected_population"]
    assert len(df) == exp["primary_rows"]


def test_label_counts():
    df = load_primary_dataset()
    config = load_config()
    exp = config["expected_population"]
    assert int((df["label"] == 1).sum()) == exp["primary_positive"]
    assert int((df["label"] == 0).sum()) == exp["primary_negative"]


def test_family_counts():
    df = load_primary_dataset()
    config = load_config()
    assert df["family_id"].nunique() == config["expected_population"]["primary_families"]


def test_fold_counts():
    df = load_primary_dataset()
    config = load_config()
    assert df["fold_id"].nunique() == config["expected_population"]["n_folds"]


def test_no_family_cross_fold():
    df = load_primary_dataset()
    assert_no_family_cross_fold(df)  # raises AssertionError on violation


def test_no_exact_bytecode_cross_fold():
    df = load_primary_dataset()
    assert_no_exact_bytecode_cross_fold(df)


def test_no_conflicting_exact_bytecode_label():
    df = load_primary_dataset()
    assert_no_conflicting_exact_bytecode_label(df)


def test_stored_fold_reproduction_and_no_leakage():
    df = load_primary_dataset()
    for test_fold in range(5):
        train_df, val_df, test_df = fold_split(df, test_fold)
        assert len(train_df) + len(val_df) + len(test_df) == len(df)
        train_ids = set(train_df["sample_id"])
        val_ids = set(val_df["sample_id"])
        test_ids = set(test_df["sample_id"])
        assert train_ids.isdisjoint(val_ids)
        assert train_ids.isdisjoint(test_ids)
        assert val_ids.isdisjoint(test_ids)
        # family isolation across the split (not just the whole-dataset check above)
        assert set(train_df["family_id"]).isdisjoint(set(test_df["family_id"]))
        assert set(val_df["family_id"]).isdisjoint(set(test_df["family_id"]))
        assert set(train_df["family_id"]).isdisjoint(set(val_df["family_id"]))


def test_hash_guard_refuses_on_tamper(tmp_path, monkeypatch):
    """Simulates a changed canonical input by pointing the manifest at a wrong hash."""
    import data.loader as loader_module
    manifest = load_manifest()
    tampered = dict(manifest)
    tampered["sha256"] = {"benchmark_csv_gz": "0" * 64}
    tampered_path = tmp_path / "input_manifest.json"
    import json
    with open(tampered_path, "w") as f:
        json.dump(tampered, f)

    monkeypatch.setattr(loader_module, "MANIFEST_PATH", str(tampered_path))
    with pytest.raises(CanonicalInputChanged):
        loader_module.load_primary_dataset(verify_hash=True)
