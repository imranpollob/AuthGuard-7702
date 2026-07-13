#!/usr/bin/env python3
"""
fetch_benign_7702_delegates.py

THE CRITICAL PATH. None of the four artifacts contain benign EIP-7702 delegate
contracts. A pre-signing risk classifier needs negatives. This script fetches
deployed runtime bytecode for the KNOWN-LEGITIMATE 7702 delegate implementations
across the EIP-7702-enabled chains, giving you a high-confidence benign set whose
label rationale you can defend in the paper ("audited/reputable AA implementations").

It uses only public JSON-RPC eth_getCode (no API key needed for most public RPCs).
Fill in RPC URLs you trust (defaults are common public endpoints; swap for your own
Infura/Alchemy/QuickNode keys for reliability).

The SEED list below is the nameable universe of legitimate 7702 delegates as of
early 2026. VERIFY each address before trusting it as benign — addresses here are
PLACEHOLDERS you must confirm from each project's official docs/repo. The script
prints which ones resolved to non-empty code so you can audit provenance.

Deps: stdlib only (urllib). Python 3.8+.

Usage:
  # 1) edit RPCS and SEED_DELEGATES below with verified addresses
  python fetch_benign_7702_delegates.py --out benign_7702_bytecode.csv

Output CSV columns: project, source_url, chain, address, bytecode_len, bytecode
"""
import argparse, json, csv, sys, time, urllib.request, urllib.error

# ---------------------------------------------------------------------------
# EDIT THESE. Public endpoints rotate/rate-limit; use your own keys if you have them.
# ---------------------------------------------------------------------------
RPCS = {
    "ethereum": "https://ethereum-rpc.publicnode.com",
    "base":     "https://base-rpc.publicnode.com",
    "bnb":      "https://bsc-rpc.publicnode.com",
    "polygon":  "https://polygon-bor-rpc.publicnode.com",
    "arbitrum": "https://arbitrum-one-rpc.publicnode.com",
    "optimism": "https://optimism-rpc.publicnode.com",
    "gnosis":   "https://gnosis-rpc.publicnode.com",
}

# ---------------------------------------------------------------------------
# SEED delegate implementations. THESE ADDRESSES ARE PLACEHOLDERS / EXAMPLES.
# You MUST replace each with the official deployed implementation address from the
# project's docs before using the output as ground-truth benign. The point of this
# scaffold is the STRUCTURE + provenance tracking, not the specific hex.
#
# Legitimate 7702 delegate families to cover (find official addresses for each):
#   - MetaMask "delegator" / EIP-7702 smart account
#   - Safe (7702 module / SafeEIP7702)
#   - Ambire
#   - ZeroDev Kernel (7702 variant)
#   - Biconomy Nexus (7702)
#   - OKX smart account
#   - Coinbase Smart Wallet (if 7702-enabled)
#   - Uniswap's 7702 delegate (Calibur / minimal)
#   - Ithaca / Odyssey "simple 7702" reference impl
#   - Alchemy Modular Account (7702)
# ---------------------------------------------------------------------------
SEED_DELEGATES = [
    # project, source_url (official provenance), chain, address
    ("REPLACE_MetaMask_Delegator", "https://docs.metamask.io/", "ethereum", "0x0000000000000000000000000000000000000000"),
    ("REPLACE_Safe_7702",          "https://docs.safe.global/",  "ethereum", "0x0000000000000000000000000000000000000000"),
    ("REPLACE_Ambire",             "https://github.com/AmbireTech","ethereum","0x0000000000000000000000000000000000000000"),
    ("REPLACE_ZeroDev_Kernel",     "https://docs.zerodev.app/",  "ethereum", "0x0000000000000000000000000000000000000000"),
    # ... add the rest, and duplicate rows across chains where the impl is deployed.
]

def rpc_getcode(url, address, retries=3, timeout=20):
    payload = json.dumps({
        "jsonrpc": "2.0", "id": 1,
        "method": "eth_getCode", "params": [address, "latest"]
    }).encode()
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=payload,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                obj = json.loads(resp.read().decode())
            return obj.get("result", "0x")
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            if attempt == retries - 1:
                return f"ERROR:{e}"
            time.sleep(1.5 * (attempt + 1))
    return "0x"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="benign_7702_bytecode.csv")
    ap.add_argument("--sleep", type=float, default=0.3, help="delay between calls")
    args = ap.parse_args()

    placeholders = [s for s in SEED_DELEGATES if s[3] == "0x"+"0"*40 or s[0].startswith("REPLACE_")]
    if placeholders:
        print(f"WARNING: {len(placeholders)}/{len(SEED_DELEGATES)} seed rows are still")
        print("placeholders. Replace them with verified official addresses, then re-run.")
        print("Proceeding anyway so you can see the mechanics on any real rows present.\n")

    rows_out = []
    nonempty = 0
    for project, src, chain, addr in SEED_DELEGATES:
        url = RPCS.get(chain)
        if not url:
            print(f"[skip] no RPC configured for chain={chain}")
            continue
        code = rpc_getcode(url, addr)
        blen = 0 if not code.startswith("0x") else (len(code) - 2)//2
        status = "EMPTY" if blen == 0 else f"{blen}B"
        if code.startswith("ERROR"):
            status = code
        elif blen > 0:
            nonempty += 1
        print(f"[{chain:9}] {project:28} {addr[:10]}... -> {status}")
        rows_out.append({
            "project": project, "source_url": src, "chain": chain,
            "address": addr, "bytecode_len": blen,
            "bytecode": code if blen > 0 else "",
        })
        time.sleep(args.sleep)

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["project","source_url","chain","address","bytecode_len","bytecode"])
        w.writeheader(); w.writerows(rows_out)

    print(f"\nwrote {len(rows_out)} rows ({nonempty} with non-empty bytecode) -> {args.out}")
    print("\nNEXT: audit each non-empty row's provenance (does source_url actually")
    print("name this address as its 7702 delegate?), then run the SAME PUSH-skeleton +")
    print("D3 clustering on this benign set so benign families are counted the same way")
    print("as malicious ones. You want benign family count >> a handful, or reviewers")
    print("will say the negative class is too narrow.")

if __name__ == "__main__":
    main()
