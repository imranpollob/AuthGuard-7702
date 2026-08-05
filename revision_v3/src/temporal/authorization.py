"""EIP-7702 authorization-tuple hashing and authority recovery."""
from __future__ import annotations

from collections.abc import Mapping

import rlp
from eth_keys.datatypes import Signature
from eth_utils import keccak

MAGIC = b"\x05"
SECP256K1_N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141


def _integer(value) -> int:
    if isinstance(value, str):
        return int(value, 16) if value.lower().startswith("0x") else int(value)
    return int(value)


def _address_bytes(value: str) -> bytes:
    text = str(value).lower().removeprefix("0x")
    if len(text) != 40 or any(character not in "0123456789abcdef" for character in text):
        raise ValueError(f"authorization delegate must be a 20-byte address: {value!r}")
    return bytes.fromhex(text)


def authorization_message_hash(chain_id, delegate_address: str, nonce) -> bytes:
    """Return keccak(0x05 || rlp([chain_id, address, nonce])) from EIP-7702."""
    chain = _integer(chain_id)
    authorization_nonce = _integer(nonce)
    if not 0 <= chain < 2**256:
        raise ValueError("authorization chain_id exceeds uint256")
    if not 0 <= authorization_nonce < 2**64:
        raise ValueError("authorization nonce exceeds uint64")
    return keccak(MAGIC + rlp.encode([chain, _address_bytes(delegate_address), authorization_nonce]))


def recover_authority(authorization: Mapping) -> tuple[str, str]:
    """Recover the authorizing EOA and return ``(lowercase_address, message_hash_hex)``."""
    chain_id = authorization.get("chainId", authorization.get("chain_id"))
    delegate = authorization.get("address", authorization.get("delegate_address"))
    nonce = authorization.get("nonce", authorization.get("authorization_nonce"))
    parity = _integer(authorization.get("yParity", authorization.get("y_parity")))
    r_value = _integer(authorization["r"])
    s_value = _integer(authorization["s"])
    if parity not in (0, 1):
        raise ValueError("authorization y_parity must be 0 or 1")
    if not 0 < r_value < SECP256K1_N:
        raise ValueError("authorization r is outside the secp256k1 scalar range")
    if not 0 < s_value <= SECP256K1_N // 2:
        raise ValueError("authorization s violates the EIP-2 low-s requirement")
    message_hash = authorization_message_hash(chain_id, delegate, nonce)
    public_key = Signature(vrs=(parity, r_value, s_value)).recover_public_key_from_msg_hash(
        message_hash
    )
    return "0x" + public_key.to_canonical_address().hex(), "0x" + message_hash.hex()
