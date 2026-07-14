#!/usr/bin/env python3
"""
ind_04_maliciousness.py -- T3 independent-maliciousness triage for the 9 delegate targets.

Independent of the USENIX rule. Gathers, per target:
  * structural read of the delegate bytecode (sweeper-like vs full-account-like): code size,
    external-call opcodes, SELFDESTRUCT, whether it is a minimal forwarder, selector count.
  * on-chain behavioral evidence from the delegating (victim) accounts: balance (swept->~0),
    nonce (observed activity/execution). Many independent accounts converging on one tiny
    forwarder delegate = shared-sweeper signature.
NOTE: we deliberately do NOT use "external-call-from-fallback" as the malicious criterion
(that is the USENIX rule; using it would be circular). Structure is descriptive; the
maliciousness call combines manual code inspection + observed execution + victim convergence.
"""
import os, sys, json, csv, urllib.request
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ag_common import normalize_bytecode, disasm

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "network_query_log.csv")
UA = "Mozilla/5.0 (AuthGuard-7702 research; read-only; contact polboy777@gmail.com)"
EP = "https://ethereum-rpc.publicnode.com"

def now(): return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def rpc(method, params):
    req = urllib.request.Request(EP, data=json.dumps(
        {"jsonrpc":"2.0","id":1,"method":method,"params":params}).encode(),
        headers={"Content-Type":"application/json","User-Agent":UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        d = json.loads(r.read().decode())
    with open(LOG,"a") as f: f.write(f"{now()},{EP},{method},1,200,{params[0]}\n")
    return d.get("result")

def struct(bc):
    ops,_,sel = disasm(bc)
    return dict(code_bytes=len(bc)//2, n_ops=len(ops), n_selectors=len(sel),
        n_call=ops.count("CALL"), n_delegatecall=ops.count("DELEGATECALL"),
        n_staticcall=ops.count("STATICCALL"), n_selfdestruct=ops.count("SELFDESTRUCT"),
        n_create=ops.count("CREATE")+ops.count("CREATE2"),
        has_ext_call=any(o in ops for o in ("CALL","CALLCODE","DELEGATECALL")))

def main():
    tgt_rows = list(csv.DictReader(open(os.path.join(ROOT,"reports","independent_targets.csv"))))
    gc = list(csv.DictReader(open(os.path.join(ROOT,"reports","getcode_mainnet.csv"))))
    from collections import defaultdict
    victims = defaultdict(list)
    for r in gc:
        if r["is_7702_designator"]=="1" and r["delegate_target"]:
            victims[r["delegate_target"].lower()].append(r["address"])

    out=[]
    for tr in tgt_rows:
        t=tr["target"]
        code = rpc("eth_getCode",[t,"latest"]) or "0x"
        s = struct(normalize_bytecode(code))
        # victim behavioral evidence: sample up to 8 delegating accounts
        vs = victims[t][:8]
        vinfo=[]
        for v in vs:
            bal = rpc("eth_getBalance",[v,"latest"]) or "0x0"
            nonce = rpc("eth_getTransactionCount",[v,"latest"]) or "0x0"
            vinfo.append((v, int(bal,16), int(nonce,16)))
        n_active = sum(1 for _,_,nc in vinfo if nc>0)
        near_zero_bal = sum(1 for _,b,_ in vinfo if b < 10**15)  # <0.001 ETH
        out.append(dict(target=t, novelty_subset=tr["novelty_subset"],
            n_delegating=int(tr["n_delegating_blacklisted"]),
            max_sim_793=tr["max_minhash_sim_to_793"], **s,
            victims_sampled=len(vinfo), victims_active_nonce=n_active,
            victims_near_zero_balance=near_zero_bal,
            in_usenix_dataset=tr["in_usenix_dataset"], in_usenix_793=tr["in_usenix_793"]))
        print(f"{t} {tr['novelty_subset']:12s} bytes={s['code_bytes']:5d} extcall={s['has_ext_call']} "
              f"selfdestruct={s['n_selfdestruct']} victims={len(vinfo)} active={n_active} "
              f"zerobal={near_zero_bal}", flush=True)

    with open(os.path.join(ROOT,"reports","target_maliciousness.json"),"w") as f:
        json.dump(out,f,indent=2)

if __name__=="__main__":
    main()
