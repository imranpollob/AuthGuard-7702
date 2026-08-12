#!/usr/bin/env python3
"""Phase 2 — expanded execution-preservation audit, per transformation class.

Determines whether Tier B (flooding + metadata + neutral insertion) can be described as
an audit-supported action space, or only as partially audited.

Each transformation class is audited separately against a real EVM (anvil) using the
UNCHANGED fingerprint/compare definitions from the existing exec_validation harness, so
"preserved" means the same thing it did in the 100-call audit: same failure status, same
return data, same external-call set and count, same SSTORE set, same log count.

Address and selector rewrite are deliberately NOT audited into the preservation-supported
tier; their existing 23/100 result stands and they remain Tier C only.

Risk-relevant coverage is tracked explicitly: empty calldata exercises receive()/fallback(),
the zero selector exercises fallback(), and discovered PUSH4 selectors exercise named
entry points. Whether a given execution actually reached an external call or a storage
write is read off the original trace fingerprint.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
import urllib.request

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RV2 = os.path.abspath(os.path.join(HERE, "..", ".."))
ROOT = os.path.abspath(os.path.join(RV2, ".."))
OUT = os.path.join(RV2, "results", "sprint_phase2")
PORT = 8599
RPC = f"http://127.0.0.1:{PORT}"
TEST_ADDR = "0x00000000000000000000000000000000000c0de7"

sys.path.insert(0, os.path.join(RV2, "experiments", "adaptive_attacks_v2"))
sys.path.insert(0, os.path.join(RV2, "experiments", "exec_validation"))
sys.path.insert(0, os.path.join(RV2, "experiments", "common"))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


runner = _load("run_adaptive_attacks_v2", os.path.join(
    RV2, "experiments", "adaptive_attacks_v2", "run_adaptive_attacks_v2.py"))
execval = _load("run_exec_validation", os.path.join(
    RV2, "experiments", "exec_validation", "run_exec_validation.py"))
from ag_common import disasm, normalize_bytecode  # noqa: E402

fingerprint, compare = execval.fingerprint, execval.compare

CLASSES = {
    "flooding": ["flood25", "flood50", "flood100", "flood200"],
    "metadata_rewrite": ["metadata"],
    "neutral_insertion": ["neutral25"],
}


def post(method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                       "params": params}).encode()
    request = urllib.request.Request(RPC, data=body,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=90) as response:
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
    for _ in range(60):
        try:
            post("web3_clientVersion", [])
            return process
        except Exception:
            time.sleep(0.25)
    process.terminate()
    raise RuntimeError("anvil did not start")


def selector_suite(bytecode, max_selectors=8):
    _, _, selectors = disasm(bytecode)
    return ["", "00000000", *sorted(selectors)[:max_selectors]]


def entry_class(calldata):
    if calldata == "":
        return "empty_calldata_receive_or_fallback"
    if calldata == "00000000":
        return "zero_selector_fallback"
    return "discovered_selector"


def wilson(k, n, z=1.96):
    if not n:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return (max(0.0, c - h), min(1.0, c + h))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-delegates", type=int, default=60)
    parser.add_argument("--max-selectors", type=int, default=8)
    parser.add_argument("--fold", type=int, default=0)
    args = parser.parse_args()
    started = time.time()
    if runner.verify_frozen() != 0:
        raise RuntimeError("frozen-artifact verification failed")
    os.makedirs(OUT, exist_ok=True)

    bench, frame = runner.load_primary()
    pools = runner.build_pools(bench)
    positives = frame[frame.label == 1].copy()
    # One delegate per family, spread across families, so the sample is family-diverse.
    picked = (positives.sort_values("sample_id")
              .groupby("family_id", as_index=False).first())
    if len(picked) > args.n_delegates:
        step = np.linspace(0, len(picked) - 1, args.n_delegates).round().astype(int)
        picked = picked.iloc[np.unique(step)]
    print(f"[phase2] {len(picked)} delegates across {picked.family_id.nunique()} families",
          flush=True)

    rows = []
    process = start_anvil()
    try:
        for count, (_, src) in enumerate(picked.iterrows()):
            original = normalize_bytecode(src["runtime_bytecode"])
            suite = selector_suite(original, args.max_selectors)
            row = dict(sid=src["sample_id"], family_id=src["family_id"],
                       address=src["address"], chain=src["chain"],
                       bytecode=src["runtime_bytecode"], y=1)
            base = {cd: fingerprint(trace(original, cd)) for cd in suite}
            for cls, actions in CLASSES.items():
                for action in actions:
                    ctx = runner.AttackContext(pools, row, args.fold)
                    variant = ctx.apply_sequence((action,))
                    if variant is None:
                        rows.append(dict(sid=row["sid"], family_id=row["family_id"],
                                         transformation_class=cls, action=action,
                                         calldata="*", entry_class="*",
                                         comparable=False, behavior_equivalent=False,
                                         failure_reason="candidate_failed_validity"))
                        continue
                    for cd in suite:
                        original_fp = base[cd]
                        variant_fp = fingerprint(trace(variant, cd))
                        cmp = compare(original_fp, variant_fp)
                        equivalent = bool(cmp.get("comparable") and all(
                            cmp.get(k) for k in ("same_failed", "same_return", "same_calls",
                                                 "same_call_count", "same_sstore",
                                                 "same_logs")))
                        rows.append(dict(
                            sid=row["sid"], family_id=row["family_id"],
                            transformation_class=cls, action=action,
                            calldata=cd[:10], entry_class=entry_class(cd),
                            comparable=bool(cmp.get("comparable")),
                            behavior_equivalent=equivalent,
                            original_reached_external_call=bool(
                                original_fp.get("ok") and original_fp.get("n_calls", 0) > 0),
                            original_reached_sstore=bool(
                                original_fp.get("ok") and original_fp.get("n_sstore", 0) > 0),
                            original_failed=(original_fp.get("failed")
                                             if original_fp.get("ok") else None),
                            byte_overhead=ctx.overhead(variant),
                            **{k: cmp.get(k) for k in
                               ("same_failed", "same_return", "same_calls",
                                "same_call_count", "same_sstore", "same_logs",
                                "same_opcount")}))
            if (count + 1) % 10 == 0:
                print(f"[phase2] {count + 1}/{len(picked)} delegates "
                      f"({time.time() - started:.0f}s)", flush=True)
    finally:
        process.terminate()
        process.wait(timeout=15)

    per_call = pd.DataFrame(rows)
    per_call.to_csv(os.path.join(OUT, "preservation_per_call.csv.gz"),
                    index=False, compression="gzip")

    summary = {}
    for cls, group in per_call.groupby("transformation_class"):
        valid = group[group.calldata != "*"]
        k = int(valid.behavior_equivalent.sum())
        n = int(len(valid))
        lo, hi = wilson(k, n)
        # failure taxonomy: which comparison component broke
        failures = valid[~valid.behavior_equivalent]
        taxonomy = {}
        for key in ("same_failed", "same_return", "same_calls", "same_call_count",
                    "same_sstore", "same_logs"):
            taxonomy[key + "_violated"] = int((failures[key] == False).sum())  # noqa: E712
        taxonomy["not_comparable"] = int((~failures.comparable).sum())
        coverage = valid.entry_class.value_counts().to_dict()
        risk = dict(
            calls_where_original_reached_external_call=int(
                valid.original_reached_external_call.sum()),
            calls_where_original_reached_sstore=int(valid.original_reached_sstore.sum()))
        summary[cls] = dict(
            delegates_tested=int(valid.sid.nunique()),
            distinct_families=int(valid.family_id.nunique()),
            calls_tested=n, preserved_calls=k, failed_calls=n - k,
            preservation_rate=k / n if n else float("nan"),
            wilson95=[lo, hi],
            failure_taxonomy=taxonomy,
            entry_class_coverage=coverage,
            risk_relevant_execution=risk,
            candidate_construction_failures=int((group.calldata == "*").sum()))
        print(f"\n{cls}: {k}/{n} preserved = {k / n if n else float('nan'):.4f} "
              f"[{lo:.4f},{hi:.4f}]  delegates={summary[cls]['delegates_tested']} "
              f"families={summary[cls]['distinct_families']}")
        print(f"   entry coverage: {coverage}")
        print(f"   risk-relevant: {risk}")
        if n - k:
            print(f"   failure taxonomy: {taxonomy}")

    payload = dict(
        phase="2 expanded execution-preservation audit",
        script="revision_v2/experiments/sprint_phase2/expanded_preservation_audit.py",
        git_commit=subprocess.run(["git", "rev-parse", "HEAD"], cwd=RV2,
                                  capture_output=True, text=True).stdout.strip(),
        provenance="regenerated_experiment",
        equivalence_definition=("same_failed AND same_return AND same_calls AND "
                                "same_call_count AND same_sstore AND same_logs, "
                                "imported unchanged from exec_validation"),
        scope_note=("Bounded empirical execution preservation over the tested calldata "
                    "suite. Entry coverage includes empty calldata (receive/fallback) and "
                    "the zero selector (fallback); it does not prove preservation of the "
                    "reference risk condition itself."),
        excluded_from_preservation_tier=["address rewrite", "selector rewrite"],
        wall_seconds=time.time() - started, summary=summary)
    with open(os.path.join(OUT, "preservation_audit.json"), "w") as fh:
        json.dump(payload, fh, indent=2, default=str)
    if runner.verify_frozen() != 0:
        raise RuntimeError("frozen-artifact verification failed after run")
    print(f"\n[phase2] done in {time.time() - started:.0f}s -> {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
