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
# SEED delegate implementations, verified against each project's official
# docs/GitHub (see source_url per row). Two of the ten nameable families were
# deliberately SKIPPED because no canonical, officially-deployed address could
# be confirmed:
#   - Safe (SafeEIP7702): Safe's own docs (docs.safe.global/advanced/eip-7702/7702-safe)
#     state the 7702 contracts are "experimental" and "not yet audited"; the
#     5afe/safe-eip7702 repo is a POC with no deployed address published.
#   - Ithaca/Odyssey "simple-7702": ithacaxyz/odyssey-examples's SimpleDelegateContract
#     is a `forge create` tutorial contract meant to be freshly deployed by
#     whoever runs the walkthrough (local anvil node) -- there is no persistent
#     official mainnet/testnet address to cite.
#
# For the rest, most of these implementations are deployed via a deterministic
# CREATE2 factory at the SAME address on every chain the project supports, so
# one address maps to several chain rows below -- but each (project, chain) row
# below is only included where the project's own source explicitly names that
# chain as supported/deployed.
# ---------------------------------------------------------------------------
SEED_DELEGATES = [
    # project, source_url (official provenance), chain, address

    # MetaMask EIP7702StatelessDeleGatorImpl v1.3.0 -- CREATE2, same address on
    # every chain MetaMask lists as a deployment target.
    # Source: https://github.com/MetaMask/delegation-framework/blob/main/documents/Deployments.md
    ("MetaMask_EIP7702StatelessDeleGator", "https://github.com/MetaMask/delegation-framework/blob/main/documents/Deployments.md", "ethereum", "0x63c0c19a282a1B52b07dD5a65b58948A07DAE32B"),
    ("MetaMask_EIP7702StatelessDeleGator", "https://github.com/MetaMask/delegation-framework/blob/main/documents/Deployments.md", "base",     "0x63c0c19a282a1B52b07dD5a65b58948A07DAE32B"),
    ("MetaMask_EIP7702StatelessDeleGator", "https://github.com/MetaMask/delegation-framework/blob/main/documents/Deployments.md", "bnb",      "0x63c0c19a282a1B52b07dD5a65b58948A07DAE32B"),
    ("MetaMask_EIP7702StatelessDeleGator", "https://github.com/MetaMask/delegation-framework/blob/main/documents/Deployments.md", "polygon",  "0x63c0c19a282a1B52b07dD5a65b58948A07DAE32B"),
    ("MetaMask_EIP7702StatelessDeleGator", "https://github.com/MetaMask/delegation-framework/blob/main/documents/Deployments.md", "arbitrum", "0x63c0c19a282a1B52b07dD5a65b58948A07DAE32B"),
    ("MetaMask_EIP7702StatelessDeleGator", "https://github.com/MetaMask/delegation-framework/blob/main/documents/Deployments.md", "optimism", "0x63c0c19a282a1B52b07dD5a65b58948A07DAE32B"),
    ("MetaMask_EIP7702StatelessDeleGator", "https://github.com/MetaMask/delegation-framework/blob/main/documents/Deployments.md", "gnosis",   "0x63c0c19a282a1B52b07dD5a65b58948A07DAE32B"),

    # Ambire's own EIP_7702_AMBIRE_ACCOUNT constant. Only listing chains
    # explicitly named in Ambire's own sources (repo constant is chain-agnostic;
    # blog names Ethereum + BNB Chain as live).
    # Source: https://github.com/AmbireTech/ambire-common/blob/v2/src/consts/deploy.ts
    ("Ambire_EIP7702Account", "https://github.com/AmbireTech/ambire-common/blob/v2/src/consts/deploy.ts", "ethereum", "0x5A7FC11397E9a8AD41BF10bf13F22B0a63f96f6d"),
    ("Ambire_EIP7702Account", "https://github.com/AmbireTech/ambire-common/blob/v2/src/consts/deploy.ts", "bnb",      "0x5A7FC11397E9a8AD41BF10bf13F22B0a63f96f6d"),

    # ZeroDev Kernel v0.3.3 -- KERNEL_7702_DELEGATION_ADDRESS. Chains taken from
    # the SDK's own FAST_POLLING_CHAIN_IDS = [1, 10, 56, 137, 8453, 42161, 84532]
    # (84532 = Base Sepolia testnet, excluded here).
    # Source: https://github.com/zerodevapp/sdk/blob/main/packages/core/constants.ts
    ("ZeroDev_Kernel_v3.3_7702", "https://github.com/zerodevapp/sdk/blob/main/packages/core/constants.ts", "ethereum", "0xd6CEDDe84be40893d153Be9d467CD6aD37875b28"),
    ("ZeroDev_Kernel_v3.3_7702", "https://github.com/zerodevapp/sdk/blob/main/packages/core/constants.ts", "optimism", "0xd6CEDDe84be40893d153Be9d467CD6aD37875b28"),
    ("ZeroDev_Kernel_v3.3_7702", "https://github.com/zerodevapp/sdk/blob/main/packages/core/constants.ts", "bnb",      "0xd6CEDDe84be40893d153Be9d467CD6aD37875b28"),
    ("ZeroDev_Kernel_v3.3_7702", "https://github.com/zerodevapp/sdk/blob/main/packages/core/constants.ts", "polygon",  "0xd6CEDDe84be40893d153Be9d467CD6aD37875b28"),
    ("ZeroDev_Kernel_v3.3_7702", "https://github.com/zerodevapp/sdk/blob/main/packages/core/constants.ts", "base",     "0xd6CEDDe84be40893d153Be9d467CD6aD37875b28"),
    ("ZeroDev_Kernel_v3.3_7702", "https://github.com/zerodevapp/sdk/blob/main/packages/core/constants.ts", "arbitrum", "0xd6CEDDe84be40893d153Be9d467CD6aD37875b28"),

    # Biconomy Nexus Implementation v1.3.1, MEE Contracts Suite v2.2.1 (latest
    # at research time). Chains per docs.biconomy.io/contracts-and-audits/supported-chains.
    # Source: https://docs.biconomy.io/contracts-and-audits
    ("Biconomy_Nexus_v1.3.1", "https://docs.biconomy.io/contracts-and-audits", "ethereum", "0x0000000020fe2F30453074aD916eDeB653eC7E9D"),
    ("Biconomy_Nexus_v1.3.1", "https://docs.biconomy.io/contracts-and-audits", "base",     "0x0000000020fe2F30453074aD916eDeB653eC7E9D"),
    ("Biconomy_Nexus_v1.3.1", "https://docs.biconomy.io/contracts-and-audits", "polygon",  "0x0000000020fe2F30453074aD916eDeB653eC7E9D"),
    ("Biconomy_Nexus_v1.3.1", "https://docs.biconomy.io/contracts-and-audits", "arbitrum", "0x0000000020fe2F30453074aD916eDeB653eC7E9D"),
    ("Biconomy_Nexus_v1.3.1", "https://docs.biconomy.io/contracts-and-audits", "optimism", "0x0000000020fe2F30453074aD916eDeB653eC7E9D"),
    ("Biconomy_Nexus_v1.3.1", "https://docs.biconomy.io/contracts-and-audits", "bnb",      "0x0000000020fe2F30453074aD916eDeB653eC7E9D"),
    ("Biconomy_Nexus_v1.3.1", "https://docs.biconomy.io/contracts-and-audits", "gnosis",   "0x0000000020fe2F30453074aD916eDeB653eC7E9D"),

    # OKX Smart Wallet SmartWalletEntry (production implementation contract).
    # Chains per repo README: "Ethereum / X Layer / Base / Optimism / Arbitrum / BSC / Polygon".
    # Source: https://github.com/okxlabs/okx-smart-wallet-evm
    ("OKX_SmartWalletEntry", "https://github.com/okxlabs/okx-smart-wallet-evm", "ethereum", "0xe40ccB2D94975c51bff0C004eFDfd9B3a5796fA4"),
    ("OKX_SmartWalletEntry", "https://github.com/okxlabs/okx-smart-wallet-evm", "base",     "0xe40ccB2D94975c51bff0C004eFDfd9B3a5796fA4"),
    ("OKX_SmartWalletEntry", "https://github.com/okxlabs/okx-smart-wallet-evm", "optimism", "0xe40ccB2D94975c51bff0C004eFDfd9B3a5796fA4"),
    ("OKX_SmartWalletEntry", "https://github.com/okxlabs/okx-smart-wallet-evm", "arbitrum", "0xe40ccB2D94975c51bff0C004eFDfd9B3a5796fA4"),
    ("OKX_SmartWalletEntry", "https://github.com/okxlabs/okx-smart-wallet-evm", "bnb",      "0xe40ccB2D94975c51bff0C004eFDfd9B3a5796fA4"),
    ("OKX_SmartWalletEntry", "https://github.com/okxlabs/okx-smart-wallet-evm", "polygon",  "0xe40ccB2D94975c51bff0C004eFDfd9B3a5796fA4"),

    # Uniswap Calibur v1.1.0 (current mainnet version; supersedes the older
    # v1.0.0 address used only on Monad/Robinhood Chain, not in our chain set).
    # Source: https://developers.uniswap.org/docs/protocols/smart-wallet/deployments
    ("Uniswap_Calibur_v1.1.0", "https://developers.uniswap.org/docs/protocols/smart-wallet/deployments", "ethereum", "0x000000005c84F8Fd50b21CAC312528A64437030e"),
    ("Uniswap_Calibur_v1.1.0", "https://developers.uniswap.org/docs/protocols/smart-wallet/deployments", "base",     "0x000000005c84F8Fd50b21CAC312528A64437030e"),
    ("Uniswap_Calibur_v1.1.0", "https://developers.uniswap.org/docs/protocols/smart-wallet/deployments", "optimism", "0x000000005c84F8Fd50b21CAC312528A64437030e"),
    ("Uniswap_Calibur_v1.1.0", "https://developers.uniswap.org/docs/protocols/smart-wallet/deployments", "bnb",      "0x000000005c84F8Fd50b21CAC312528A64437030e"),
    ("Uniswap_Calibur_v1.1.0", "https://developers.uniswap.org/docs/protocols/smart-wallet/deployments", "arbitrum", "0x000000005c84F8Fd50b21CAC312528A64437030e"),

    # Alchemy SemiModularAccount7702 (Modular Account v2, EIP-7702 variant).
    # Docs state "same address across all EVM chains"; chains per
    # alchemy.com/docs/wallets/supported-chains (mainnets only, subset relevant here).
    # Source: https://www.alchemy.com/docs/wallets/smart-contracts/deployed-addresses
    ("Alchemy_SemiModularAccount7702", "https://www.alchemy.com/docs/wallets/smart-contracts/deployed-addresses", "ethereum", "0x69007702764179f14F51cdce752f4f775d74E139"),
    ("Alchemy_SemiModularAccount7702", "https://www.alchemy.com/docs/wallets/smart-contracts/deployed-addresses", "base",     "0x69007702764179f14F51cdce752f4f775d74E139"),
    ("Alchemy_SemiModularAccount7702", "https://www.alchemy.com/docs/wallets/smart-contracts/deployed-addresses", "bnb",      "0x69007702764179f14F51cdce752f4f775d74E139"),
    ("Alchemy_SemiModularAccount7702", "https://www.alchemy.com/docs/wallets/smart-contracts/deployed-addresses", "arbitrum", "0x69007702764179f14F51cdce752f4f775d74E139"),
    ("Alchemy_SemiModularAccount7702", "https://www.alchemy.com/docs/wallets/smart-contracts/deployed-addresses", "optimism", "0x69007702764179f14F51cdce752f4f775d74E139"),
    ("Alchemy_SemiModularAccount7702", "https://www.alchemy.com/docs/wallets/smart-contracts/deployed-addresses", "polygon",  "0x69007702764179f14F51cdce752f4f775d74E139"),

    # Coinbase Smart Wallet EIP7702Proxy. Chains per docs.base.org "Full Support"
    # list for Base Account (Zora/Avalanche excluded -- not in our chain set).
    # Source: https://github.com/base/eip-7702-proxy
    ("Coinbase_EIP7702Proxy", "https://github.com/base/eip-7702-proxy", "base",     "0x7702cb554e6bFb442cb743A7dF23154544a7176C"),
    ("Coinbase_EIP7702Proxy", "https://github.com/base/eip-7702-proxy", "arbitrum", "0x7702cb554e6bFb442cb743A7dF23154544a7176C"),
    ("Coinbase_EIP7702Proxy", "https://github.com/base/eip-7702-proxy", "optimism", "0x7702cb554e6bFb442cb743A7dF23154544a7176C"),
    ("Coinbase_EIP7702Proxy", "https://github.com/base/eip-7702-proxy", "polygon",  "0x7702cb554e6bFb442cb743A7dF23154544a7176C"),
    ("Coinbase_EIP7702Proxy", "https://github.com/base/eip-7702-proxy", "bnb",      "0x7702cb554e6bFb442cb743A7dF23154544a7176C"),
    ("Coinbase_EIP7702Proxy", "https://github.com/base/eip-7702-proxy", "ethereum", "0x7702cb554e6bFb442cb743A7dF23154544a7176C"),
]

def rpc_getcode(url, address, retries=3, timeout=20):
    payload = json.dumps({
        "jsonrpc": "2.0", "id": 1,
        "method": "eth_getCode", "params": [address, "latest"]
    }).encode()
    for attempt in range(retries):
        try:
            # Some public RPC endpoints sit behind Cloudflare bot-protection that
            # 403s urllib's default (absent) User-Agent; a browser-like UA clears it.
            req = urllib.request.Request(url, data=payload, headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
            })
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
