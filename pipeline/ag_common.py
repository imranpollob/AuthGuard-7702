#!/usr/bin/env python3
"""
ag_common.py -- shared, DETERMINISTIC primitives for the AuthGuard-7702 pipeline.

Everything downstream imports from here so that bytecode normalization, disassembly,
feature extraction, and MinHash are identical and reproducible across scripts.

No Python built-in hash() is used anywhere that affects results (PYTHONHASHSEED-safe).
All hashing goes through blake2b with explicit seeds.
"""
import hashlib
import numpy as np

SEED = 7702  # global project seed

# ----------------------------------------------------------------------------
# EVM opcode table (0x00..0xff). Names for the ones we care about; others get hex.
# ----------------------------------------------------------------------------
# Minimal canonical opcode names (Shanghai-era). Unknown/invalid -> "INVALID_xx".
_OPCODES = {
    0x00: "STOP", 0x01: "ADD", 0x02: "MUL", 0x03: "SUB", 0x04: "DIV", 0x05: "SDIV",
    0x06: "MOD", 0x07: "SMOD", 0x08: "ADDMOD", 0x09: "MULMOD", 0x0a: "EXP",
    0x0b: "SIGNEXTEND", 0x10: "LT", 0x11: "GT", 0x12: "SLT", 0x13: "SGT", 0x14: "EQ",
    0x15: "ISZERO", 0x16: "AND", 0x17: "OR", 0x18: "XOR", 0x19: "NOT", 0x1a: "BYTE",
    0x1b: "SHL", 0x1c: "SHR", 0x1d: "SAR", 0x20: "KECCAK256", 0x30: "ADDRESS",
    0x31: "BALANCE", 0x32: "ORIGIN", 0x33: "CALLER", 0x34: "CALLVALUE",
    0x35: "CALLDATALOAD", 0x36: "CALLDATASIZE", 0x37: "CALLDATACOPY",
    0x38: "CODESIZE", 0x39: "CODECOPY", 0x3a: "GASPRICE", 0x3b: "EXTCODESIZE",
    0x3c: "EXTCODECOPY", 0x3d: "RETURNDATASIZE", 0x3e: "RETURNDATACOPY",
    0x3f: "EXTCODEHASH", 0x40: "BLOCKHASH", 0x41: "COINBASE", 0x42: "TIMESTAMP",
    0x43: "NUMBER", 0x44: "PREVRANDAO", 0x45: "GASLIMIT", 0x46: "CHAINID",
    0x47: "SELFBALANCE", 0x48: "BASEFEE", 0x50: "POP", 0x51: "MLOAD", 0x52: "MSTORE",
    0x53: "MSTORE8", 0x54: "SLOAD", 0x55: "SSTORE", 0x56: "JUMP", 0x57: "JUMPI",
    0x58: "PC", 0x59: "MSIZE", 0x5a: "GAS", 0x5b: "JUMPDEST", 0x5f: "PUSH0",
    0x80: "DUP1", 0x90: "SWAP1", 0xa0: "LOG0", 0xa1: "LOG1", 0xa2: "LOG2",
    0xa3: "LOG3", 0xa4: "LOG4", 0xf0: "CREATE", 0xf1: "CALL", 0xf2: "CALLCODE",
    0xf3: "RETURN", 0xf4: "DELEGATECALL", 0xf5: "CREATE2", 0xfa: "STATICCALL",
    0xfd: "REVERT", 0xfe: "INVALID", 0xff: "SELFDESTRUCT",
}
# fill DUP1..DUP16, SWAP1..SWAP16, PUSH1..PUSH32 handled specially in disasm
for i in range(16):
    _OPCODES[0x80 + i] = f"DUP{i+1}"
    _OPCODES[0x90 + i] = f"SWAP{i+1}"

_PUSH1, _PUSH32 = 0x60, 0x7f
# Canonical vocabulary of opcode names used for histogram features (fixed order).
# Built once so the feature vector column order is stable across runs/machines.
def build_opcode_vocab():
    names = []
    seen = set()
    for code in range(256):
        if _PUSH1 <= code <= _PUSH32:
            nm = "PUSH"          # collapse all PUSHn into one token for histogram
        else:
            nm = _OPCODES.get(code, f"UNK_{code:02x}")
        if nm not in seen:
            seen.add(nm); names.append(nm)
    return names

OPCODE_VOCAB = build_opcode_vocab()


def normalize_bytecode(raw):
    """Lowercase, strip 0x, drop a trailing odd nibble. Returns hex string (no 0x)."""
    h = str(raw).lower().strip()
    if h.startswith("0x"):
        h = h[2:]
    if len(h) % 2:
        h = h[:-1]
    return h


def is_delegation_pointer(hexstr):
    """EIP-7702 designator ef0100 + 20-byte address stored in the EOA (not real code)."""
    return hexstr.startswith("ef0100") and len(hexstr) == 46


def disasm(hexstr):
    """
    Deterministic linear-sweep disassembly.
    Returns (ops, push_ops, selectors):
      ops       : list of opcode name tokens (PUSHn collapsed to "PUSH")
      push_imm  : list of ("PUSH", size, imm_bytes) for structural stats
      selectors : set of 4-byte PUSH4 immediates (candidate function selectors), hex
    Invalid/odd input is handled gracefully (best-effort skeleton).
    """
    try:
        b = bytes.fromhex(hexstr)
    except ValueError:
        # skip non-hex chars defensively
        clean = "".join(c for c in hexstr if c in "0123456789abcdef")
        if len(clean) % 2:
            clean = clean[:-1]
        try:
            b = bytes.fromhex(clean)
        except ValueError:
            return [], [], set()
    ops, pushes, selectors = [], [], set()
    i, n = 0, len(b)
    while i < n:
        op = b[i]
        if _PUSH1 <= op <= _PUSH32:
            size = op - _PUSH1 + 1
            imm = b[i + 1:i + 1 + size]
            ops.append("PUSH")
            pushes.append(size)
            if size == 4 and len(imm) == 4:
                selectors.add(imm.hex())
            i += 1 + size
        else:
            ops.append(_OPCODES.get(op, f"UNK_{op:02x}"))
            i += 1
    return ops, pushes, selectors


# ----------------------------------------------------------------------------
# Deterministic MinHash over opcode k-grams (PYTHONHASHSEED-independent).
# ----------------------------------------------------------------------------
def _bl(data: bytes, seed: int) -> int:
    """64-bit deterministic hash via blake2b with an 8-byte salt seed."""
    salt = seed.to_bytes(8, "little")
    return int.from_bytes(hashlib.blake2b(data, digest_size=8, salt=salt).digest(), "little")


def opcode_kgrams(ops, k=4):
    if len(ops) < k:
        return {" ".join(ops)} if ops else {"<EMPTY>"}
    return {" ".join(ops[i:i + k]) for i in range(len(ops) - k + 1)}


def minhash_signature(ops, num_perm=128, k=4):
    """Deterministic MinHash signature (num_perm int64s) of opcode k-gram set."""
    grams = opcode_kgrams(ops, k)
    gram_hashes = np.array([_bl(g.encode(), 0) for g in grams], dtype=np.uint64)
    sig = np.empty(num_perm, dtype=np.uint64)
    # xor-permutation trick: h_p(x) = h(x) xor seed_p  -> cheap independent-ish perms
    seeds = np.array([_bl(p.to_bytes(4, "little"), 1) for p in range(num_perm)],
                     dtype=np.uint64)
    for p in range(num_perm):
        sig[p] = np.min(gram_hashes ^ seeds[p])
    return sig
