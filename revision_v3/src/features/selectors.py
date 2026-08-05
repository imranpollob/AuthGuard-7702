"""Function-selector reference sets for Revision v3 structural features.

Selectors are the first 4 bytes of keccak256(signature) — a public, standard Ethereum ABI
convention, not project-specific expression. The "sensitive" signature list and generic
signature list are re-declared independently here (same public convention as used elsewhere
in the project for cross-comparability) plus the same optional USENIX artifact selector-name
dump, read read-only.
"""
from __future__ import annotations

import json
import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

SENSITIVE_SIGNATURES = [
    "sweep(address[])", "sweepToken(address)", "sweepTokens(address,uint256)",
    "sweepETH(uint256)", "drain(address)", "drainToken(address)", "steal(address)",
    "attack()", "hack()", "exploit()", "pwn()",
]

GENERIC_SIGNATURES = {
    "transfer(address,uint256)": "a9059cbb",
    "transferFrom(address,address,uint256)": "23b872dd",
    "approve(address,uint256)": "095ea7b3",
    "safeTransferFrom(address,address,uint256)": "42842e0e",
    "withdraw(uint256)": "2e1a7d4d",
    "owner()": "8da5cb5b",
    "execute(address,uint256,bytes)": "b61d27f6",
}

TOKEN_MOVEMENT_SIGNATURES = (
    "transfer(address,uint256)",
    "transferFrom(address,address,uint256)",
    "safeTransferFrom(address,address,uint256)",
)
APPROVAL_SIGNATURE = "approve(address,uint256)"

_USENIX_SELECTOR_JSONL = os.path.join(
    REPO_ROOT, "USENIX EIP-7702 artifact", "eoa_detect", "decompile",
    "AM_Detect_SensitiveSigName.jsonl",
)


def keccak_selector(signature: str) -> str | None:
    try:
        from Crypto.Hash import keccak
        digest = keccak.new(digest_bits=256)
        digest.update(signature.encode())
        return digest.hexdigest()[:8]
    except Exception:
        return None


def build_sensitive_selector_set() -> set[str]:
    selectors = set()
    for sig in SENSITIVE_SIGNATURES:
        s = keccak_selector(sig)
        if s:
            selectors.add(s)
    if os.path.exists(_USENIX_SELECTOR_JSONL):
        with open(_USENIX_SELECTOR_JSONL) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                for pair in row.get("result", []):
                    sh = pair[0].lower().replace("0x", "")
                    if len(sh) <= 8:
                        selectors.add(sh.zfill(8))
    return selectors
