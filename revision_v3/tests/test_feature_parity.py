"""Feature parity: Revision v3's independent feature pipeline vs. the frozen Revision v2
pipeline, on 200 sampled canonical contracts. This test IMPORTS revision_v2 code as a
read-only oracle for comparison purposes only — v3's own pipeline (revision_v3/src/features/)
never imports from revision_v2 or pipeline/.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "revision_v3", "src"))
sys.path.insert(0, os.path.join(REPO_ROOT, "revision_v2"))

from features.encode import encode_bytecode as v3_encode  # noqa: E402
from data.loader import load_primary_dataset  # noqa: E402

N_SAMPLE = 200
SEED = 7702

TOKEN_EQUALITY_MIN = 1.0
OPCODE_COUNT_EQUALITY_MIN = 1.0
DENSE_MAX_ABS_DIFF_MAX = 1e-4
NGRAM_MAX_ABS_DIFF_MAX = 1e-4


def _v2_encode():
    from authguard7702 import features as v2_features  # noqa
    return v2_features


def _sample_rows():
    df = load_primary_dataset()
    sample = df.sample(n=N_SAMPLE, random_state=SEED).reset_index(drop=True)
    return sample


@pytest.fixture(scope="module")
def parity_results():
    v2_features = _v2_encode()
    sample = _sample_rows()

    token_matches = 0
    opcode_count_matches = 0
    dense_max_abs = 0.0
    ngram_max_abs = 0.0
    rows = []

    for _, row in sample.iterrows():
        bc = row["runtime_bytecode"]
        v3_enc = v3_encode(bc, chunk_size=256, max_chunks=None)
        v2_enc = v2_features.encode_bytecode(bc, chunk_size=256, max_chunks=None)

        v2_ops, _, _ = v2_features.disasm(v2_features.normalize_bytecode(bc))
        v3_ops = v3_enc.tokens

        tok_match = (v2_ops == v3_ops)
        token_matches += int(tok_match)
        opcode_count_matches += int(len(v2_ops) == len(v3_ops))

        d_diff = float(np.max(np.abs(v3_enc.dense - v2_enc.dense))) if len(v2_enc.dense) == len(v3_enc.dense) else float("inf")
        n_diff = float(np.max(np.abs(v3_enc.ngram - v2_enc.ngram))) if len(v2_enc.ngram) == len(v3_enc.ngram) else float("inf")
        dense_max_abs = max(dense_max_abs, d_diff)
        ngram_max_abs = max(ngram_max_abs, n_diff)

        rows.append({
            "sample_id": row["sample_id"],
            "token_match": tok_match,
            "v2_n_ops": len(v2_ops),
            "v3_n_ops": len(v3_ops),
            "dense_max_abs_diff": d_diff,
            "ngram_max_abs_diff": n_diff,
        })

    n = len(sample)
    results = {
        "n_sample": n,
        "token_sequence_equality_rate": token_matches / n,
        "opcode_count_equality_rate": opcode_count_matches / n,
        "dense_feature_max_abs_diff": dense_max_abs,
        "ngram_feature_max_abs_diff": ngram_max_abs,
        "rows": rows,
    }
    return results


def test_token_sequence_equality(parity_results):
    assert parity_results["token_sequence_equality_rate"] >= TOKEN_EQUALITY_MIN, parity_results["token_sequence_equality_rate"]


def test_opcode_count_equality(parity_results):
    assert parity_results["opcode_count_equality_rate"] >= OPCODE_COUNT_EQUALITY_MIN, parity_results["opcode_count_equality_rate"]


def test_dense_feature_parity(parity_results):
    assert parity_results["dense_feature_max_abs_diff"] <= DENSE_MAX_ABS_DIFF_MAX, parity_results["dense_feature_max_abs_diff"]


def test_ngram_feature_parity(parity_results):
    assert parity_results["ngram_feature_max_abs_diff"] <= NGRAM_MAX_ABS_DIFF_MAX, parity_results["ngram_feature_max_abs_diff"]
