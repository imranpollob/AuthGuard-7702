"""Minimal, dependency-free JSON-RPC client for the temporal collector.

No batching (per prior-session finding: eth.drpc.org returns HTTP 500 on batched requests) --
every call is a single sequential POST. Retries with exponential backoff on transient errors.
Public, keyless endpoints only (no Etherscan/Dune/Alchemy keys exist in this environment).
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

# Public, keyless RPC endpoints per historical chain. eth.drpc.org is Ethereum-only and the
# most capable free endpoint found in prior sessions (archive state, trace_* support, but no
# batching); the others are chain-specific public endpoints. publicnode.com endpoints require
# a browser User-Agent header or they 403.
CHAIN_RPC_ENDPOINTS = {
    "ethereum": ["https://eth.drpc.org", "https://ethereum-rpc.publicnode.com"],
    # base-rpc.publicnode.com's free tier was observed (2026-07-30 pilot) to return
    # "pruned history unavailable" for blocks ~7.7M behind its head -- base.drpc.org served
    # the same historical block fine, so it is tried first for this chain.
    "base": ["https://base.drpc.org", "https://base-rpc.publicnode.com"],
    "bnb": ["https://bsc-rpc.publicnode.com", "https://bsc.drpc.org"],
    "optimism": ["https://optimism-rpc.publicnode.com", "https://optimism.drpc.org"],
    "arbitrum": ["https://arbitrum-one-rpc.publicnode.com", "https://arbitrum.drpc.org"],
    "polygon": ["https://polygon-bor-rpc.publicnode.com", "https://polygon.drpc.org"],
    "gnosis": ["https://gnosis-rpc.publicnode.com", "https://gnosis.drpc.org"],
}

USER_AGENT = "Mozilla/5.0 (compatible; AuthGuard-7702-temporal-collector/1.0)"


class RpcError(RuntimeError):
    pass


def rpc_call(url: str, method: str, params: list, timeout: int = 20, max_retries: int = 3) -> dict:
    payload = json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": 1}).encode()
    last_err = None
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(
                url, data=payload,
                headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read())
            if "error" in body:
                raise RpcError(f"{url} {method}: {body['error']}")
            return body["result"]
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, RpcError) as e:
            last_err = e
            time.sleep(min(2 ** attempt, 8))
    raise RpcError(f"failed after {max_retries} retries: {last_err}")


class ChainClient:
    def __init__(self, chain: str):
        if chain not in CHAIN_RPC_ENDPOINTS:
            raise ValueError(f"unsupported chain: {chain}")
        self.chain = chain
        self.endpoints = list(CHAIN_RPC_ENDPOINTS[chain])
        self._active_idx = 0

    def _call(self, method: str, params: list) -> dict:
        errors = []
        for _ in range(len(self.endpoints)):
            url = self.endpoints[self._active_idx]
            try:
                return rpc_call(url, method, params)
            except RpcError as e:
                errors.append(str(e))
                self._active_idx = (self._active_idx + 1) % len(self.endpoints)
        raise RpcError(f"all endpoints failed for {self.chain}: {errors}")

    def block_number(self) -> int:
        return int(self._call("eth_blockNumber", []), 16)

    def get_block(self, block_number: int, full_transactions: bool = True) -> dict | None:
        return self._call("eth_getBlockByNumber", [hex(block_number), full_transactions])

    def get_code(self, address: str, block_tag: str = "latest") -> str:
        return self._call("eth_getCode", [address, block_tag])

    def find_block_by_timestamp(self, target_unix_ts: int) -> int:
        """Binary search over block numbers for the first block with timestamp >=
        target_unix_ts. A handful of RPC calls, not a full scan -- reproducible date-to-block
        resolution without a paid indexer."""
        lo, hi = 0, self.block_number()
        hi_block = self.get_block(hi, full_transactions=False)
        if int(hi_block["timestamp"], 16) < target_unix_ts:
            return hi  # target is in the future relative to chain head
        while lo < hi:
            mid = (lo + hi) // 2
            block = self.get_block(mid, full_transactions=False)
            if block is None:
                lo = mid + 1
                continue
            ts = int(block["timestamp"], 16)
            if ts < target_unix_ts:
                lo = mid + 1
            else:
                hi = mid
        return lo
