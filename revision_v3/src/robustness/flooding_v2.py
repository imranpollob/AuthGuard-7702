"""Phase 2 final-paper-grade Flood-200% reimplementation.

Differences from Phase 1's revision_v3/src/robustness/flooding.py (documented there as an
intentional simplification): this version (a) detects the CBOR metadata trailer and computes
"200%" against the EXECUTABLE region only, not total bytecode length, matching the canonical
project's semantics as closely as possible without importing its code; (b) exposes an
independent `transform_seed` axis (separate from model-training seed) so donor-selection
variance can be measured by generating multiple flood variants per recipient; (c) donors are
also stripped to their own executable region before being appended, so no donor's own CBOR
trailer contaminates a recipient's flood.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np
import pandas as pd

STOP_BYTE = b"\x00"
CBOR_MAP_MAJOR_TYPE_PREFIXES = {0xA0, 0xA1, 0xA2, 0xA3, 0xA4}


def find_executable_region(code: bytes) -> tuple[bytes, bytes]:
    """Best-effort detection of a Solidity-style CBOR metadata trailer: the last 2 bytes
    encode (big-endian) the length of a preceding CBOR map. Returns (executable, metadata);
    if no plausible trailer is found, returns (code, b"") -- the whole bytecode is treated as
    executable, which is always a safe fallback (never over-strips real code)."""
    n = len(code)
    if n < 4:
        return code, b""
    cbor_len = int.from_bytes(code[-2:], "big")
    split = n - 2 - cbor_len
    if 0 < cbor_len < n - 2 and split >= 0 and code[split] in CBOR_MAP_MAJOR_TYPE_PREFIXES:
        return code[:split], code[split:]
    return code, b""


def _seed_for(recipient_sample_id: str, condition: str, model_seed: int, transform_seed: int) -> int:
    material = f"{condition}:{recipient_sample_id}:{model_seed}:{transform_seed}".encode()
    digest = hashlib.blake2b(material, digest_size=8, salt=(transform_seed & 0xFFFFFFFFFFFFFFFF).to_bytes(8, "little")).digest()
    return int.from_bytes(digest, "little")


@dataclass(frozen=True)
class DonorPoolV2:
    sample_ids: np.ndarray
    family_ids: np.ndarray
    executable_bytes: list  # list[bytes], donor's OWN executable region only


def build_donor_pool_v2(full_dataset: pd.DataFrame) -> DonorPoolV2:
    donors = full_dataset[full_dataset["population"] == "EXTERNAL_BENIGN_CONTROL"]
    donors = donors[donors["code_bytes"] >= 32]
    exec_bytes_list = []
    for bc in donors["runtime_bytecode"]:
        h = str(bc).lower().replace("0x", "")
        if len(h) % 2:
            h = h[:-1]
        try:
            raw = bytes.fromhex(h)
        except ValueError:
            raw = b""
        exec_bytes, _meta = find_executable_region(raw)
        exec_bytes_list.append(exec_bytes)
    return DonorPoolV2(
        sample_ids=donors["sample_id"].to_numpy(),
        family_ids=donors["family_id"].to_numpy(),
        executable_bytes=exec_bytes_list,
    )


def flood_bytecode_v2(
    recipient_hex: str,
    recipient_sample_id: str,
    recipient_family_id,
    donor_pool: DonorPoolV2,
    model_seed: int,
    transform_seed: int,
    fraction: float = 2.0,
    condition: str = "flood200_v2",
) -> tuple[str, dict]:
    """Returns (flooded_hex, provenance_dict). provenance records donor sample_ids used,
    executable-region split point, and target length -- for the donor-isolation audit."""
    h = str(recipient_hex).lower().replace("0x", "")
    if len(h) % 2:
        h = h[:-1]
    recipient_bytes = bytes.fromhex(h) if h else b""
    exec_bytes, meta_bytes = find_executable_region(recipient_bytes)

    target_len = max(1, int(round(len(exec_bytes) * fraction)))
    eligible = np.where(donor_pool.family_ids != recipient_family_id)[0]
    if len(eligible) == 0:
        eligible = np.arange(len(donor_pool.sample_ids))

    rng_seed = _seed_for(recipient_sample_id, condition, model_seed, transform_seed)
    rng = np.random.default_rng(rng_seed)
    order = rng.permutation(eligible)

    collected = bytearray()
    donors_used = []
    for donor_idx in order:
        if len(collected) >= target_len:
            break
        donor_bytes = donor_pool.executable_bytes[donor_idx]
        if not donor_bytes:
            continue
        offset = int(rng.integers(0, max(1, len(donor_bytes))))
        rotated = donor_bytes[offset:] + donor_bytes[:offset]
        collected.extend(rotated)
        donors_used.append(str(donor_pool.sample_ids[donor_idx]))
    collected = bytes(collected[:target_len])

    # metadata trailer is dropped (flooding appends dead code after the executable region;
    # keeping a stale CBOR trailer mid-sequence would be semantically meaningless anyway)
    flooded = recipient_bytes[:len(exec_bytes)] + STOP_BYTE + collected
    provenance = {
        "recipient_sample_id": recipient_sample_id,
        "recipient_family_id": recipient_family_id,
        "executable_region_bytes": len(exec_bytes),
        "metadata_region_bytes": len(meta_bytes),
        "target_donor_bytes": target_len,
        "donors_used": donors_used,
        "model_seed": model_seed,
        "transform_seed": transform_seed,
    }
    return flooded.hex(), provenance
