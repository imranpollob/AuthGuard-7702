#!/usr/bin/env python3
"""
ind_03_targets_overlap.py -- fetch delegate-target bytecodes and compute T4 overlap vs USENIX-793.

For each unique delegate target D (delegate-usage verified on-chain via ind_01/02):
  * fetch runtime bytecode (eth_getCode) + sha256
  * exact overlap: sha256 == any USENIX-793
  * family overlap: max MinHash-Jaccard sim to any USENIX-793 malicious >= 0.85 (frozen threshold)
  * record delegate-usage evidence (blacklisted accounts pointing to D)
Outputs reports/independent_targets.csv (the pre-model candidate table).
"""
import os, sys, json, csv, hashlib, urllib.request
import numpy as np
import pandas as pd
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ag_common import normalize_bytecode, disasm, minhash_signature

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "network_query_log.csv")
UA = "AuthGuard-7702 anonymous research audit (read-only eth_getCode)"
EP = "https://ethereum-rpc.publicnode.com"


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def getcode(addr):
    calls = {"jsonrpc": "2.0", "id": 1, "method": "eth_getCode", "params": [addr, "latest"]}
    req = urllib.request.Request(EP, data=json.dumps(calls).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        code = json.loads(r.read().decode())["result"]
    with open(LOG, "a") as f:
        f.write(f"{now()},{EP},eth_getCode,1,200,target {addr}\n")
    return code


def main():
    rows = list(csv.DictReader(open(os.path.join(ROOT, "reports", "getcode_mainnet.csv"))))
    # delegate-usage evidence: which blacklisted accounts point to each target
    from collections import defaultdict
    evid = defaultdict(list)
    for r in rows:
        if r["is_7702_designator"] == "1" and r["delegate_target"]:
            evid[r["delegate_target"].lower()].append(r["address"])
    targets = sorted(evid.keys())
    print(f"[T4] {len(targets)} unique delegate targets", flush=True)

    # USENIX-793 malicious signatures + hashes
    df = pd.read_csv(os.path.join(ROOT, "capability_dataset.csv"))
    df["al"] = df["address"].str.lower()
    mal = df[df["class"] == "malicious"].copy()
    mal["bc"] = mal["bytecode"].map(normalize_bytecode)
    mal["h"] = mal["bc"].map(lambda b: hashlib.sha256(b.encode()).hexdigest())
    mal_hashes = set(mal["h"])
    mal_addr = set(mal["al"])
    ds_addr = set(df["al"])
    print("[T4] computing 793 malicious MinHash signatures...", flush=True)
    mal_sigs = np.stack([minhash_signature(disasm(b)[0]) for b in mal["bc"].values])

    out = []
    for t in targets:
        code = getcode(t)
        bc = normalize_bytecode(code)
        h = hashlib.sha256(bc.encode()).hexdigest()
        if bc and bc not in ("", "0x"):
            sig = minhash_signature(disasm(bc)[0])
            sims = (mal_sigs == sig).mean(axis=1)
            max_sim = float(sims.max())
            nn_idx = int(sims.argmax())
            nn_addr = mal.iloc[nn_idx]["al"]
        else:
            max_sim = 0.0; nn_addr = ""
        in_793 = t in mal_addr
        in_ds = t in ds_addr
        exact = h in mal_hashes
        if in_793 or exact:
            subset = "exact_known"
        elif max_sim >= 0.85:
            subset = "known_family"
        elif max_sim >= 0.80:
            subset = "uncertain_family_boundary"
        else:
            subset = "truly_novel"
        out.append(dict(
            target=t, n_delegating_blacklisted=len(evid[t]), code_bytes=len(bc)//2,
            bytecode_sha256=h, in_usenix_793=in_793, in_usenix_dataset=in_ds,
            exact_overlap=exact, max_minhash_sim_to_793=round(max_sim, 3),
            nearest_793=nn_addr, novelty_subset=subset,
            usage_evidence_example=evid[t][0]))
        print(f"  {t} n={len(evid[t])} bytes={len(bc)//2} sim={max_sim:.3f} -> {subset}", flush=True)

    cols = ["target", "n_delegating_blacklisted", "code_bytes", "bytecode_sha256",
            "in_usenix_793", "in_usenix_dataset", "exact_overlap",
            "max_minhash_sim_to_793", "nearest_793", "novelty_subset", "usage_evidence_example"]
    with open(os.path.join(ROOT, "reports", "independent_targets.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
        for r in out:
            w.writerow(r)

    from collections import Counter
    print("[T4] novelty subsets:", dict(Counter(r["novelty_subset"] for r in out)), flush=True)


if __name__ == "__main__":
    main()
