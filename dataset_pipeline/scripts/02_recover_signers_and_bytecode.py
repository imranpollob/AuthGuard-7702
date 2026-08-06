"""Stage 2b: for the raw per-authorization CSV produced by 01_collect_authorizations.py --
1. recover the actual signing authority for every authorization entry via ECDSA (not tx.from),
2. build the complete collected population of distinct nonzero delegate addresses with
   first-observed block/tx, authorization frequency, and runtime bytecode fetched at first
   observation, marking delegates with no available bytecode as NOTSCREENABLE,
3. write both a per-authorization enriched table and the per-delegate population table.

No filtering by suspicion, labels, or predictions happens here -- every distinct nonzero
delegate address observed in the raw scan is kept, including NOTSCREENABLE ones.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "dataset_pipeline")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pandas as pd  # noqa: E402

from lib.config import load_config  # noqa: E402
from lib.bytecode_cache import BytecodeCache  # noqa: E402
from lib.repo_paths import add_revision_v3_src_to_path  # noqa: E402

add_revision_v3_src_to_path()
from temporal.authorization import recover_authority  # noqa: E402
from temporal.rpc_client import ChainClient, RpcError  # noqa: E402

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


def recover_row(row: pd.Series) -> tuple[str | None, str | None]:
    try:
        addr, _msg_hash = recover_authority({
            "chainId": row["authorization_chain_id"],
            "address": row["delegate_address"],
            "nonce": row["authorization_nonce"],
            "yParity": row["authorization_y_parity"],
            "r": row["authorization_r"],
            "s": row["authorization_s"],
        })
        return addr, None
    except Exception as e:  # noqa: BLE001 -- deliberately broad: any malformed tuple is a data issue, not a crash
        return None, f"{type(e).__name__}: {e}"


def main():
    cfg = load_config()
    out_dir = cfg["_resolved_paths"]["collected_delegates"]
    run_id = cfg["run_id"]
    cache = BytecodeCache(cfg["_resolved_paths"]["bytecode_cache"])

    for chain in cfg["chains"]:
        raw_path = os.path.join(out_dir, f"{run_id}_{chain}_authorizations_raw.csv")
        if not os.path.exists(raw_path):
            print(f"[recover] {chain}: no raw file at {raw_path}, skipping")
            continue
        raw = pd.read_csv(raw_path, dtype=str)
        print(f"[recover] {chain}: {len(raw)} raw authorization entries")

        recovered = raw.apply(recover_row, axis=1, result_type="expand")
        raw["recovered_authority"] = recovered[0]
        raw["recovery_error"] = recovered[1]
        raw["delegate_address"] = raw["delegate_address"].str.lower()
        raw["recovered_authority"] = raw["recovered_authority"].where(raw["recovered_authority"].isna(), raw["recovered_authority"].str.lower())

        n_recovered = raw["recovered_authority"].notna().sum()
        print(f"[recover] {chain}: recovered signer for {n_recovered}/{len(raw)} authorization entries")

        nonzero = raw[raw["delegate_address"] != ZERO_ADDRESS.lower()].copy()
        nonzero["block_number"] = nonzero["block_number"].astype(int)

        first_obs = (
            nonzero.sort_values("block_number")
            .groupby("delegate_address", as_index=False)
            .first()[["delegate_address", "block_number", "tx_hash", "block_timestamp_unix"]]
            .rename(columns={
                "block_number": "first_observed_block",
                "tx_hash": "first_observed_tx_hash",
                "block_timestamp_unix": "first_observed_block_timestamp_unix",
            })
        )
        freq = nonzero.groupby("delegate_address").size().reset_index(name="authorization_frequency")
        distinct_authorities = (
            nonzero.groupby("delegate_address")["recovered_authority"].nunique().reset_index(name="distinct_recovered_authorities")
        )
        distinct_senders = (
            nonzero.groupby("delegate_address")["tx_from"].nunique().reset_index(name="distinct_tx_senders")
        )

        population = first_obs.merge(freq, on="delegate_address").merge(distinct_authorities, on="delegate_address").merge(distinct_senders, on="delegate_address")

        client = ChainClient(chain)
        bytecodes, hashes, lengths, statuses, errors = [], [], [], [], []
        for _, prow in population.iterrows():
            addr = prow["delegate_address"]
            block_tag = hex(int(prow["first_observed_block"]))
            cached = cache.get(chain, addr, block_tag)
            if cached is not None:
                code_hex, err = cached["code"], cached["error"]
            else:
                try:
                    code_hex = client.get_code(addr, block_tag=block_tag)
                    err = None
                except RpcError as e:
                    code_hex = None
                    err = str(e)
                cache.put(chain, addr, block_tag, {"code": code_hex, "error": err})

            if err is not None:
                bytecodes.append(None); hashes.append(None); lengths.append(None)
                statuses.append("NOTSCREENABLE"); errors.append(err)
            elif code_hex in (None, "0x", "0x0"):
                bytecodes.append(code_hex); hashes.append(None); lengths.append(0)
                statuses.append("NOTSCREENABLE"); errors.append(None)
            else:
                code_bytes = bytes.fromhex(code_hex[2:])
                bytecodes.append(code_hex)
                hashes.append(hashlib.sha256(code_bytes).hexdigest())
                lengths.append(len(code_bytes))
                statuses.append("OK"); errors.append(None)

        cache.save()
        population["runtime_bytecode"] = bytecodes
        population["bytecode_sha256"] = hashes
        population["bytecode_length"] = lengths
        population["retrieval_status"] = statuses
        population["retrieval_error"] = errors
        population["chain"] = chain

        pop_path = os.path.join(out_dir, f"{run_id}_{chain}_population.csv")
        population.to_csv(pop_path, index=False)

        enriched = raw.merge(
            population[["delegate_address", "first_observed_block", "first_observed_tx_hash",
                        "authorization_frequency", "distinct_recovered_authorities",
                        "distinct_tx_senders", "bytecode_sha256", "bytecode_length", "retrieval_status"]],
            on="delegate_address", how="left",
        )
        enriched_path = os.path.join(out_dir, f"{run_id}_{chain}_authorizations_enriched.csv")
        enriched.to_csv(enriched_path, index=False)

        n_notscreenable = (population["retrieval_status"] == "NOTSCREENABLE").sum()
        summary = {
            "chain": chain,
            "n_authorization_entries_total": int(len(raw)),
            "n_authorization_entries_recovered_signer": int(n_recovered),
            "n_distinct_nonzero_delegates": int(len(population)),
            "n_notscreenable": int(n_notscreenable),
            "n_screenable": int(len(population) - n_notscreenable),
            "population_csv": pop_path,
            "authorizations_enriched_csv": enriched_path,
        }
        print(f"[recover] {chain}: {json.dumps(summary, indent=2)}")

        summary_path = os.path.join(out_dir, f"{run_id}_{chain}_population_summary.json")
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2)


if __name__ == "__main__":
    main()
