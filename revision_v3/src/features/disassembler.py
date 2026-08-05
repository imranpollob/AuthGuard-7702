"""Deterministic linear-sweep EVM disassembler — independent Revision v3 implementation.

No control-flow recovery, no jump-target resolution: a pure linear sweep that walks the byte
stream once, emitting one token per instruction and skipping PUSH immediates as data. This is
the same class of disassembler used throughout the project (necessary for opcode-token
features and any subsequent MinHash-style similarity), rewritten independently for Revision v3.
"""
from __future__ import annotations

from .opcodes import PUSH1, PUSH32, mnemonic


def normalize_hex(raw: str) -> str:
    """Lower-case, strip an optional 0x prefix, drop a dangling odd nibble."""
    text = str(raw).strip().lower()
    if text.startswith("0x"):
        text = text[2:]
    if len(text) % 2:
        text = text[:-1]
    return text


def to_bytes(hex_str: str) -> bytes:
    try:
        return bytes.fromhex(hex_str)
    except ValueError:
        cleaned = "".join(c for c in hex_str if c in "0123456789abcdef")
        if len(cleaned) % 2:
            cleaned = cleaned[:-1]
        try:
            return bytes.fromhex(cleaned)
        except ValueError:
            return b""


def is_eip7702_designator(hex_str: str) -> bool:
    """ef0100 || 20-byte address: an authorization designator, not deployed runtime code."""
    return hex_str.startswith("ef0100") and len(hex_str) == 46


def linear_sweep(hex_str: str) -> tuple[list[str], list[int], set[str]]:
    """Returns (tokens, push_immediate_sizes, four_byte_push_immediates_as_hex).

    tokens: one mnemonic per instruction, PUSH1..PUSH32 collapsed to "PUSH".
    push_immediate_sizes: the byte-width of every PUSH instruction encountered, in order.
    four_byte_push_immediates: the set of 4-byte PUSH immediates (candidate function
    selectors), used by the structural/selector feature layer.
    """
    code = to_bytes(hex_str)
    tokens: list[str] = []
    push_sizes: list[int] = []
    selectors: set[str] = set()
    i, n = 0, len(code)
    while i < n:
        op = code[i]
        if PUSH1 <= op <= PUSH32:
            size = op - PUSH1 + 1
            immediate = code[i + 1: i + 1 + size]
            tokens.append("PUSH")
            push_sizes.append(size)
            if size == 4 and len(immediate) == 4:
                selectors.add(immediate.hex())
            i += 1 + size
        else:
            tokens.append(mnemonic(op))
            i += 1
    return tokens, push_sizes, selectors
