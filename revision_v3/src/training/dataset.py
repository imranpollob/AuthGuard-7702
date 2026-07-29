"""Feature caching and fixed-size array construction for Revision v3 training.

Tokens/dense/ngram are computed once per contract (cached to a pickle under revision_v3/data/
— a small, regenerable derived-feature cache, not a copy of the canonical dataset) and then
reshaped into fixed-size numpy arrays for whichever model spec (chunk_size/max_chunks or flat
max_len) is being trained. This keeps every model's training loop a simple, uniform
index-based minibatch loop over precomputed arrays.
"""
from __future__ import annotations

import os
import pickle
import sys

import numpy as np
import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "revision_v3", "src"))

from features.encode import (  # noqa: E402
    DENSE_DIM, NGRAM_DIM, chunk_token_ids, encode_bytecode, tokens_to_ids,
)
from models.flat_cnn import downsample_to_budget  # noqa: E402

TOKEN_CACHE_PATH = os.path.join(REPO_ROOT, "revision_v3", "data", "encoded_primary_cache.pkl")


def build_token_cache(df: pd.DataFrame, force: bool = False) -> dict:
    if os.path.exists(TOKEN_CACHE_PATH) and not force:
        with open(TOKEN_CACHE_PATH, "rb") as f:
            return pickle.load(f)

    cache = {}
    for _, row in df.iterrows():
        enc = encode_bytecode(row["runtime_bytecode"], chunk_size=256, max_chunks=None)
        cache[row["sample_id"]] = {
            "tokens": enc.tokens,
            "dense": enc.dense,
            "ngram": enc.ngram,
        }
    os.makedirs(os.path.dirname(TOKEN_CACHE_PATH), exist_ok=True)
    with open(TOKEN_CACHE_PATH, "wb") as f:
        pickle.dump(cache, f)
    return cache


def chunks_array_for_spec(df: pd.DataFrame, token_cache: dict, chunk_size: int, max_chunks: int) -> dict:
    n = len(df)
    ids_array = np.zeros((n, max_chunks, chunk_size), dtype=np.int16)
    mask_array = np.zeros((n, max_chunks), dtype=np.bool_)
    for i, sample_id in enumerate(df["sample_id"]):
        tokens = token_cache[sample_id]["tokens"]
        ids = tokens_to_ids(tokens)
        chunks = chunk_token_ids(ids, chunk_size=chunk_size, max_chunks=max_chunks)
        n_chunks = min(len(chunks), max_chunks)
        ids_array[i, :n_chunks] = chunks[:n_chunks]
        mask_array[i, :n_chunks] = True
    return {
        "chunks": ids_array,
        "chunk_mask": mask_array,
        "dense": np.stack([token_cache[s]["dense"] for s in df["sample_id"]]).astype(np.float32),
        "ngram": np.stack([token_cache[s]["ngram"] for s in df["sample_id"]]).astype(np.float32),
        "labels": df["label"].to_numpy(dtype=np.float32),
        "family_id": df["family_id"].to_numpy(),
        "fold_id": df["fold_id"].to_numpy(),
        "sample_id": df["sample_id"].to_numpy(),
    }


def flat_array_for_spec(df: pd.DataFrame, token_cache: dict, max_len: int) -> dict:
    n = len(df)
    ids_array = np.zeros((n, max_len), dtype=np.int16)
    for i, sample_id in enumerate(df["sample_id"]):
        tokens = token_cache[sample_id]["tokens"]
        ids = tokens_to_ids(tokens)
        ids_array[i] = downsample_to_budget(ids, max_len)
    return {
        "tokens": ids_array,
        "labels": df["label"].to_numpy(dtype=np.float32),
        "family_id": df["family_id"].to_numpy(),
        "fold_id": df["fold_id"].to_numpy(),
        "sample_id": df["sample_id"].to_numpy(),
    }
