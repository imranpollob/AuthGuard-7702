"""Deterministic, bytecode-only proxy/delegation heuristics for evidence packets.

Everything here is a structural pattern match over the disassembled opcode stream and raw
bytes -- no network calls, no ML, no source-analyzer label. Used only to populate factual
evidence fields for human reviewers, never to produce a verdict.
"""
from __future__ import annotations

import re

from features.disassembler import is_eip7702_designator, linear_sweep, to_bytes

# EIP-1967 standard storage slots (keccak256("eip1967.proxy.implementation") - 1, etc.) --
# public, standard constants, not project-specific.
EIP1967_IMPLEMENTATION_SLOT = "360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
EIP1967_ADMIN_SLOT = "b53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103"
EIP1967_BEACON_SLOT = "a3f0ad74e5423aebfd80d3ef4346578335a9a72aeaee59ff6cb3582b35133d50"


def detect_eip7702_designator(hex_str: str) -> dict:
    is_designator = is_eip7702_designator(hex_str)
    resolved = None
    if is_designator:
        resolved = "0x" + hex_str[6:46]
    return {"is_eip7702_designator": is_designator, "designator_target_address": resolved}


def detect_eip1967_slots(hex_str: str) -> dict:
    """A crude but deterministic check: does the raw bytecode contain the EIP-1967 slot
    constant as a 32-byte PUSH32 immediate anywhere? (Full 64-hex-char substring match.)"""
    found = {
        "eip1967_implementation_slot_present": EIP1967_IMPLEMENTATION_SLOT in hex_str,
        "eip1967_admin_slot_present": EIP1967_ADMIN_SLOT in hex_str,
        "eip1967_beacon_slot_present": EIP1967_BEACON_SLOT in hex_str,
    }
    return found


def detect_delegatecall_proxy_pattern(tokens: list[str]) -> dict:
    """Heuristic: DELEGATECALL present near the end of the token stream combined with no
    (or very few) other state-changing opcodes, resembling a minimal forwarding proxy."""
    n = len(tokens)
    if n == 0:
        return {"has_delegatecall": False, "delegatecall_count": 0, "delegatecall_position_ratio": None,
                "resembles_minimal_forwarder": False}
    delegatecall_positions = [i for i, t in enumerate(tokens) if t == "DELEGATECALL"]
    has_delegatecall = len(delegatecall_positions) > 0
    ratio = (delegatecall_positions[-1] / n) if has_delegatecall else None
    sstore_count = tokens.count("SSTORE")
    resembles_minimal_forwarder = has_delegatecall and n < 200 and sstore_count == 0
    return {
        "has_delegatecall": has_delegatecall,
        "delegatecall_count": len(delegatecall_positions),
        "delegatecall_last_position_ratio": ratio,
        "resembles_minimal_forwarder": resembles_minimal_forwarder,
    }


def detect_ownership_admin_selectors(selector_set: set[str]) -> dict:
    """Presence of common ownership/admin/initialization selectors -- a public, standard ABI
    convention (first 4 bytes of keccak256(signature)), not project-specific."""
    from .selectors_table import ADMIN_OWNERSHIP_SIGNATURES
    present = {name: sel in selector_set for name, sel in ADMIN_OWNERSHIP_SIGNATURES.items()}
    return {"admin_ownership_selectors_present": {k: v for k, v in present.items() if v},
            "any_admin_ownership_selector_present": any(present.values())}


def compute_proxy_evidence(hex_str: str) -> dict:
    tokens, _push_sizes, selector_set = linear_sweep(hex_str)
    evidence = {}
    evidence.update(detect_eip7702_designator(hex_str))
    evidence.update(detect_eip1967_slots(hex_str))
    evidence.update(detect_delegatecall_proxy_pattern(tokens))
    evidence.update(detect_ownership_admin_selectors(selector_set))
    return evidence
