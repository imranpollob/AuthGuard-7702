"""EVM opcode table for Revision v3 — an independent implementation.

Written from the public EVM instruction-set specification (opcode -> mnemonic mapping is a
standard fact, not implementation-specific expression). Any single-byte value with no assigned
mnemonic below is rendered as ``UNK_xx`` (hex, lower-case) so that the vocabulary construction
below is well-defined for every one of the 256 possible opcode bytes.

Vocabulary rule (must match the property under test in the parity suite, not any specific
prior source file): PUSH1..PUSH32 (0x60..0x7f) collapse to a single "PUSH" token because their
immediate bytes are consumed as data, not instructions. PUSH0 (0x5f) takes no immediate and
therefore keeps its own token. This yields 256 - 32 + 1 = 225 distinct mnemonics.
"""
from __future__ import annotations

PUSH1, PUSH32 = 0x60, 0x7F

_BASE_NAMES: dict[int, str] = {
    0x00: "STOP", 0x01: "ADD", 0x02: "MUL", 0x03: "SUB", 0x04: "DIV", 0x05: "SDIV",
    0x06: "MOD", 0x07: "SMOD", 0x08: "ADDMOD", 0x09: "MULMOD", 0x0A: "EXP",
    0x0B: "SIGNEXTEND",
    0x10: "LT", 0x11: "GT", 0x12: "SLT", 0x13: "SGT", 0x14: "EQ", 0x15: "ISZERO",
    0x16: "AND", 0x17: "OR", 0x18: "XOR", 0x19: "NOT", 0x1A: "BYTE", 0x1B: "SHL",
    0x1C: "SHR", 0x1D: "SAR",
    0x20: "KECCAK256",
    0x30: "ADDRESS", 0x31: "BALANCE", 0x32: "ORIGIN", 0x33: "CALLER", 0x34: "CALLVALUE",
    0x35: "CALLDATALOAD", 0x36: "CALLDATASIZE", 0x37: "CALLDATACOPY", 0x38: "CODESIZE",
    0x39: "CODECOPY", 0x3A: "GASPRICE", 0x3B: "EXTCODESIZE", 0x3C: "EXTCODECOPY",
    0x3D: "RETURNDATASIZE", 0x3E: "RETURNDATACOPY", 0x3F: "EXTCODEHASH",
    0x40: "BLOCKHASH", 0x41: "COINBASE", 0x42: "TIMESTAMP", 0x43: "NUMBER",
    0x44: "PREVRANDAO", 0x45: "GASLIMIT", 0x46: "CHAINID", 0x47: "SELFBALANCE",
    0x48: "BASEFEE",
    0x50: "POP", 0x51: "MLOAD", 0x52: "MSTORE", 0x53: "MSTORE8", 0x54: "SLOAD",
    0x55: "SSTORE", 0x56: "JUMP", 0x57: "JUMPI", 0x58: "PC", 0x59: "MSIZE",
    0x5A: "GAS", 0x5B: "JUMPDEST", 0x5F: "PUSH0",
    0xF0: "CREATE", 0xF1: "CALL", 0xF2: "CALLCODE", 0xF3: "RETURN",
    0xF4: "DELEGATECALL", 0xF5: "CREATE2", 0xFA: "STATICCALL", 0xFD: "REVERT",
    0xFE: "INVALID", 0xFF: "SELFDESTRUCT",
}
for _i in range(16):
    _BASE_NAMES[0x80 + _i] = f"DUP{_i + 1}"
    _BASE_NAMES[0x90 + _i] = f"SWAP{_i + 1}"
for _i in range(5):
    _BASE_NAMES[0xA0 + _i] = f"LOG{_i}"


def mnemonic(opcode_byte: int) -> str:
    if PUSH1 <= opcode_byte <= PUSH32:
        return "PUSH"
    return _BASE_NAMES.get(opcode_byte, f"UNK_{opcode_byte:02x}")


def build_vocab() -> list[str]:
    """Every distinct mnemonic across all 256 byte values, first-seen order, 225 entries."""
    seen: set[str] = set()
    vocab: list[str] = []
    for code in range(256):
        name = mnemonic(code)
        if name not in seen:
            seen.add(name)
            vocab.append(name)
    return vocab


OPCODE_VOCAB: list[str] = build_vocab()
assert len(OPCODE_VOCAB) == 225, f"expected 225-entry opcode vocabulary, got {len(OPCODE_VOCAB)}"
