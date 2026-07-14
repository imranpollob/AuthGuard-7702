#!/usr/bin/env python3
"""
ind_02_retry_failures.py -- retry the FETCH_FAIL addresses from ind_01 with patient pacing,
so the designator/target census is complete (2,150 unfetched = 27% would bias the funnel).
Updates reports/getcode_mainnet.csv in place; appends to network_query_log.csv.
"""
import os, sys, json, csv, time, urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(ROOT, "reports", "getcode_mainnet.csv")
LOG = os.path.join(ROOT, "network_query_log.csv")
UA = "Mozilla/5.0 (AuthGuard-7702 research; read-only eth_getCode; contact polboy777@gmail.com)"
ENDPOINTS = ["https://ethereum-rpc.publicnode.com", "https://rpc.ankr.com/eth",
             "https://eth.llamarpc.com", "https://ethereum.blockpi.network/v1/rpc/public"]
BATCH = 20


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def log(ep, n, status, note):
    with open(LOG, "a") as f:
        f.write(f"{now()},{ep},eth_getCode,{n},{status},{note}\n")

def rpc_batch(ep, chunk):
    calls = [{"jsonrpc": "2.0", "id": j, "method": "eth_getCode", "params": [a, "latest"]}
             for j, a in enumerate(chunk)]
    req = urllib.request.Request(ep, data=json.dumps(calls).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        data = json.loads(r.read().decode()); status = r.status
    if not isinstance(data, list):
        raise RuntimeError("nonlist")
    out = {}
    for item in data:
        out[item["id"]] = item.get("result")
    if len(out) != len(chunk):
        raise RuntimeError("partial")
    return out, status


def classify(code):
    if code is None:
        return None
    code = code.lower()
    if code in ("0x", "0x0", ""):
        return ("EOA_OR_EMPTY", 0, 0, "")
    body = code[2:]
    if body.startswith("ef0100") and len(body) == 46:
        return ("DESIGNATOR_7702", 23, 1, "0x" + body[6:46])
    return ("CONTRACT_CODE", len(body) // 2, 0, "")


def main():
    rows = list(csv.DictReader(open(CSV)))
    fails = [r["address"] for r in rows if r["class"] == "FETCH_FAIL"]
    print(f"[retry] {len(fails)} fetch-fails to retry", flush=True)
    idx = {r["address"]: r for r in rows}
    ep_i = 0
    i = 0
    recovered = 0
    while i < len(fails):
        chunk = fails[i:i + BATCH]
        ok = False
        for _ in range(len(ENDPOINTS)):
            ep = ENDPOINTS[ep_i % len(ENDPOINTS)]
            try:
                out, status = rpc_batch(ep, chunk)
                for j, a in enumerate(chunk):
                    c = classify(out.get(j))
                    if c is not None:
                        idx[a].update(dict(zip(["class", "code_bytes", "is_7702_designator",
                                                "delegate_target"], [c[0], c[1], c[2], c[3]])))
                        recovered += 1
                log(ep, len(chunk), status, f"retry {i//BATCH}")
                ok = True
                break
            except Exception as e:
                log(ep, len(chunk), "ERR", f"retry {i//BATCH}:{type(e).__name__}")
                ep_i += 1
                time.sleep(1.5)
        i += BATCH
        if (i // BATCH) % 20 == 0:
            print(f"  retry {i}/{len(fails)} recovered={recovered}", flush=True)
        time.sleep(0.35)

    with open(CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["address", "class", "code_bytes",
                                          "is_7702_designator", "delegate_target"])
        w.writeheader()
        for r in rows:
            w.writerow(r)

    from collections import Counter
    cnt = Counter(r["class"] for r in rows)
    print("[retry] final classification:", dict(cnt), flush=True)
    with open(os.path.join(ROOT, "reports", "getcode_summary.json"), "w") as f:
        json.dump(dict(unique=len(rows), with_contract_code=cnt.get("CONTRACT_CODE", 0),
                       eoa_or_empty=cnt.get("EOA_OR_EMPTY", 0),
                       is_7702_designator=cnt.get("DESIGNATOR_7702", 0),
                       fetch_fail=cnt.get("FETCH_FAIL", 0)), f, indent=2)


if __name__ == "__main__":
    main()
