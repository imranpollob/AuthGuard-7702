"""Tests for Part 7 sampling: Gold-Dev/Gold-Test family isolation and frozen Gold-Test hashes."""
import hashlib
import json
import os

import pandas as pd
import pytest

HUMAN_EVAL_DIR = os.path.join(os.path.dirname(__file__), "..", "human_eval")


def _skip_if_missing(path):
    if not os.path.exists(path):
        pytest.skip(f"{path} not generated in this environment")


def test_gold_dev_gold_test_family_disjoint():
    gd_path = os.path.join(HUMAN_EVAL_DIR, "gold_dev_manifest.csv")
    gt_path = os.path.join(HUMAN_EVAL_DIR, "gold_test_manifest.csv")
    _skip_if_missing(gd_path)
    _skip_if_missing(gt_path)
    gd = pd.read_csv(gd_path)
    gt = pd.read_csv(gt_path)
    assert set(gd["family_id"]).isdisjoint(set(gt["family_id"]))
    assert set(gd["bytecode_sha256"]).isdisjoint(set(gt["bytecode_sha256"]))


def test_gold_test_population_proportional_labels():
    gt_path = os.path.join(HUMAN_EVAL_DIR, "gold_test_manifest.csv")
    _skip_if_missing(gt_path)
    gt = pd.read_csv(gt_path)
    n_pos = int((gt["source_label"] == 1).sum())
    n_neg = int((gt["source_label"] == 0).sum())
    assert n_pos == 50
    assert n_neg == 100


def test_gold_test_frozen_hash_matches_manifest():
    hashes_path = os.path.join(HUMAN_EVAL_DIR, "gold_test_hashes.json")
    manifest_path = os.path.join(HUMAN_EVAL_DIR, "gold_test_manifest.csv")
    _skip_if_missing(hashes_path)
    _skip_if_missing(manifest_path)
    with open(hashes_path) as f:
        recorded = json.load(f)
    manifest = pd.read_csv(manifest_path)

    recomputed_bytecode_list_hash = hashlib.sha256(
        "\n".join(sorted(manifest["bytecode_sha256"])).encode()
    ).hexdigest()
    assert recomputed_bytecode_list_hash == recorded["unique_bytecode_sha256_list_sha256"]

    recomputed_family_list_hash = hashlib.sha256(
        "\n".join(sorted(str(f) for f in manifest["family_id"].unique())).encode()
    ).hexdigest()
    assert recomputed_family_list_hash == recorded["unique_family_id_list_sha256"]


def test_pilot_disjoint_from_gold_sets_by_exact_bytecode():
    p_path = os.path.join(HUMAN_EVAL_DIR, "pilot_manifest.csv")
    gd_path = os.path.join(HUMAN_EVAL_DIR, "gold_dev_manifest.csv")
    gt_path = os.path.join(HUMAN_EVAL_DIR, "gold_test_manifest.csv")
    for p in (p_path, gd_path, gt_path):
        _skip_if_missing(p)
    pilot = pd.read_csv(p_path)
    gd = pd.read_csv(gd_path)
    gt = pd.read_csv(gt_path)
    assert set(pilot["bytecode_sha256"]).isdisjoint(set(gd["bytecode_sha256"]))
    assert set(pilot["bytecode_sha256"]).isdisjoint(set(gt["bytecode_sha256"]))
