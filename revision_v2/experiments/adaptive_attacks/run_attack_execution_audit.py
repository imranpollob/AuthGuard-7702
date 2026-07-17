#!/usr/bin/env python3
"""Bounded execution-fingerprint audit for selected adaptive attack candidates."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))
sys.path.insert(0, os.path.join(HERE, "..", "exec_validation"))
from harness import load_corpus, verify_frozen_or_die, sha256_file, RV2, SEED, disasm  # noqa: E402
from run_exec_validation import fingerprint, compare  # noqa: E402

OUT = os.path.join(RV2, "results", "adaptive_attacks")
PORT = 8583
RPC = f"http://127.0.0.1:{PORT}"
TEST_ADDR = "0x00000000000000000000000000000000000c0de3"
METHODS = ["M1", "M2", "M3", "F200", "random_flood_best", "fixed_oracle_best",
           "random_search", "beam_search"]


def post(method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                       "params": params}).encode()
    request = urllib.request.Request(RPC, data=body,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode())


def trace(runtime_hex, calldata):
    post("anvil_setCode", [TEST_ADDR, "0x" + runtime_hex])
    response = post("debug_traceCall",
                    [{"to": TEST_ADDR, "data": "0x" + calldata, "gas": "0x2625a0"},
                     "latest", {"disableStorage": False, "disableStack": False,
                                "disableMemory": True}])
    return response.get("result", {"error": response.get("error")})


def start_anvil():
    process = subprocess.Popen(["anvil", "--port", str(PORT), "--silent"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(40):
        try:
            post("web3_clientVersion", [])
            return process
        except Exception:
            time.sleep(0.25)
    process.terminate()
    raise RuntimeError("anvil did not start")


def selector_suite(bytecode):
    _, _, selectors = disasm(bytecode)
    return ["", "00000000", *sorted(selectors)[:8]]


def equivalent(comparison):
    keys = ["same_failed", "same_return", "same_calls", "same_call_count",
            "same_sstore", "same_logs"]
    return bool(comparison.get("comparable") and all(comparison.get(key) for key in keys))


def preservation_oriented(sequence):
    lowered = str(sequence).lower()
    intent_changing = ("address" in lowered or "selector" in lowered or
                       lowered in {"m2", "m3"} or
                       "selected:m2" in lowered or "selected:m3" in lowered)
    return not intent_changing


def update_manifest(paths):
    manifest_path = os.path.join(OUT, "manifest.json")
    manifest = json.load(open(manifest_path))
    manifest.setdefault("config", {})["bounded_execution_validation"] = \
        "ten prior delegates, fixed 100-call suite"
    for path in paths:
        key = os.path.relpath(path, os.path.dirname(os.path.dirname(OUT)))
        # Existing manifests use repository-relative keys beginning revision_v2/.
        if not key.startswith("revision_v2/"):
            key = os.path.relpath(path, os.path.abspath(os.path.join(OUT, "..", "..", "..")))
        manifest["outputs"][key] = sha256_file(path)
    with open(manifest_path, "w") as handle:
        json.dump(manifest, handle, indent=2)


def main():
    verify_frozen_or_die()
    attacks_path = os.path.join(OUT, "attack_per_row.csv.gz")
    previous_path = os.path.join(RV2, "results", "exec_validation", "exec_validation.json")
    attacks = pd.read_csv(attacks_path)
    previous = json.load(open(previous_path))
    selected_sids = [item["sid"] for item in previous["contracts"]]
    df, _, _, _ = load_corpus()
    source = df.set_index("sid")
    candidates = attacks[attacks["method"].isin(METHODS)].set_index(["sid", "method"])
    assert all((sid, method) in candidates.index for sid in selected_sids for method in METHODS)

    rows = []
    process = start_anvil()
    try:
        for sid in selected_sids:
            original = source.loc[sid, "bc"]
            suite = selector_suite(original)
            original_traces = {calldata: trace(original, calldata) for calldata in suite}
            for method in METHODS:
                candidate = candidates.loc[(sid, method)]
                sequence = candidate["sequence"]
                for calldata in suite:
                    original_fp = fingerprint(original_traces[calldata])
                    candidate_fp = fingerprint(trace(candidate["candidate_hex"], calldata))
                    comparison = compare(original_fp, candidate_fp)
                    rows.append(dict(
                        sid=sid, method=method, sequence=sequence,
                        preservation_oriented=preservation_oriented(sequence),
                        calldata=calldata[:10], comparable=bool(comparison.get("comparable")),
                        behavior_equivalent=equivalent(comparison),
                        structural_valid=bool(candidate["structural_valid"]),
                        byte_overhead=float(candidate["byte_overhead"]),
                        **{key: comparison.get(key) for key in
                           ["same_failed", "same_return", "same_calls", "same_call_count",
                            "same_sstore", "same_logs", "same_opcount"]}))
            print(f"[attack-exec] {sid}: {len(suite)} calls x {len(METHODS)} methods", flush=True)
    finally:
        process.terminate(); process.wait(timeout=10)

    per_call = pd.DataFrame(rows)
    per_call_path = os.path.join(OUT, "execution_audit_per_call.csv")
    per_call.to_csv(per_call_path, index=False)
    summary = {}
    for method, group in per_call.groupby("method"):
        contracts = group.groupby("sid")["behavior_equivalent"].all()
        oriented = group[group["preservation_oriented"]]
        summary[method] = dict(
            calls=int(len(group)), comparable_calls=int(group["comparable"].sum()),
            equivalent_calls=int(group["behavior_equivalent"].sum()),
            execution_preservation_rate=float(group["behavior_equivalent"].mean()),
            all_calls_preserved_contracts=int(contracts.sum()), contracts=int(len(contracts)),
            preservation_oriented_calls=int(len(oriented)),
            preservation_oriented_rate=(float(oriented["behavior_equivalent"].mean())
                                        if len(oriented) else None))
    payload = dict(
        seed=SEED,
        scope="Ten previously selected delegates; empty/zero-selector plus up to eight PUSH4 "
              "selectors with zero arguments. Raw bounded fingerprint preservation, not formal "
              "semantic equivalence. Address/selector actions are intentionally reported without "
              "assuming preservation.",
        contracts=len(selected_sids), methods=METHODS,
        source_calls=int(per_call[["sid", "calldata"]].drop_duplicates().shape[0]),
        summary=summary)
    results_path = os.path.join(OUT, "execution_audit.json")
    with open(results_path, "w") as handle:
        json.dump(payload, handle, indent=2)

    aggregate_path = os.path.join(OUT, "adaptive_attack_results.json")
    aggregate = json.load(open(aggregate_path))
    aggregate["bounded_execution_validation"] = payload
    with open(aggregate_path, "w") as handle:
        json.dump(aggregate, handle, indent=2)
    update_manifest([aggregate_path, results_path, per_call_path])
    verify_frozen_or_die()
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
