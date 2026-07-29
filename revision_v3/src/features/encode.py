"""Top-level Revision v3 feature encoding: chunked opcode tokens, dense (histogram+structural)
vector, and hashed opcode 4-gram vector. Independent implementation; see module docstrings in
opcodes.py / disassembler.py / structural.py for what "independent" means here.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .disassembler import linear_sweep, normalize_hex
from .hashing import NGRAM_HASH_SEED, opcode_kgrams, stable_hash64
from .opcodes import OPCODE_VOCAB
from .selectors import build_sensitive_selector_set
from .structural import STRUCTURAL_FIELD_ORDER, compute_structural_features

PAD_ID = 0
UNK_ID = 1
TOKEN_TO_ID = {token: index + 2 for index, token in enumerate(OPCODE_VOCAB)}
VOCAB_SIZE = len(TOKEN_TO_ID) + 2  # 227
NGRAM_DIM = 512
DENSE_DIM = len(OPCODE_VOCAB) + len(STRUCTURAL_FIELD_ORDER)  # 261

_SENSITIVE_SELECTORS = None


def sensitive_selectors() -> set[str]:
    global _SENSITIVE_SELECTORS
    if _SENSITIVE_SELECTORS is None:
        _SENSITIVE_SELECTORS = build_sensitive_selector_set()
    return _SENSITIVE_SELECTORS


@dataclass(frozen=True)
class EncodedContract:
    chunks: np.ndarray       # (n_chunks, chunk_size) int64 token ids
    chunk_mask: np.ndarray   # (n_chunks,) bool
    dense: np.ndarray        # (261,) float32
    ngram: np.ndarray        # (512,) float32
    token_count: int
    tokens: list[str]


def tokens_to_ids(tokens: list[str]) -> np.ndarray:
    if not tokens:
        return np.asarray([UNK_ID], dtype=np.int64)
    return np.asarray([TOKEN_TO_ID.get(t, UNK_ID) for t in tokens], dtype=np.int64)


def chunk_token_ids(ids: np.ndarray, chunk_size: int, max_chunks: int | None) -> np.ndarray:
    """Pack token ids into fixed-width chunks; if the chunk count exceeds max_chunks, select
    evenly spaced chunks across the whole stream (never a prefix truncation)."""
    n_chunks = int(np.ceil(len(ids) / chunk_size))
    chunks = np.full((n_chunks, chunk_size), PAD_ID, dtype=np.int64)
    for i in range(n_chunks):
        part = ids[i * chunk_size:(i + 1) * chunk_size]
        chunks[i, :len(part)] = part
    if max_chunks is not None and len(chunks) > max_chunks:
        selected = np.linspace(0, len(chunks) - 1, max_chunks).round().astype(int)
        chunks = chunks[selected]
    return chunks


def opcode_histogram(tokens: list[str]) -> np.ndarray:
    vocab_index = {name: i for i, name in enumerate(OPCODE_VOCAB)}
    hist = np.zeros(len(OPCODE_VOCAB), dtype=np.float32)
    if not tokens:
        return hist
    total = len(tokens)
    for t in tokens:
        j = vocab_index.get(t)
        if j is not None:
            hist[j] += 1.0 / total
    return hist


def hashed_opcode_4grams(tokens: list[str]) -> np.ndarray:
    vec = np.zeros(NGRAM_DIM, dtype=np.float32)
    if not tokens:
        return vec
    grams = opcode_kgrams(tokens, k=4)
    for g in grams:
        vec[stable_hash64(g.encode(), NGRAM_HASH_SEED) % NGRAM_DIM] += 1.0
    vec /= max(len(grams), 1)
    return vec


def encode_bytecode(raw_bytecode: str, chunk_size: int = 256,
                     max_chunks: int | None = None) -> EncodedContract:
    hex_str = normalize_hex(raw_bytecode)
    tokens, _push_sizes, _selectors = linear_sweep(hex_str)
    ids = tokens_to_ids(tokens)
    chunks = chunk_token_ids(ids, chunk_size, max_chunks)
    mask = np.ones(len(chunks), dtype=np.bool_)

    struct_fields, _ = compute_structural_features(hex_str, sensitive_selectors())
    struct_vec = np.asarray([struct_fields[c] for c in STRUCTURAL_FIELD_ORDER], dtype=np.float32)
    dense = np.concatenate([opcode_histogram(tokens), struct_vec]).astype(np.float32)
    ngram = hashed_opcode_4grams(tokens)

    return EncodedContract(
        chunks=chunks, chunk_mask=mask, dense=dense, ngram=ngram,
        token_count=len(tokens), tokens=tokens,
    )


def collate(rows: list[EncodedContract]) -> dict[str, np.ndarray]:
    if not rows:
        raise ValueError("cannot collate an empty batch")
    max_chunks = max(len(r.chunks) for r in rows)
    chunk_size = rows[0].chunks.shape[1]
    chunks = np.full((len(rows), max_chunks, chunk_size), PAD_ID, dtype=np.int64)
    mask = np.zeros((len(rows), max_chunks), dtype=np.bool_)
    for i, r in enumerate(rows):
        chunks[i, :len(r.chunks)] = r.chunks
        mask[i, :len(r.chunks)] = True
    return {
        "chunks": chunks,
        "chunk_mask": mask,
        "dense": np.stack([r.dense for r in rows]),
        "ngram": np.stack([r.ngram for r in rows]),
    }
