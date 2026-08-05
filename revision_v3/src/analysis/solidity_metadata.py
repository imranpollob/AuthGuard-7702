"""Conservative recognition of Solidity's CBOR runtime metadata trailer.

The final two bytes of Solidity-produced runtime bytecode encode the byte length of a CBOR
map immediately before them.  Treating an arbitrary suffix as metadata would hide executable
code, so this module removes a suffix only when all of the following hold:

* the declared length lands exactly on a decodable CBOR object;
* that object is a non-empty map with only documented Solidity metadata keys; and
* every value has the documented byte shape (or the historical ``experimental`` flag).

Any malformed, unfamiliar, or ambiguous suffix is retained as executable bytecode.  This is
deliberately stricter than checking only the first CBOR byte.
"""
from __future__ import annotations

from io import BytesIO

import cbor2


_BYTE_LENGTHS = {
    "ipfs": 34,   # multihash: sha2-256 prefix (0x12, 0x20) plus 32-byte digest
    "bzzr0": 32,
    "bzzr1": 32,
    "solc": 3,    # major, minor, patch for released compiler versions
}
_KNOWN_KEYS = frozenset((*_BYTE_LENGTHS, "experimental"))


def _has_valid_value_shape(key: str, value: object) -> bool:
    if key == "experimental":
        return value is True
    if not isinstance(value, bytes) or len(value) != _BYTE_LENGTHS[key]:
        return False
    if key == "ipfs" and not value.startswith(b"\x12\x20"):
        return False
    return True


def validated_solidity_metadata_start(code: bytes) -> int:
    """Return the metadata start, or ``len(code)`` when validation does not succeed."""
    if len(code) < 4:
        return len(code)
    metadata_length = int.from_bytes(code[-2:], "big")
    start = len(code) - metadata_length - 2
    if start < 0 or start >= len(code) - 2:
        return len(code)

    encoded = code[start:-2]
    stream = BytesIO(encoded)
    try:
        metadata = cbor2.CBORDecoder(stream).decode()
    except (ValueError, TypeError, EOFError):
        return len(code)
    if stream.tell() != len(encoded):
        return len(code)
    if not isinstance(metadata, dict) or not metadata:
        return len(code)
    if not all(isinstance(key, str) and key in _KNOWN_KEYS for key in metadata):
        return len(code)
    if not any(key in metadata for key in ("ipfs", "bzzr0", "bzzr1")):
        return len(code)
    if not all(_has_valid_value_shape(key, value) for key, value in metadata.items()):
        return len(code)
    return start
