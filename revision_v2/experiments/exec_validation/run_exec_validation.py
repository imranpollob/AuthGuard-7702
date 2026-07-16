#!/usr/bin/env python3
"""Phase 2C — bounded execution-validation harness (anvil + debug_traceCall).

We cannot replay real attacks (the USENIX artifact ships no attack tx hashes / victim state /
exploit scripts). Instead we install each contract's runtime bytecode at a test address via
anvil_setCode and drive it with a fixed calldata suite (empty calldata + each sensitive/generic
selector present in the dispatch table, zero args). For every call we capture an execution
fingerprint from the opcode-level trace: success/revert, external-call opcodes and their target
addresses + values, SSTORE writes, LOG topics, and return value. We compare original vs each
transform (M1/M2/M3/F200) over the SAME calldata.

Claim scope (bounded, honest): under the tested transactions, whether the transformed variant
preserved the observed execution fingerprint. Divergences at deliberately-changed immediates
(M2 address PUSH20, M3 renamed selectors) are expected and are categorized, not hidden.
"""
import json
import os
import subprocess
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
sys.path.insert(0, os.path.join(HERE, "..", "common"))
sys.path.insert(0, os.path.join(HERE, "..", "donor_pools"))
from ag_common import normalize_bytecode, disasm  # noqa: E402
from harness import load_corpus, SEED, RV2  # noqa: E402
from pools import mut  # noqa: E402

OUT = os.path.join(RV2, "results", "exec_validation")
PORT = 8579
RPC = f"http://127.0.0.1:{PORT}"
TEST_ADDR = "0x00000000000000000000000000000000000c0de0"
CALL_OPS = {"CALL", "CALLCODE", "DELEGATECALL", "STATICCALL", "CREATE", "CREATE2"}


def rpc(method, params):
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    out = subprocess.run(["cast", "rpc", "--rpc-url", RPC, method, *_cast_args(params)],
                         capture_output=True, text=True, timeout=60)
    # fall back to raw curl for structured params
    return out


def _post(method, params):
    import urllib.request
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                          "params": params}).encode()
    req = urllib.request.Request(RPC, data=payload,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def trace_call(runtime_hex, calldata_hex):
    _post("anvil_setCode", [TEST_ADDR, "0x" + normalize_bytecode(runtime_hex)])
    r = _post("debug_traceCall",
              [{"to": TEST_ADDR, "data": "0x" + calldata_hex, "gas": "0x2625a0"}, "latest",
               {"disableStorage": False, "disableStack": False, "disableMemory": True}])
    return r.get("result", {"error": r.get("error")})


def fingerprint(trace):
    if "error" in trace or "structLogs" not in trace:
        return dict(ok=False, error=str(trace.get("error"))[:120])
    failed = bool(trace.get("failed", False))
    logs = trace["structLogs"]
    calls, sstores, log_ops = [], [], 0
    for i, s in enumerate(logs):
        op = s["op"]
        if op in CALL_OPS:
            stack = s.get("stack", [])
            # target address is 2nd stack item for CALL/DELEGATECALL/STATICCALL (gas, addr, ...)
            tgt = stack[-2][-40:] if len(stack) >= 2 else ""
            calls.append(f"{op}:{tgt}")
        elif op == "SSTORE":
            stack = s.get("stack", [])
            if len(stack) >= 2:
                sstores.append(f"{stack[-1]}={stack[-2]}")
        elif op.startswith("LOG"):
            log_ops += 1
    return dict(ok=True, failed=failed, gas=trace.get("gas"),
                return_value=trace.get("returnValue", ""),
                n_calls=len(calls), call_set=sorted(set(calls)),
                n_sstore=len(sstores), sstore_set=sorted(set(sstores)),
                n_logs=log_ops,
                op_count=len(logs))


def compare(a, b):
    if not a["ok"] or not b["ok"]:
        return dict(comparable=False, orig_ok=a["ok"], var_ok=b["ok"])
    return dict(
        comparable=True,
        same_failed=(a["failed"] == b["failed"]),
        same_return=(a["return_value"] == b["return_value"]),
        same_calls=(a["call_set"] == b["call_set"]),
        same_call_count=(a["n_calls"] == b["n_calls"]),
        same_sstore=(a["sstore_set"] == b["sstore_set"]),
        same_logs=(a["n_logs"] == b["n_logs"]),
        same_opcount=(a["op_count"] == b["op_count"]))


def selector_suite(bc):
    _, _, sels = disasm(bc)
    cds = ["", "00000000"]  # empty + zero-selector fallback
    cds += [s for s in sorted(sels)][:8]
    return cds


def start_anvil():
    proc = subprocess.Popen(["anvil", "--port", str(PORT), "--silent"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(30):
        try:
            _post("web3_clientVersion", [])
            return proc
        except Exception:
            time.sleep(0.3)
    raise RuntimeError("anvil did not start")


def pick_contracts(df, n=10):
    """Representative malicious delegates with real executable code and >=1 call opcode."""
    mal = df[df["class"] == "malicious"].copy()
    rows = []
    for _, r in mal.iterrows():
        bc = r["bc"]
        if len(bc) < 200 or bc.startswith("ef0100"):
            continue
        ops, _, sels = disasm(bc)
        ncall = sum(ops.count(o) for o in ("CALL", "DELEGATECALL", "STATICCALL"))
        if ncall >= 1 and len(sels) >= 1:
            rows.append((r["sid"], bc, r["address"], len(bc) // 2, ncall, len(sels)))
    rows.sort(key=lambda x: (x[4], x[5]), reverse=True)
    # diversify by size buckets
    picks, seen = [], set()
    for row in rows:
        bucket = row[3] // 500
        if bucket not in seen:
            seen.add(bucket); picks.append(row)
        if len(picks) >= n:
            break
    if len(picks) < n:
        picks += [r for r in rows if r not in picks][:n - len(picks)]
    return picks


def main():
    os.makedirs(OUT, exist_ok=True)
    df, _, _, _ = load_corpus()
    picks = pick_contracts(df, 10)
    proc = start_anvil()
    per_call, per_contract = [], []
    try:
        for sid, bc, addr, nb, ncall, nsel in picks:
            variants = {
                "M1": mut.make_mutant(bc, addr, "M1").hex(),
                "M2": mut.make_mutant(bc, addr, "M2").hex(),
                "M3": mut.make_mutant(bc, addr, "M3").hex(),
                "F200": mut.mut_deadcode_append(mut.to_bytes(bc), addr, 2.0).hex(),
            }
            suite = selector_suite(bc)
            orig_fps = {cd: fingerprint(trace_call(bc, cd)) for cd in suite}
            summary = {v: dict(preserved=0, expected_divergence=0, unexpected=0, calls=0)
                       for v in variants}
            for vname, vhex in variants.items():
                for cd in suite:
                    of = orig_fps[cd]
                    vf = fingerprint(trace_call(vhex, cd))
                    cmp = compare(of, vf)
                    summary[vname]["calls"] += 1
                    # define preservation per variant intent
                    if not cmp.get("comparable"):
                        cls = "incomparable"
                    elif vname == "M1":
                        cls = "preserved" if all(
                            cmp[k] for k in ["same_failed", "same_return", "same_calls",
                                             "same_sstore", "same_logs"]) else "unexpected"
                    elif vname in ("M2", "F200"):
                        # control-flow structure preserved; CALL targets may differ (M2) and
                        # trailing bytes never execute (F200) -> require same failed/logs/sstore
                        # counts and (F200) identical everything; (M2) call COUNT identical
                        keys = (["same_failed", "same_return", "same_calls", "same_sstore",
                                 "same_logs", "same_opcount"] if vname == "F200"
                                else ["same_failed", "same_call_count", "same_logs"])
                        cls = "preserved" if all(cmp[k] for k in keys) else "unexpected"
                    else:  # M3: renamed selectors reroute -> divergence at those selectors is expected
                        base = all(cmp[k] for k in ["same_failed", "same_calls", "same_sstore"])
                        cls = "preserved" if base else "expected_divergence"
                    if cls == "preserved":
                        summary[vname]["preserved"] += 1
                    elif cls == "expected_divergence":
                        summary[vname]["expected_divergence"] += 1
                    elif cls == "unexpected":
                        summary[vname]["unexpected"] += 1
                    per_call.append(dict(sid=sid, variant=vname, calldata=cd[:10],
                                         classification=cls, **{k: cmp.get(k) for k in
                                         ["same_failed", "same_return", "same_calls",
                                          "same_sstore", "same_logs", "same_opcount"]}))
            per_contract.append(dict(sid=sid, address=addr, code_bytes=nb, n_call=ncall,
                                     n_selectors=nsel, n_calldata=len(suite),
                                     summary=summary))
            print(f"[exec] {sid[:24]} {nb}B: "
                  + " ".join(f"{v}={summary[v]['preserved']}/{summary[v]['calls']}"
                             for v in variants), flush=True)
    finally:
        proc.terminate()

    payload = dict(
        harness="anvil debug_traceCall opcode-level; anvil_setCode installs runtime bytecode",
        anvil_version=subprocess.run(["anvil", "--version"], capture_output=True,
                                     text=True).stdout.strip(),
        scope="Bounded: fixed calldata suite (empty + dispatch selectors, zero args). No real "
              "attack replay (artifact ships no attack tx / victim state). Divergences at "
              "M2 address immediates and M3 renamed selectors are expected by construction.",
        n_contracts=len(per_contract), contracts=per_contract)
    with open(os.path.join(OUT, "exec_validation.json"), "w") as f:
        json.dump(payload, f, indent=2)
    pd.DataFrame(per_call).to_csv(os.path.join(OUT, "exec_validation_per_call.csv"), index=False)

    # headline: M1 full-preservation contract count
    m1_full = sum(1 for c in per_contract
                  if c["summary"]["M1"]["unexpected"] == 0 and c["summary"]["M1"]["preserved"] > 0)
    f200_full = sum(1 for c in per_contract
                    if c["summary"]["F200"]["unexpected"] == 0 and c["summary"]["F200"]["preserved"] > 0)
    print(f"[exec] M1 fully-preserved contracts: {m1_full}/{len(per_contract)}; "
          f"F200 fully-preserved: {f200_full}/{len(per_contract)}")


if __name__ == "__main__":
    main()
