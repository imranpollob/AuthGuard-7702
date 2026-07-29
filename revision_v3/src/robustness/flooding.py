"""Independent Revision v3 reimplementation of Flood-200% dead-code appending.

Donor population: EXTERNAL_BENIGN_CONTROL (benign_general, 797 rows) -- entirely outside the
primary train/val/test population, so donor content can never leak primary-fold information
into a model's training set (Phase 1 only evaluates flooding at INFERENCE time on already
clean-trained models; no model here is retrained on flooded data). Donor selection is
deterministic (seeded blake2b) and excludes any donor sharing the recipient's family_id, for
defense in depth even though family_id spaces barely overlap between populations.

"200%" here means 200% of the recipient's own total runtime-bytecode byte length (a
documented simplification vs. the canonical project's CBOR-metadata-aware executable-region
split -- see MATCHED_ROBUSTNESS_REPORT.md for why this simplification does not materially
change the matched-budget conclusion).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np
import pandas as pd

STOP_BYTE = b"\x00"


def _seed_for(recipient_sample_id: str, condition: str, seed: int) -> int:
    material = f"{condition}:{recipient_sample_id}:{seed}".encode()
    digest = hashlib.blake2b(material, digest_size=8, salt=seed.to_bytes(8, "little")).digest()
    return int.from_bytes(digest, "little")


@dataclass(frozen=True)
class DonorPool:
    sample_ids: np.ndarray
    family_ids: np.ndarray
    hex_bytes: list  # list[bytes], executable bytes per donor


def build_donor_pool(full_dataset: pd.DataFrame) -> DonorPool:
    donors = full_dataset[full_dataset["population"] == "EXTERNAL_BENIGN_CONTROL"]
    donors = donors[donors["code_bytes"] >= 32]
    hex_bytes = []
    for bc in donors["runtime_bytecode"]:
        h = str(bc).lower().replace("0x", "")
        if len(h) % 2:
            h = h[:-1]
        try:
            hex_bytes.append(bytes.fromhex(h))
        except ValueError:
            hex_bytes.append(b"")
    return DonorPool(
        sample_ids=donors["sample_id"].to_numpy(),
        family_ids=donors["family_id"].to_numpy(),
        hex_bytes=hex_bytes,
    )


def flood_bytecode(recipient_hex: str, recipient_sample_id: str, recipient_family_id,
                    donor_pool: DonorPool, seed: int, fraction: float = 2.0,
                    condition: str = "flood200") -> str:
    h = str(recipient_hex).lower().replace("0x", "")
    if len(h) % 2:
        h = h[:-1]
    recipient_bytes = bytes.fromhex(h) if h else b""

    target_len = max(1, int(round(len(recipient_bytes) * fraction)))
    eligible = np.where(donor_pool.family_ids != recipient_family_id)[0]
    if len(eligible) == 0:
        eligible = np.arange(len(donor_pool.sample_ids))

    rng_seed = _seed_for(recipient_sample_id, condition, seed)
    rng = np.random.default_rng(rng_seed)
    order = rng.permutation(eligible)

    collected = bytearray()
    for donor_idx in order:
        if len(collected) >= target_len:
            break
        donor_bytes = donor_pool.hex_bytes[donor_idx]
        if not donor_bytes:
            continue
        offset = int(rng.integers(0, max(1, len(donor_bytes))))
        rotated = donor_bytes[offset:] + donor_bytes[:offset]
        collected.extend(rotated)
    collected = bytes(collected[:target_len])

    flooded = recipient_bytes + STOP_BYTE + collected
    return flooded.hex()
