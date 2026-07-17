#!/usr/bin/env python3
"""Bounded dynamic reachability/behavior audit for first-STOP and canonical forms."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "common"))
sys.path.insert(0, os.path.join(HERE, "..", "exec_validation"))
from canonicalizer import analyze_bytecode  # noqa: E402
from harness import load_corpus, verify_frozen_or_die, write_manifest, RV2, SEED, disasm  # noqa: E402
from run_exec_validation import fingerprint, compare  # noqa: E402

OUT = os.path.join(RV2, "results", "first_stop_audit")
PORT = 8581
RPC = f"http://127.0.0.1:{PORT}"
TEST_ADDR = "0x00000000000000000000000000000000000c0de1"


def post(method, params):
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                          "params": params}).encode()
    req = urllib.request.Request(RPC, data=payload,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.loads(response.read().decode())


def trace(runtime_hex, calldata_hex):
    post("anvil_setCode", [TEST_ADDR, "0x" + runtime_hex])
    response = post("debug_traceCall",
                    [{"to": TEST_ADDR, "data": "0x" + calldata_hex, "gas": "0x2625a0"},
                     "latest", {"disableStorage": False, "disableStack": False,
                                "disableMemory": True}])
    return response.get("result", {"error": response.get("error")})


def start_anvil():
    proc = subprocess.Popen(["anvil", "--port", str(PORT), "--silent"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(40):
        try:
            post("web3_clientVersion", [])
            return proc
        except Exception:
            time.sleep(0.25)
    proc.terminate()
    raise RuntimeError("anvil did not start")


def selector_suite(bytecode):
    _, _, selectors = disasm(bytecode)
    return ["", "00000000", *sorted(selectors)[:8]]


def behavior_equivalent(comparison):
    keys = ["same_failed", "same_return", "same_calls", "same_call_count",
            "same_sstore", "same_logs"]
    return bool(comparison.get("comparable") and all(comparison.get(k) for k in keys))


def executed_pcs(raw_trace):
    return {int(row["pc"]) for row in raw_trace.get("structLogs", []) if "pc" in row}


def in_ranges(pc, ranges):
    return any(r["start"] <= pc < r["end"] for r in ranges
               if r["reason"] == "cfg_unreachable")


def main():
    started = time.time()
    verify_frozen_or_die()
    os.makedirs(OUT, exist_ok=True)
    previous_path = os.path.join(RV2, "results", "exec_validation", "exec_validation.json")
    previous = json.load(open(previous_path))
    selected = [row["sid"] for row in previous["contracts"]]
    df, _, _, _ = load_corpus()
    lookup = df.set_index("sid")
    missing = sorted(set(selected) - set(lookup.index))
    assert not missing, f"execution-validation rows missing: {missing}"

    rows = []
    proc = start_anvil()
    try:
        for sid in selected:
            bytecode = lookup.loc[sid, "bc"]
            audit = analyze_bytecode(bytecode)
            analysis = audit["analysis"]
            meta_start = analysis["executable_bytes"]
            original_bytes = bytes.fromhex(audit["normalized_hex"])
            masked_with_metadata = (bytes.fromhex(audit["reachable_masked_hex"]) +
                                    original_bytes[meta_start:]).hex()
            variants = {
                "metadata_stripped": audit["metadata_stripped_hex"],
                "first_stop": audit["first_stop_hex"],
                "reachable_masked_preserve_metadata": masked_with_metadata,
                "reachable_compact": audit["reachable_compact_hex"],
            }
            removed_ranges = analysis["removed_ranges"]
            first_stop_pc = analysis["first_stop_pc"]
            for calldata in selector_suite(bytecode):
                original_trace = trace(audit["normalized_hex"], calldata)
                original_fp = fingerprint(original_trace)
                pcs = executed_pcs(original_trace)
                post_stop_executed = bool(first_stop_pc is not None and
                                          any(pc > first_stop_pc for pc in pcs))
                removed_pc_executed = any(in_ranges(pc, removed_ranges) for pc in pcs)
                for name, variant in variants.items():
                    variant_trace = trace(variant, calldata)
                    cmp = compare(original_fp, fingerprint(variant_trace))
                    rows.append(dict(
                        sid=sid, calldata=calldata[:10], representation=name,
                        comparable=bool(cmp.get("comparable")),
                        behavior_equivalent=behavior_equivalent(cmp),
                        post_first_stop_pc_executed=post_stop_executed,
                        statically_reachable_after_first_stop=bool(
                            analysis["cfg_reachable_after_first_stop"]),
                        removed_cfg_pc_executed=removed_pc_executed,
                        first_stop_pc=first_stop_pc,
                        original_trace_steps=len(original_trace.get("structLogs", [])),
                        variant_trace_steps=len(variant_trace.get("structLogs", [])),
                        **{k: cmp.get(k) for k in ["same_failed", "same_return", "same_calls",
                                                   "same_call_count", "same_sstore",
                                                   "same_logs", "same_opcount"]}))
            print(f"[execution-audit] {sid}: {len(selector_suite(bytecode))} calls", flush=True)
    finally:
        proc.terminate()
        proc.wait(timeout=10)

    per_call = pd.DataFrame(rows)
    per_call_path = os.path.join(OUT, "execution_audit_per_call.csv")
    per_call.to_csv(per_call_path, index=False)
    summary = {}
    for name, group in per_call.groupby("representation"):
        by_contract = group.groupby("sid")["behavior_equivalent"].all()
        summary[name] = dict(
            calls=int(len(group)), comparable_calls=int(group["comparable"].sum()),
            equivalent_calls=int(group["behavior_equivalent"].sum()),
            execution_validation_rate=float(group["behavior_equivalent"].mean()),
            all_calls_equivalent_contracts=int(by_contract.sum()),
            contracts=int(len(by_contract)))
    payload = dict(
        seed=SEED,
        scope="Ten previously selected delegates; empty/zero-selector plus up to eight PUSH4 "
              "selectors with zero arguments. Bounded trace evidence, not formal equivalence.",
        contracts=len(selected),
        calls=int(per_call[["sid", "calldata"]].drop_duplicates().shape[0]),
        contracts_with_static_post_first_stop_reachability=int(
            per_call.groupby("sid")["statically_reachable_after_first_stop"].first().sum()),
        contracts_with_observed_post_first_stop_execution=int(
            per_call.groupby("sid")["post_first_stop_pc_executed"].any().sum()),
        calls_executing_post_first_stop=int(
            per_call.groupby(["sid", "calldata"])["post_first_stop_pc_executed"].first().sum()),
        calls_executing_cfg_removed_pc=int(
            per_call.groupby(["sid", "calldata"])["removed_cfg_pc_executed"].first().sum()),
        representations=summary)
    out_path = os.path.join(OUT, "execution_audit.json")
    with open(out_path, "w") as handle:
        json.dump(payload, handle, indent=2)
    write_manifest(OUT, dict(protocol="first_stop_audit_protocol", seed=SEED,
                             component="bounded_execution_audit"),
                   [out_path, per_call_path], started, inputs=[previous_path])
    os.replace(os.path.join(OUT, "manifest.json"),
               os.path.join(OUT, "execution_manifest.json"))
    verify_frozen_or_die()
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
