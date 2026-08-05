"""Deterministic block-explorer URL construction for the 7 historical benchmark chains.
Standard, public, canonical explorer domains for these exact chains -- not fabricated, not
project-specific, directly relevant to a bytecode security-evidence packet."""
from __future__ import annotations

EXPLORER_BASE = {
    "ethereum": "https://etherscan.io/address/",
    "bnb": "https://bscscan.com/address/",
    "base": "https://basescan.org/address/",
    "optimism": "https://optimistic.etherscan.io/address/",
    "arbitrum": "https://arbiscan.io/address/",
    "polygon": "https://polygonscan.com/address/",
    "gnosis": "https://gnosisscan.io/address/",
}


def explorer_link(chain: str, address: str) -> str | None:
    base = EXPLORER_BASE.get(str(chain).lower())
    if base is None or not address:
        return None
    return base + address
