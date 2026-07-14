#!/usr/bin/env python3
"""
ind_01_inventory_getcode.py -- T1 inventory + T2 on-chain code classification.

READ-ONLY. Only eth_getCode (+ block tag 'latest'). Every HTTP request logged to
network_query_log.csv. No state-changing calls.

Outputs:
  reports/inventory.json          T1 counts (per file, union, dedup, cross-file overlap)
  reports/getcode_mainnet.csv     per-address: has_code, code_len, is_7702_designator, delegate_target
  network_query_log.csv           append-only request log
"""
import os, sys, json, re, time, urllib.request, urllib.error
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLDIR = os.path.join(ROOT, "scamsonethereum-main")
FILES = ["master_blacklist_set.txt", "all_across_hard.txt"]
LOG = os.path.join(ROOT, "network_query_log.csv")
RPCS = {
    "ethereum": ["https://ethereum-rpc.publicnode.com", "https://cloudflare-eth.com",
                 "https://rpc.ankr.com/eth"],
}
ADDR_RE = re.compile(r"0x[0-9a-fA-F]{40}")
BATCH = 50
UA = "Mozilla/5.0 (AuthGuard-7702 research; read-only eth_getCode; contact polboy777@gmail.com)"


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(endpoint, method, n, status, note):
    new = not os.path.exists(LOG)
    with open(LOG, "a") as f:
        if new:
            f.write("utc,endpoint,method,n_items,http_status,note\n")
        f.write(f"{now()},{endpoint},{method},{n},{status},{note}\n")


def rpc_batch(endpoint, calls):
    """calls: list of (id, method, params). Returns dict id->result or raises."""
    payload = json.dumps([{"jsonrpc": "2.0", "id": i, "method": m, "params": p}
                          for (i, m, p) in calls]).encode()
    req = urllib.request.Request(endpoint, data=payload,
                                 headers={"Content-Type": "application/json", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        status = resp.status
        data = json.loads(resp.read().decode())
    out = {}
    if isinstance(data, dict):  # single error object
        raise RuntimeError(f"non-batch response: {str(data)[:200]}")
    for item in data:
        if "result" in item:
            out[item["id"]] = item["result"]
        else:
            out[item["id"]] = None
    return out, status


def load_inventory():
    per_file = {}
    for fn in FILES:
        lines = [l.strip() for l in open(os.path.join(BLDIR, fn)) if l.strip()]
        valid = [l.lower() for l in lines if ADDR_RE.fullmatch(l)]
        per_file[fn] = dict(lines=len(lines), valid=len(valid),
                            malformed=len(lines) - len(valid),
                            unique=len(set(valid)), addrs=set(valid))
    a, b = per_file[FILES[0]]["addrs"], per_file[FILES[1]]["addrs"]
    union = a | b
    inv = dict(
        per_file={k: {kk: vv for kk, vv in v.items() if kk != "addrs"} for k, v in per_file.items()},
        cross_file_overlap=len(a & b),
        union_unique=len(union),
        note="No chain/label/source metadata present in either file; both are bare address "
             "lists. File mtime 2023-12-05 predates EIP-7702 mainnet activation (Pectra, 2025). "
             "Blacklist membership alone is NOT evidence of malicious EIP-7702 delegate usage.",
    )
    with open(os.path.join(ROOT, "reports", "inventory.json"), "w") as f:
        json.dump(inv, f, indent=2)
    return sorted(union), inv


def getcode_all(addrs):
    endpoints = RPCS["ethereum"]
    ep_i = 0
    results = {}
    i = 0
    while i < len(addrs):
        chunk = addrs[i:i + BATCH]
        calls = [(j, "eth_getCode", [chunk[j], "latest"]) for j in range(len(chunk))]
        ok = False
        for _try in range(len(endpoints)):
            ep = endpoints[(ep_i) % len(endpoints)]
            try:
                out, status = rpc_batch(ep, calls)
                for j, a in enumerate(chunk):
                    results[a] = out.get(j)
                log(ep, "eth_getCode", len(chunk), status, f"batch {i//BATCH}")
                ok = True
                break
            except Exception as e:
                log(ep, "eth_getCode", len(chunk), "ERR", f"batch {i//BATCH}: {type(e).__name__}")
                ep_i += 1
                time.sleep(1.0)
        if not ok:
            for a in chunk:
                results.setdefault(a, None)
        i += BATCH
        if (i // BATCH) % 10 == 0:
            print(f"  getcode {i}/{len(addrs)}", flush=True)
        time.sleep(0.15)
    return results


def main():
    addrs, inv = load_inventory()
    print("[T1] inventory:", json.dumps(inv["per_file"]), "union", inv["union_unique"], flush=True)
    print(f"[T2] eth_getCode on mainnet for {len(addrs)} unique addresses...", flush=True)
    codes = getcode_all(addrs)

    rows = []
    n_code = n_eoa = n_desig = n_fail = 0
    for a in addrs:
        c = codes.get(a)
        if c is None:
            n_fail += 1
            rows.append((a, "FETCH_FAIL", 0, 0, ""))
            continue
        c = c.lower()
        if c in ("0x", "0x0", ""):
            n_eoa += 1
            rows.append((a, "EOA_OR_EMPTY", 0, 0, ""))
        else:
            body = c[2:]
            is_desig = body.startswith("ef0100") and len(body) == 46
            target = ("0x" + body[6:46]) if is_desig else ""
            if is_desig:
                n_desig += 1
            n_code += 1
            rows.append((a, "DESIGNATOR_7702" if is_desig else "CONTRACT_CODE",
                        len(body) // 2, 1 if is_desig else 0, target))

    with open(os.path.join(ROOT, "reports", "getcode_mainnet.csv"), "w") as f:
        f.write("address,class,code_bytes,is_7702_designator,delegate_target\n")
        for r in rows:
            f.write(",".join(str(x) for x in r) + "\n")

    summary = dict(unique=len(addrs), with_contract_code=n_code, eoa_or_empty=n_eoa,
                   is_7702_designator=n_desig, fetch_fail=n_fail)
    with open(os.path.join(ROOT, "reports", "getcode_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print("[T2] mainnet classification:", json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
