#!/usr/bin/env python3
"""Partition-isolated, multi-donor flooding pools (donor_isolation_protocol.md v1.1).

Donor corpus: task-aligned benign_general (primary) or benign_cleared (sensitivity arm).
Roles are fold-aligned: a donor family's role for outer fold f follows its stored outer fold
(test if == f, val if == (f+1)%5, else train). Donor selection is a deterministic function of
(experiment, fold, rng_domain, recipient sid, condition, fraction) and never of the label.
"""
from __future__ import annotations

import hashlib
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
sys.path.insert(0, os.path.join(ROOT, "revision_v2", "experiments", "common"))

from ag_common import normalize_bytecode  # noqa: E402
import importlib.util as _ilu  # noqa: E402

_spec = _ilu.spec_from_file_location("mut04_v2", os.path.join(ROOT, "pipeline", "04_mutations.py"))
mut = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(mut)

SEED = 7702
MIN_EXEC_BYTES = 64
N_OUTER = 5


def _bseed(*parts) -> int:
    h = hashlib.blake2b(":".join(str(p) for p in parts).encode(), digest_size=8,
                        salt=SEED.to_bytes(8, "little"))
    return int.from_bytes(h.digest(), "little")


class DonorPools:
    def __init__(self, df: pd.DataFrame, donor_class: str, population_foldcol: str,
                 experiment_id: str):
        """df: full task-aligned corpus (with sid, bc columns added).
        donor_class: 'benign_general' or 'benign_cleared'.
        population_foldcol: fold column defining recipient partitions
                            ('outer_fold_primary' for the primary task)."""
        self.experiment_id = experiment_id
        self.donor_class = donor_class
        cand = df[df["class"] == donor_class].copy()
        execs, keep = [], []
        for idx, row in cand.iterrows():
            b = mut.to_bytes(row["bc"])
            ms = mut.find_metadata_split(b)
            if ms >= MIN_EXEC_BYTES:
                execs.append(bytes(b[:ms]))
                keep.append(idx)
        self.donors = cand.loc[keep].reset_index(drop=True)
        self.donors["exec_bytes"] = execs
        self.donors["exec_sha"] = [hashlib.sha256(e).hexdigest() for e in execs]
        # Deduplicate by executable-region hash (deterministic keep: smallest sid), so an
        # identical donor segment can never appear under two families/roles.
        self.donors = (self.donors.sort_values("sid")
                       .drop_duplicates("exec_sha", keep="first")
                       .reset_index(drop=True))

        # family role fold: population fold if the family appears in the recipient
        # population; else the donor row's stored outer_fold_secondary (deterministic).
        pop_fold = (df.dropna(subset=[population_foldcol])
                      .groupby("family_id")[population_foldcol].first().astype(int))
        fam_fold = {}
        for fam, grp in self.donors.groupby("family_id"):
            if fam in pop_fold.index:
                fam_fold[fam] = int(pop_fold[fam])
            else:
                fam_fold[fam] = int(grp["outer_fold_secondary"].iloc[0])
        self.donors["role_fold"] = self.donors["family_id"].map(fam_fold)
        self.ledger_rows: list[dict] = []

    def pool(self, outer_fold: int, partition: str) -> pd.DataFrame:
        rf = self.donors["role_fold"].to_numpy()
        if partition == "test":
            m = rf == outer_fold
        elif partition == "val":
            m = rf == (outer_fold + 1) % N_OUTER
        elif partition == "train":
            m = (rf != outer_fold) & (rf != (outer_fold + 1) % N_OUTER)
        else:
            raise ValueError(partition)
        p = self.donors[m]
        assert p["family_id"].nunique() >= 10, \
            f"pool too small: fold={outer_fold} partition={partition} fams={p['family_id'].nunique()}"
        return p

    def assert_disjoint(self, outer_fold: int, partitions=("train", "val", "test")):
        fams = {p: set(self.pool(outer_fold, p)["family_id"]) for p in partitions}
        hashes = {p: set(self.pool(outer_fold, p)["exec_sha"]) for p in partitions}
        ps = list(partitions)
        for i in range(len(ps)):
            for j in range(i + 1, len(ps)):
                assert not (fams[ps[i]] & fams[ps[j]]), "donor family crosses roles"
                assert not (hashes[ps[i]] & hashes[ps[j]]), "donor hash crosses roles"

    def flood(self, recipient_bytes: bytearray, recipient_row: dict, outer_fold: int,
              partition: str, condition: str, frac: float, rng_domain: str) -> bytearray:
        """Append STOP + donor chunk sized ~frac of the recipient executable region.
        Records full provenance. Donor never from the recipient's family."""
        if frac <= 0:
            return bytearray(recipient_bytes)
        pool = self.pool(outer_fold, partition)
        pool = pool[pool["family_id"] != recipient_row["family_id"]]
        assert len(pool), "no donor outside recipient family"
        seed = _bseed(self.experiment_id, outer_fold, rng_domain,
                      recipient_row["sid"], condition, frac)
        rng = np.random.default_rng(seed)
        b = bytearray(recipient_bytes)
        ms = mut.find_metadata_split(b)
        want = max(1, int(ms * frac))
        # Concatenate seeded multi-donor segments until `want` bytes are reached, so small
        # donors cannot silently weaken the flooding stress. Each segment is ledgered.
        chunks: list[bytes] = []
        total = 0
        for seg_idx in range(64):
            if total >= want:
                break
            d = pool.iloc[int(rng.integers(0, len(pool)))]
            src = d["exec_bytes"]
            need = want - total
            off = int(rng.integers(0, max(1, len(src) - need - 1))) if len(src) > need + 1 else 0
            chunk = src[off:off + need]
            if not chunk:
                continue
            chunks.append(bytes(chunk))
            total += len(chunk)
            self.ledger_rows.append(dict(
                experiment_id=self.experiment_id, outer_fold=outer_fold,
                recipient_sid=recipient_row["sid"], recipient_address=recipient_row["address"],
                recipient_family=recipient_row["family_id"], recipient_partition=partition,
                recipient_label=int(recipient_row["y"]),
                donor_sid=str(d["chain"]) + ":" + str(d["address"]),
                donor_address=d["address"], donor_family=d["family_id"],
                donor_partition_pool=partition, donor_subset=self.donor_class,
                condition=condition, flooding_fraction=frac, segment_index=seg_idx,
                byte_offset=off, byte_length=len(chunk),
                copied_segment_sha256=hashlib.sha256(bytes(chunk)).hexdigest(),
                transformation_seed=seed, rng_domain=rng_domain,
            ))
            # both-side isolation assertions
            assert d["family_id"] != recipient_row["family_id"]
            assert int(d["role_fold"]) == (outer_fold if partition == "test"
                                           else (outer_fold + 1) % N_OUTER if partition == "val"
                                           else int(d["role_fold"]))
        return b + bytearray([0x00]) + bytearray(b"".join(chunks))

    def write_ledger(self, path: str):
        led = pd.DataFrame(self.ledger_rows)
        led.to_csv(path, index=False)
        return led


def make_variant_isolated(pools: DonorPools, row: dict, outer_fold: int, partition: str,
                          cond: str, rng_domain: str) -> str:
    """v2 variant generator: M-conditions reuse frozen mutation code (seeded per domain);
    F-conditions and the M2 dead-code component use isolated donor pools.
    Conditions: M0, M1, M2, M3, F25, F50, F100, F200, M3F200 (compound)."""
    seed_addr = f"{rng_domain}:{row['sid']}"
    b = mut.to_bytes(row["bytecode"])
    if cond == "M0":
        return normalize_bytecode(row["bytecode"])
    if cond in ("M1", "M2", "M3", "M3F200"):
        b = mut.mut_metadata(b, seed_addr)
        if cond != "M1":
            b = mut.mut_addr_immediates(b, seed_addr)
            if cond == "M2":
                b = pools.flood(b, row, outer_fold, partition, cond, 0.20, rng_domain)
                return b.hex()
            b = mut.mut_selector_rewrite(b, seed_addr)
            if cond == "M3":
                b = pools.flood(b, row, outer_fold, partition, cond, 0.20, rng_domain)
                return b.hex()
            # compound M3F200: full M3 recipe then +200% flooding
            b = pools.flood(b, row, outer_fold, partition, cond, 2.0, rng_domain)
            return b.hex()
        return b.hex()
    frac = {"F25": 0.25, "F50": 0.5, "F100": 1.0, "F200": 2.0}[cond]
    b = pools.flood(b, row, outer_fold, partition, cond, frac, rng_domain)
    return b.hex()
