"""Part 11 (Base and other Blockscout-supported chains): indexed-transaction-API collection,
avoiding a naive full block-range scan. Investigated per the brief: Base's Blockscout instance
exposes `/api/v2/advanced-filters?transaction_types=set_code_transaction&age_from=...
&age_to=...`, which returns only actual EIP-7702 (type-4 / "set_code_transaction")
transactions for a date range directly from Blockscout's index, each tagged with its
block_number -- multiple orders of magnitude fewer blocks to touch than scanning every block
in the window.

Two real findings from investigating this (documented, not asserted):
1. Blockscout's own `authorization_list` field on the tx-detail endpoint was found EMPTY for
   confirmed type-4 transactions (checked against multiple real Base txs) -- not usable as
   the actual authorization-tuple source.
2. The publicly available free RPC endpoints already in rpc_client.py could not serve
   5-month-old Base historical data ("pruned history unavailable" / rate-limited); the
   official Base team RPC (mainnet.base.org) could, and was added to rpc_client.py's
   endpoint list for the `base` chain as a result.

So this collector uses Blockscout's advanced-filters purely to discover which BLOCK NUMBERS
contain type-4 transactions (cheap, indexed), then fetches only those specific blocks via
the existing, proven eth_getBlockByNumber path (same method the plain block-scanning
collector uses for Ethereum) to read the real `authorizationList` field. Writes to the same
ROW_FIELDS/CSV schema as temporal/collector.py.

Checkpointed on the Blockscout pagination cursor -- safe to resume.

Usage:
    python3 revision_v3/experiments/temporal_v2/indexed_collector.py --chain base \
        --age-from 2026-02-01T00:00:00.00Z --age-to 2026-06-30T00:00:00.00Z --run-id v2_window
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "revision_v3", "src"))

from temporal.checkpoint import load_checkpoint, save_checkpoint  # noqa: E402
from temporal.collector import _row_writer  # noqa: E402
from temporal.rpc_client import ChainClient, RpcError  # noqa: E402

BLOCKSCOUT_HOSTS = {
    "base": "base.blockscout.com", "bnb": "bsc.blockscout.com",
    "optimism": "optimism.blockscout.com", "arbitrum": "arbitrum.blockscout.com",
    "polygon": "polygon.blockscout.com", "gnosis": "gnosis.blockscout.com",
    "ethereum": "eth.blockscout.com",
}
USER_AGENT = "AuthGuard-7702-research/1.0 (academic reproducibility pipeline)"


def http_get_json(url: str, timeout: int = 25, max_retries: int = 4):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_err = None
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            last_err = e
            time.sleep(min(2 ** attempt, 8))
    raise RuntimeError(f"failed after {max_retries} retries: {last_err}")


def fetch_page(chain: str, age_from: str, age_to: str, page_params: dict | None) -> dict:
    host = BLOCKSCOUT_HOSTS[chain]
    url = (f"https://{host}/api/v2/advanced-filters?transaction_types=set_code_transaction"
           f"&age_from={age_from}&age_to={age_to}")
    if page_params:
        for k, v in page_params.items():
            if v is not None:
                url += f"&{k}={v}"
    return http_get_json(url)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chain", required=True, choices=list(BLOCKSCOUT_HOSTS))
    parser.add_argument("--age-from", required=True)
    parser.add_argument("--age-to", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--max-blocks", type=int, default=None, help="debug: stop after N fetched blocks")
    args = parser.parse_args()

    state = load_checkpoint(args.chain, args.run_id)
    state.setdefault("next_page_params", None)
    state.setdefault("n_pages_fetched", 0)
    state.setdefault("n_hashes_discovered", 0)
    state.setdefault("n_blocks_fetched", 0)
    state.setdefault("n_authorization_entries", 0)
    state.setdefault("n_type4_txs", 0)
    state.setdefault("n_rpc_errors", 0)
    state.setdefault("pagination_complete", False)
    state.setdefault("processed_blocks", [])

    client = ChainClient(args.chain)
    f, writer = _row_writer(args.chain, args.run_id)

    try:
        while not state["pagination_complete"]:
            page = fetch_page(args.chain, args.age_from, args.age_to, state["next_page_params"])
            items = page["items"]
            state["n_pages_fetched"] += 1
            state["n_hashes_discovered"] += len(items)

            block_numbers = sorted({item["block_number"] for item in items
                                     if item.get("block_number") not in state["processed_blocks"]})

            for block_num in block_numbers:
                try:
                    block = client.get_block(block_num, full_transactions=True)
                except RpcError as e:
                    state["n_rpc_errors"] += 1
                    print(f"[indexed_collector] {args.chain} block {block_num}: RPC error: {e}", flush=True)
                    continue
                if block is None:
                    state["n_rpc_errors"] += 1
                    continue
                ts = int(block["timestamp"], 16)
                for tx in block.get("transactions", []):
                    if tx.get("type") != "0x4":
                        continue
                    state["n_type4_txs"] += 1
                    for auth in tx.get("authorizationList", []):
                        state["n_authorization_entries"] += 1
                        writer.writerow({
                            "chain": args.chain, "block_number": block_num, "block_timestamp_unix": ts,
                            "tx_hash": tx.get("hash"), "tx_from": tx.get("from"),
                            "authorization_chain_id": auth.get("chainId"),
                            "delegate_address": auth.get("address"),
                            "authorization_nonce": auth.get("nonce"),
                        })
                state["n_blocks_fetched"] += 1
                state["processed_blocks"].append(block_num)
                state["processed_blocks"] = state["processed_blocks"][-2000:]
                if state["n_blocks_fetched"] % 10 == 0:
                    f.flush()
                    save_checkpoint(args.chain, args.run_id, state)
                    print(f"[indexed_collector] {args.chain}: {state['n_blocks_fetched']} blocks fetched, "
                          f"{state['n_type4_txs']} type-4 txs, "
                          f"{state['n_authorization_entries']} authorization entries so far", flush=True)
                if args.max_blocks and state["n_blocks_fetched"] >= args.max_blocks:
                    save_checkpoint(args.chain, args.run_id, state)
                    print("[indexed_collector] hit --max-blocks debug limit, stopping")
                    return 0

            next_params = page.get("next_page_params")
            state["next_page_params"] = next_params
            save_checkpoint(args.chain, args.run_id, state)
            if not next_params or len(items) == 0:
                state["pagination_complete"] = True
                save_checkpoint(args.chain, args.run_id, state)
                break
    finally:
        f.flush()
        f.close()
        save_checkpoint(args.chain, args.run_id, state)

    print(f"[indexed_collector] {args.chain}: DONE. {state['n_blocks_fetched']} blocks, "
          f"{state['n_type4_txs']} type-4 txs, {state['n_authorization_entries']} authorization entries, "
          f"{state['n_rpc_errors']} RPC errors")
    return 0


if __name__ == "__main__":
    sys.exit(main())
