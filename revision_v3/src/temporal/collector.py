"""Core temporal collector: scans a block range on one chain, extracts EIP-7702
authorization-list entries from type-0x4 transactions, retrieves delegate runtime bytecode,
and writes one row per (block, tx, authorization-entry) to an append-only CSV. Checkpointed
and resumable -- safe to interrupt and re-run.
"""
from __future__ import annotations

import csv
import os
import time

from temporal.rpc_client import ChainClient, RpcError  # noqa: E402
from temporal.checkpoint import load_checkpoint, save_checkpoint  # noqa: E402

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "temporal", "raw")

ROW_FIELDS = [
    "chain", "block_number", "block_timestamp_unix", "tx_hash", "tx_from",
    "authorization_chain_id", "delegate_address", "authorization_nonce",
]


def _row_writer(chain: str, run_id: str):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, f"{run_id}_{chain}_authorizations.csv")
    is_new = not os.path.exists(path)
    if not is_new:
        with open(path, "rb") as probe:
            if probe.readline().startswith(b"version https://git-lfs.github.com/spec/v1"):
                raise RuntimeError(
                    f"refusing to append authorization rows to an unhydrated Git-LFS pointer: {path}; "
                    "run `git lfs checkout -- <path>` first"
                )
    f = open(path, "a", newline="")
    writer = csv.DictWriter(f, fieldnames=ROW_FIELDS, lineterminator="\n")
    if is_new:
        writer.writeheader()
    return f, writer


def scan_block_range(chain: str, start_block: int, end_block: int, run_id: str,
                      fetch_bytecode: bool = True, sleep_between_blocks: float = 0.0) -> dict:
    """Scans [start_block, end_block] inclusive, resuming from checkpoint if one exists and
    covers part of this range. Returns the final checkpoint state."""
    client = ChainClient(chain)
    state = load_checkpoint(chain, run_id)
    resume_from = start_block
    if state["last_scanned_block"] is not None and state["last_scanned_block"] >= start_block - 1:
        resume_from = state["last_scanned_block"] + 1

    f, writer = _row_writer(chain, run_id)
    t0 = time.time()
    n_blocks_this_run = 0
    try:
        for block_num in range(resume_from, end_block + 1):
            try:
                block = client.get_block(block_num, full_transactions=True)
            except RpcError as e:
                state["n_rpc_errors"] += 1
                print(f"[collector] {chain} block {block_num}: RPC error, will resume here next run: {e}", flush=True)
                break  # stop; checkpoint was not advanced past this block, so a rerun retries it
            if block is None:
                state["n_rpc_errors"] += 1
                break

            ts = int(block["timestamp"], 16)
            for tx in block.get("transactions", []):
                if tx.get("type") != "0x4":
                    continue
                state["n_type4_txs"] += 1
                for auth in tx.get("authorizationList", []):
                    state["n_authorization_entries"] += 1
                    writer.writerow({
                        "chain": chain, "block_number": block_num, "block_timestamp_unix": ts,
                        "tx_hash": tx.get("hash"), "tx_from": tx.get("from"),
                        "authorization_chain_id": auth.get("chainId"),
                        "delegate_address": auth.get("address"),
                        "authorization_nonce": auth.get("nonce"),
                    })

            state["last_scanned_block"] = block_num
            state["n_blocks_scanned"] += 1
            n_blocks_this_run += 1
            if n_blocks_this_run % 50 == 0:
                f.flush()
                save_checkpoint(chain, run_id, state)
            if sleep_between_blocks:
                time.sleep(sleep_between_blocks)
    finally:
        f.flush()
        f.close()
        save_checkpoint(chain, run_id, state)

    elapsed = time.time() - t0
    state["last_run_wall_seconds"] = elapsed
    state["last_run_blocks_per_second"] = n_blocks_this_run / elapsed if elapsed > 0 else None
    state["last_run_n_blocks"] = n_blocks_this_run
    save_checkpoint(chain, run_id, state)
    return state
