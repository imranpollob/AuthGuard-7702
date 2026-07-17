"""Revision-v2 bounded transformations with safe truncated-PUSH handling."""
from __future__ import annotations

from .features import normalize_bytecode


def _safe_addr_immediates(mut, bytecode, seed_material):
    """Equivalent to frozen M2 address rewriting, clamped to available immediate bytes."""
    value = bytearray(bytecode)
    metadata_start = mut.find_metadata_split(value)
    rng = mut.det_rng("addr:" + seed_material)
    for _opcode_index, size, start, end in mut.push_positions(value, metadata_start):
        if size == 20:
            # A malformed/truncated PUSH20 may report an end beyond the bytearray. Rewriting only
            # bytes that actually exist preserves length and prevents the historical IndexError.
            for index in range(start, min(end, len(value), metadata_start)):
                value[index] = int(rng.integers(0, 256))
    return value


def make_variant_isolated_safe(pools, row: dict, outer_fold: int, partition: str,
                               condition: str, rng_domain: str) -> str:
    """Donor-isolated generator matching the frozen protocol with one bounds fix."""
    mut = pools.__class__.__module__  # only used to make accidental shadowing obvious
    del mut
    # DonorPools is defined in the dynamically imported `pools` module.
    import pools as pools_module
    mut = pools_module.mut
    seed_address = f"{rng_domain}:{row['sid']}"
    value = mut.to_bytes(row["bytecode"])
    if condition == "M0":
        return normalize_bytecode(row["bytecode"])
    if condition in ("M1", "M2", "M3", "M3F200"):
        value = mut.mut_metadata(value, seed_address)
        if condition != "M1":
            value = _safe_addr_immediates(mut, value, seed_address)
            if condition == "M2":
                return pools.flood(value, row, outer_fold, partition, condition, 0.20,
                                   rng_domain).hex()
            value = mut.mut_selector_rewrite(value, seed_address)
            fraction = 0.20 if condition == "M3" else 2.0
            return pools.flood(value, row, outer_fold, partition, condition, fraction,
                               rng_domain).hex()
        return value.hex()
    fraction = {"F25": 0.25, "F50": 0.5, "F100": 1.0,
                "F200": 2.0}[condition]
    return pools.flood(value, row, outer_fold, partition, condition, fraction,
                       rng_domain).hex()

