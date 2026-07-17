"""Feature and explanation primitives for AuthGuard-Fusion.

Frozen pipeline modules are imported read-only so the new model uses exactly the established
normalization, disassembly, dense features, and hashed n-grams.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
import sys
from typing import Iterable

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
PIPE = os.path.join(ROOT, "pipeline")
if PIPE not in sys.path:
    sys.path.insert(0, PIPE)

from ag_common import OPCODE_VOCAB, disasm, normalize_bytecode  # noqa: E402
from ag_features import GENERIC_SIGS, build_sensitive_selector_set, featurize  # noqa: E402

PAD_ID = 0
UNK_ID = 1
TOKEN_TO_ID = {token: index + 2 for index, token in enumerate(OPCODE_VOCAB)}
VOCAB_SIZE = len(TOKEN_TO_ID) + 2
SENSITIVE_SELECTORS = build_sensitive_selector_set()

AUXILIARY_FACTORS = (
    "external_call_surface",
    "state_write_surface",
    "delegate_proxy_surface",
    "token_movement_selector_surface",
    "approval_selector_surface",
    "code_lifecycle_surface",
)

TOKEN_MOVEMENT_SELECTORS = {
    GENERIC_SIGS["transfer(address,uint256)"],
    GENERIC_SIGS["transferFrom(address,address,uint256)"],
    GENERIC_SIGS["safeTransferFrom(address,address,uint256)"],
}
APPROVAL_SELECTOR = GENERIC_SIGS["approve(address,uint256)"]


@dataclass(frozen=True)
class EncodedBytecode:
    chunks: np.ndarray
    chunk_mask: np.ndarray
    dense: np.ndarray
    ngram: np.ndarray
    auxiliary: np.ndarray
    evidence: dict


def auxiliary_targets(bytecode: str) -> tuple[np.ndarray, dict]:
    """Return reproducible observable factors and their direct bytecode evidence."""
    normalized = normalize_bytecode(bytecode)
    ops, _, selectors = disasm(normalized)
    counts = {name: ops.count(name) for name in (
        "CALL", "CALLCODE", "DELEGATECALL", "STATICCALL", "SSTORE",
        "CREATE", "CREATE2", "SELFDESTRUCT")}
    token_selectors = sorted(selectors & TOKEN_MOVEMENT_SELECTORS)
    approval = APPROVAL_SELECTOR in selectors
    values = np.asarray([
        any(counts[name] for name in ("CALL", "CALLCODE", "DELEGATECALL", "STATICCALL")),
        counts["SSTORE"] > 0,
        counts["DELEGATECALL"] > 0 or counts["CALLCODE"] > 0,
        bool(token_selectors),
        approval,
        any(counts[name] for name in ("CREATE", "CREATE2", "SELFDESTRUCT")),
    ], dtype=np.float32)
    evidence = {
        "code_bytes": len(normalized) // 2,
        "opcode_count": len(ops),
        "opcode_counts": counts,
        "token_movement_selectors": token_selectors,
        "approval_selector": APPROVAL_SELECTOR if approval else None,
        "observed_factors": {
            name: bool(value) for name, value in zip(AUXILIARY_FACTORS, values)
        },
    }
    return values, evidence


def opcode_chunks(bytecode: str, chunk_size: int = 256,
                  max_chunks: int | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Encode the complete linear-sweep opcode stream as padded chunks.

    `max_chunks=None` preserves every opcode. If a training configuration sets a cap, evenly
    spaced chunks are selected across the complete stream instead of taking only a prefix.
    """
    ops, _, _ = disasm(normalize_bytecode(bytecode))
    ids = np.asarray([TOKEN_TO_ID.get(op, UNK_ID) for op in ops], dtype=np.int64)
    if not len(ids):
        ids = np.asarray([UNK_ID], dtype=np.int64)
    count = int(np.ceil(len(ids) / chunk_size))
    chunks = np.full((count, chunk_size), PAD_ID, dtype=np.int64)
    for index in range(count):
        part = ids[index * chunk_size:(index + 1) * chunk_size]
        chunks[index, :len(part)] = part
    if max_chunks is not None and len(chunks) > max_chunks:
        selected = np.linspace(0, len(chunks) - 1, max_chunks).round().astype(int)
        chunks = chunks[selected]
    mask = np.ones(len(chunks), dtype=np.bool_)
    return chunks, mask


def encode_bytecode(bytecode: str, chunk_size: int = 256,
                    max_chunks: int | None = None) -> EncodedBytecode:
    chunks, chunk_mask = opcode_chunks(bytecode, chunk_size, max_chunks)
    dense, ngram, _ = featurize([bytecode], sens=SENSITIVE_SELECTORS)
    auxiliary, evidence = auxiliary_targets(bytecode)
    return EncodedBytecode(chunks=chunks, chunk_mask=chunk_mask,
                           dense=dense[0].astype(np.float32),
                           ngram=ngram[0].astype(np.float32), auxiliary=auxiliary,
                           evidence=evidence)


def encode_sequence_bytecode(bytecode: str, chunk_size: int = 256,
                             max_chunks: int | None = None) -> EncodedBytecode:
    """Fast operational representation for a sequence-only AuthGuard artifact.

    Dense and n-gram placeholders preserve the model interface but their expensive feature
    extraction is skipped. Direct observable evidence remains available for explanations.
    """
    chunks, chunk_mask = opcode_chunks(bytecode, chunk_size, max_chunks)
    auxiliary, evidence = auxiliary_targets(bytecode)
    return EncodedBytecode(chunks=chunks, chunk_mask=chunk_mask,
                           dense=np.zeros(261, dtype=np.float32),
                           ngram=np.zeros(512, dtype=np.float32), auxiliary=auxiliary,
                           evidence=evidence)


def collate_encoded(rows: Iterable[EncodedBytecode]) -> dict[str, np.ndarray]:
    rows = list(rows)
    if not rows:
        raise ValueError("cannot collate an empty batch")
    max_chunks = max(len(row.chunks) for row in rows)
    chunk_size = rows[0].chunks.shape[1]
    chunks = np.full((len(rows), max_chunks, chunk_size), PAD_ID, dtype=np.int64)
    mask = np.zeros((len(rows), max_chunks), dtype=np.bool_)
    for index, row in enumerate(rows):
        chunks[index, :len(row.chunks)] = row.chunks
        mask[index, :len(row.chunks)] = True
    return {
        "chunks": chunks,
        "chunk_mask": mask,
        "dense": np.stack([row.dense for row in rows]),
        "ngram": np.stack([row.ngram for row in rows]),
        "auxiliary": np.stack([row.auxiliary for row in rows]),
    }
