"""Structural/selector scalar features — independent Revision v3 implementation.

36 scalar fields covering code size, control-flow/opcode-family counts and densities,
PUSH-immediate statistics, the EIP-7702 designator flag, and selector-presence indicators.
This is the same *category* of structural feature the rest of the project's dense
representation uses (a documented requirement of the audit brief, not incidental overlap);
field names and computation are written independently here.
"""
from __future__ import annotations

import numpy as np

from .disassembler import is_eip7702_designator, linear_sweep
from .selectors import GENERIC_SIGNATURES

STRUCTURAL_FIELD_ORDER = [
    "code_bytes", "n_ops", "n_selectors", "is_delegation_ptr",
    "n_jumpdest", "n_jump", "n_jumpi",
    "n_call", "n_staticcall", "n_delegatecall", "n_callcode", "n_call_family",
    "n_create", "n_selfdestruct", "n_sstore", "n_sload", "n_log", "n_revert", "n_invalid",
    "n_push", "mean_push_size", "n_push4", "n_push20", "n_push32",
    "jumpdest_density", "call_density", "push_density",
    "has_sensitive_selector", "n_sensitive_selectors",
] + [f"has_{name.split('(')[0]}" for name in GENERIC_SIGNATURES]

assert len(STRUCTURAL_FIELD_ORDER) == 36, len(STRUCTURAL_FIELD_ORDER)


def compute_structural_features(hex_str: str, sensitive_selectors: set[str]) -> tuple[dict, list[str]]:
    tokens, push_sizes, selector_set = linear_sweep(hex_str)
    n = len(tokens)

    def count(name: str) -> int:
        return tokens.count(name)

    n_call = count("CALL")
    n_static = count("STATICCALL")
    n_delegate = count("DELEGATECALL")
    n_callcode = count("CALLCODE")
    n_jumpdest = count("JUMPDEST")
    n_push = count("PUSH")

    fields = {
        "code_bytes": len(hex_str) // 2,
        "n_ops": n,
        "n_selectors": len(selector_set),
        "is_delegation_ptr": 1.0 if is_eip7702_designator(hex_str) else 0.0,
        "n_jumpdest": n_jumpdest,
        "n_jump": count("JUMP"),
        "n_jumpi": count("JUMPI"),
        "n_call": n_call,
        "n_staticcall": n_static,
        "n_delegatecall": n_delegate,
        "n_callcode": n_callcode,
        "n_call_family": n_call + n_static + n_delegate + n_callcode,
        "n_create": count("CREATE") + count("CREATE2"),
        "n_selfdestruct": count("SELFDESTRUCT"),
        "n_sstore": count("SSTORE"),
        "n_sload": count("SLOAD"),
        "n_log": sum(count(f"LOG{i}") for i in range(5)),
        "n_revert": count("REVERT"),
        "n_invalid": sum(1 for t in tokens if t.startswith("UNK_") or t == "INVALID"),
        "n_push": n_push,
        "mean_push_size": float(np.mean(push_sizes)) if push_sizes else 0.0,
        "n_push4": sum(1 for s in push_sizes if s == 4),
        "n_push20": sum(1 for s in push_sizes if s == 20),
        "n_push32": sum(1 for s in push_sizes if s == 32),
        "jumpdest_density": n_jumpdest / max(n, 1),
        "call_density": (n_call + n_static + n_delegate + n_callcode) / max(n, 1),
        "push_density": n_push / max(n, 1),
        "has_sensitive_selector": 1.0 if (selector_set & sensitive_selectors) else 0.0,
        "n_sensitive_selectors": len(selector_set & sensitive_selectors),
    }
    for name, selector_hex in GENERIC_SIGNATURES.items():
        fields[f"has_{name.split('(')[0]}"] = 1.0 if selector_hex in selector_set else 0.0

    return fields, tokens
