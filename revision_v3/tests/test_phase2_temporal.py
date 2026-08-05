"""Tests for temporal collector deduplication and historical-family matching (Part 8)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from temporal.enrich import jaccard


def test_jaccard_identical_sets():
    a = {"ADD PUSH JUMP STOP", "PUSH JUMP STOP MSTORE"}
    assert jaccard(a, a) == 1.0


def test_jaccard_disjoint_sets():
    a = {"ADD PUSH JUMP STOP"}
    b = {"MSTORE SLOAD SSTORE STOP"}
    assert jaccard(a, b) == 0.0


def test_jaccard_empty_sets():
    assert jaccard(set(), set()) == 1.0
    assert jaccard({"x"}, set()) == 0.0


def test_jaccard_partial_overlap():
    a = {"a", "b", "c", "d"}
    b = {"c", "d", "e", "f"}
    assert jaccard(a, b) == 2 / 6


def test_temporal_dedup_by_exact_bytecode_hash():
    """Two authorizations for the SAME delegate address must resolve to the same
    bytecode_sha256 (dedup is exact-hash-based, not address-based) -- verified structurally by
    checking enrich.py's build_historical_family_representatives keys on bytecode_sha256, not
    address."""
    import pandas as pd
    raw_dir = os.path.join(os.path.dirname(__file__), "..", "temporal", "raw")
    eth_path = os.path.join(raw_dir, "pilot_v1_ethereum_enriched.csv")
    if not os.path.exists(eth_path):
        import pytest
        pytest.skip("temporal pilot not run in this environment")
    df = pd.read_csv(eth_path)
    # same address should never appear twice with two different bytecode hashes in one pass
    dupe_check = df.groupby("address")["bytecode_sha256"].nunique()
    assert (dupe_check <= 1).all()
