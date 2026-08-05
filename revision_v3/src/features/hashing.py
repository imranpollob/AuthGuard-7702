"""Deterministic, PYTHONHASHSEED-independent hashing for Revision v3.

Uses blake2b with an explicit 8-byte salt so results are stable across processes/machines —
Python's built-in hash() is never used for anything that affects a feature value.
"""
from __future__ import annotations

import hashlib


def stable_hash64(data: bytes, seed: int) -> int:
    salt = seed.to_bytes(8, "little")
    digest = hashlib.blake2b(data, digest_size=8, salt=salt).digest()
    return int.from_bytes(digest, "little")


NGRAM_HASH_SEED = 2
MINHASH_GRAM_SEED = 0
MINHASH_PERM_SEED = 1


def opcode_kgrams(tokens: list[str], k: int = 4) -> set[str]:
    if len(tokens) < k:
        return {" ".join(tokens)} if tokens else {"<EMPTY>"}
    return {" ".join(tokens[i:i + k]) for i in range(len(tokens) - k + 1)}
