#!/usr/bin/env python3
"""Repair Excel-truncated benign_cleared runtime bytecodes via prefix-verified eth_getCode.

Context: 89 benign_cleared rows in the frozen corpus carry bytecode truncated at exactly
32,767 hex characters (the Excel cell limit). The USENIX artifact's own .hex files carry the
same truncation, so the only programmatic repair is a read-only, cached RPC refetch.

Repair policy (fixed before any fetch result was inspected):
  1. A row qualifies when its stored bytecode is exactly 32,767 characters long.
  2. Fetch eth_getCode(address, "latest") on the row's chain.
  3. Normalize both sides with the frozen normalization (lowercase, strip 0x, drop trailing
     odd nibble).
  4. REPAIRED  <=> fetched code is non-empty, is NOT an EIP-7702 designator, is strictly
     longer than the stored truncated prefix, and starts with that prefix.
  5. Anything else (empty code, prefix mismatch, RPC failure) => UNREPAIRED; the row keeps
     its truncated bytecode and is flagged `truncated_unrepaired` downstream.
Results are cached in repair_rpc_cache.json; reruns are offline.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import urllib.request

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
AUDIT = os.path.abspath(os.path.join(HERE, ".."))
CACHE = os.path.join(AUDIT, "repair_rpc_cache.json")
OUT = os.path.join(AUDIT, "truncation_repair.csv")

RPCS = {
    "ethereum": "https://ethereum-rpc.publicnode.com",
    "base": "https://base-rpc.publicnode.com",
    "bnb": "https://bsc-rpc.publicnode.com",
    "polygon": "https://polygon-bor-rpc.publicnode.com",
    "arbitrum": "https://arbitrum-one-rpc.publicnode.com",
    "optimism": "https://optimism-rpc.publicnode.com",
    "gnosis": "https://gnosis-rpc.publicnode.com",
}
EXCEL_CAP = 32767


def norm(raw: object) -> str:
    h = str(raw).lower().strip()
    if h.startswith("0x"):
        h = h[2:]
    return h[:-1] if len(h) % 2 else h


def sha(h: str) -> str:
    return hashlib.sha256(h.encode()).hexdigest()


def is_designator(h: str) -> bool:
    return len(h) == 46 and h.startswith("ef0100")


def rpc_getcode(chain: str, address: str, retries: int = 4) -> dict:
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_getCode",
                          "params": [address, "latest"]}).encode()
    last_error = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(RPCS[chain], data=payload, headers={
                "Content-Type": "application/json",
                "User-Agent": "AuthGuard-7702 anonymous research audit (read-only eth_getCode)",
            })
            with urllib.request.urlopen(req, timeout=30) as response:
                body = json.loads(response.read().decode())
            if "result" in body:
                return {"ok": True, "code": body["result"],
                        "fetched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
            last_error = str(body.get("error"))
        except Exception as exc:  # noqa: BLE001 - recorded, retried
            last_error = repr(exc)
        time.sleep(1.5 * (attempt + 1))
    return {"ok": False, "error": last_error}


def main() -> int:
    cap = pd.read_csv(os.path.join(ROOT, "capability_dataset.csv"))
    cap["hexlen"] = cap["bytecode"].astype(str).str.len()
    rows = cap[cap["hexlen"] == EXCEL_CAP].copy()
    assert (rows["class"] == "benign_cleared").all(), \
        "truncation repair scope changed; expected benign_cleared only"
    print(f"[repair] {len(rows)} truncated rows to check")

    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    records = []
    for _, row in rows.iterrows():
        chain = str(row["chain"]).lower()
        address = str(row["address"]).lower()
        key = f"{chain}:{address}"
        if key not in cache:
            cache[key] = rpc_getcode(chain, address)
            json.dump(cache, open(CACHE, "w"), indent=1)
            time.sleep(0.25)
        entry = cache[key]
        prefix = norm(row["bytecode"])  # 32,764 hex chars after dropping the odd nibble
        record = {"chain": chain, "address": address, "stored_hexlen": int(row["hexlen"]),
                  "prefix_hexlen": len(prefix)}
        if not entry.get("ok"):
            record.update(status="rpc_failed", detail=entry.get("error", "")[:200])
        else:
            fetched = norm(entry["code"])
            if fetched in ("", "0x") or len(fetched) < 4:
                record.update(status="empty_code", fetched_hexlen=len(fetched))
            elif is_designator(fetched):
                record.update(status="designator", fetched_hexlen=len(fetched))
            elif len(fetched) > len(prefix) and fetched.startswith(prefix):
                record.update(status="repaired", fetched_hexlen=len(fetched),
                              repaired_sha256=sha(fetched))
            elif fetched == prefix:
                # code genuinely ends exactly at the truncation boundary: implausible but
                # would mean the stored bytes were complete after nibble-drop
                record.update(status="exact_prefix_no_extension", fetched_hexlen=len(fetched))
            else:
                record.update(status="prefix_mismatch", fetched_hexlen=len(fetched))
        records.append(record)

    frame = pd.DataFrame(records)
    frame.to_csv(OUT, index=False)
    print(frame["status"].value_counts().to_string())
    print(f"[repair] wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
