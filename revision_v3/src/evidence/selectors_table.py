"""Standard, public ABI signatures for ownership/admin/initialization functions -- widely
used conventions (OpenZeppelin Ownable/AccessControl/Initializable and common proxy admin
patterns), not project-specific or fabricated. Selectors are computed the same
keccak256(signature)[:4] way as revision_v3/src/features/selectors.py.
"""
from __future__ import annotations

from features.selectors import keccak_selector

ADMIN_OWNERSHIP_RAW_SIGNATURES = [
    "owner()",
    "admin()",
    "getOwner()",
    "transferOwnership(address)",
    "renounceOwnership()",
    "initialize(address)",
    "initialize(bytes)",
    "initialize()",
    "upgradeTo(address)",
    "upgradeToAndCall(address,bytes)",
    "changeAdmin(address)",
    "setOwner(address)",
    "hasRole(bytes32,address)",
    "grantRole(bytes32,address)",
    "revokeRole(bytes32,address)",
]

ADMIN_OWNERSHIP_SIGNATURES: dict[str, str] = {
    sig: sel for sig in ADMIN_OWNERSHIP_RAW_SIGNATURES
    if (sel := keccak_selector(sig)) is not None
}
