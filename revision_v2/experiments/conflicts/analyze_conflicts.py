#!/usr/bin/env python3
"""Phase 2A — dossiers and categorization for the 23 conflicting exact-bytecode groups.

Evidence sources (all repository-local unless --network):
  * paper_build/data_hygiene/conflicting_bytecodes.csv (frozen quarantine record)
  * capability_dataset.csv (bytecode by original_index; cap_* capability flags)
  * USENIX artifact eoa_detect/detect_result.jsonl (per-address rule-firing facts)
  * frozen disassembly (structural signals: proxy pattern, storage gating, selectors)
  * optional read-only eth_getCode per (chain,address) with a local cache

Categories (deterministic rules, confidence recorded; rules documented in output):
  likely_label_inconsistency | context_dependent_behavior | initialization_or_state_difference
  | external_dependency_difference | unresolved
Quarantined rows are NOT restored to the primary task.
"""
import argparse
import hashlib
import json
import os
import sys
import time
import urllib.request

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
from ag_common import normalize_bytecode, disasm  # noqa: E402
from ag_features import build_sensitive_selector_set  # noqa: E402

OUT = os.path.join(ROOT, "revision_v2", "results", "conflicts")
CACHE = os.path.join(OUT, "conflict_rpc_cache.json")
SENS = build_sensitive_selector_set()

RPCS = {
    "ethereum": "https://ethereum-rpc.publicnode.com",
    "base": "https://base-rpc.publicnode.com",
    "bnb": "https://bsc-rpc.publicnode.com",
    "polygon": "https://polygon-bor-rpc.publicnode.com",
    "arbitrum": "https://arbitrum-one-rpc.publicnode.com",
    "optimism": "https://optimism-rpc.publicnode.com",
    "gnosis": "https://gnosis-rpc.publicnode.com",
}
OWNER_SELECTOR = "8da5cb5b"  # owner()


def getcode(chain, address, cache):
    key = f"{chain}:{address.lower()}"
    if key in cache:
        return cache[key]
    url = RPCS.get(chain)
    if not url:
        cache[key] = {"status": "no_rpc_for_chain"}
        return cache[key]
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_getCode",
                          "params": [address, "latest"]}).encode()
    req = urllib.request.Request(url, data=payload, headers={
        "Content-Type": "application/json",
        "User-Agent": "AuthGuard-7702 revision audit (read-only eth_getCode)"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            code = json.loads(resp.read().decode()).get("result", "0x")
        cache[key] = {"status": "ok", "code_sha": hashlib.sha256(
            normalize_bytecode(code).encode()).hexdigest(),
            "code_bytes": len(normalize_bytecode(code)) // 2}
    except Exception as exc:  # noqa: BLE001
        cache[key] = {"status": f"error:{type(exc).__name__}"}
    time.sleep(0.12)
    return cache[key]


def structural_signals(bc):
    ops, pushes, sels = disasm(bc)
    n = len(ops)
    return dict(
        exec_or_total_bytes=len(bc) // 2,
        n_ops=n,
        has_delegatecall=("DELEGATECALL" in ops),
        n_call_family=sum(ops.count(o) for o in ("CALL", "STATICCALL", "DELEGATECALL", "CALLCODE")),
        has_sstore=("SSTORE" in ops),
        has_sload=("SLOAD" in ops),
        has_owner_selector=(OWNER_SELECTOR in sels),
        has_sensitive_selector=bool(set(sels) & SENS),
        n_selectors=len(sels),
        n_push20=sum(1 for s in pushes if s == 20),
        is_delegation_pointer=bc.startswith("ef0100") and len(bc) == 46,
        proxy_like=("DELEGATECALL" in ops and n < 400),
    )


def load_usenix_facts():
    facts = {}
    path = os.path.join(ROOT, "USENIX EIP-7702 artifact", "eoa_detect", "detect_result.jsonl")
    with open(path) as f:
        for line in f:
            line = line.strip().rstrip(",")
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            facts[row["address"].lower()] = row.get("result", [])
    return facts


def categorize(g, sig, facts_by_addr):
    """Deterministic rule cascade; returns (category, confidence, rationale)."""
    mal = g[g["class"] == "malicious"]
    neg = g[g["class"] != "malicious"]
    chains = set(g["chain"])
    mal_fact = [a for a in mal["address"].str.lower() if a in facts_by_addr]
    neg_fact = [a for a in neg["address"].str.lower() if a in facts_by_addr]

    if sig["is_delegation_pointer"] or sig["proxy_like"]:
        return ("external_dependency_difference", "medium",
                "bytecode is a delegation pointer or minimal DELEGATECALL proxy; observed "
                "behavior depends on an external implementation, so identical bytecode can "
                "act differently per deployment")
    if mal_fact and not neg_fact:
        conf = "high" if len(chains) == 1 else "medium"
        return ("likely_label_inconsistency", conf,
                f"USENIX rule-firing facts exist for {len(mal_fact)} malicious-labeled "
                f"address(es) but for none of the {len(neg)} rule-silent rows despite "
                "byte-identical code; the rule is bytecode-level, so the divergent verdict "
                "indicates pipeline coverage/label inconsistency"
                + ("" if len(chains) == 1 else " (cross-chain contexts noted)"))
    if sig["has_sstore"] and sig["has_sload"] and sig["has_owner_selector"] and len(g) > 2:
        return ("initialization_or_state_difference", "low",
                "storage-gated logic with an owner() interface; per-deployment "
                "initialization/ownership state could change observed behavior")
    if len(chains) > 1:
        return ("context_dependent_behavior", "low",
                "identical bytecode deployed across multiple chains with divergent labels; "
                "no repository evidence isolates the mechanism")
    return ("unresolved", "low", "no repository evidence distinguishes the labels")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--network", action="store_true")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    conf = pd.read_csv(os.path.join(ROOT, "paper_build", "data_hygiene",
                                    "conflicting_bytecodes.csv"))
    cap = pd.read_csv(os.path.join(ROOT, "capability_dataset.csv"))
    facts = load_usenix_facts()
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}

    groups_out, dossier_rows = [], []
    for h, g in conf.groupby("normalized_bytecode_sha256"):
        bc = normalize_bytecode(cap.loc[g["original_index"].iloc[0], "bytecode"])
        # recovered designator rows may differ from original CSV bytecode; recompute defensively
        if hashlib.sha256(bc.encode()).hexdigest() != h:
            match = None
            for oi in g["original_index"]:
                cand = normalize_bytecode(cap.loc[oi, "bytecode"])
                if hashlib.sha256(cand.encode()).hexdigest() == h:
                    match = cand
                    break
            bc = match if match is not None else bc
        sig = structural_signals(bc)
        onchain = {}
        if args.network:
            for _, r in g.drop_duplicates(["chain", "address"]).iterrows():
                onchain[f"{r['chain']}:{r['address']}"] = getcode(r["chain"], r["address"], cache)
        cat, confd, why = categorize(g, sig, facts)
        rec = dict(
            normalized_bytecode_sha256=h,
            rows=len(g),
            classes=sorted(g["class"].unique()),
            class_counts=g["class"].value_counts().to_dict(),
            chains=sorted(g["chain"].unique()),
            n_distinct_addresses=g["address"].str.lower().nunique(),
            family_ids=sorted(g["family_id"].unique()),
            conflict_stage=sorted(g["conflict_stage"].unique()),
            frozen_assessment=sorted(g["evidence_assessment"].unique()),
            usenix_fact_addresses_malicious=[a for a in g[g["class"] == "malicious"]
                                             ["address"].str.lower() if a in facts],
            usenix_fact_addresses_negative=[a for a in g[g["class"] != "malicious"]
                                            ["address"].str.lower() if a in facts],
            structural_signals=sig,
            onchain_getcode=onchain,
            category=cat, confidence=confd, rationale=why,
            decision="remain_quarantined (bytecode-only primary task cannot separate labels)",
        )
        groups_out.append(rec)
        for _, r in g.iterrows():
            dossier_rows.append(dict(
                normalized_bytecode_sha256=h, address=r["address"], chain=r["chain"],
                label=r["class"], family_id=r["family_id"],
                label_provenance=r["label_provenance"], category=cat, confidence=confd))

    if args.network:
        with open(CACHE, "w") as f:
            json.dump(cache, f, indent=2, sort_keys=True)

    cats = pd.Series([g["category"] for g in groups_out]).value_counts().to_dict()
    report = dict(
        n_groups=len(groups_out), n_rows=int(len(conf)), category_counts=cats,
        rule_cascade=["delegation-pointer/proxy -> external_dependency_difference",
                      "USENIX facts fire for malicious rows only -> likely_label_inconsistency",
                      "storage-gated owner() logic -> initialization_or_state_difference",
                      "multi-chain, no mechanism evidence -> context_dependent_behavior",
                      "else unresolved"],
        note="Quarantine is preserved; no row is restored to the primary task.",
        groups=groups_out)
    with open(os.path.join(OUT, "conflict_report.json"), "w") as f:
        json.dump(report, f, indent=2)
    pd.DataFrame(dossier_rows).to_csv(os.path.join(OUT, "conflict_dossier_rows.csv"), index=False)

    lines = ["# Conflicting Exact-Bytecode Groups — Phase 2A Analysis", "",
             f"23 groups / {len(conf)} rows, all quarantined (decision preserved).", "",
             "| category | groups |", "|---|---:|"]
    for k, v in sorted(cats.items(), key=lambda kv: -kv[1]):
        lines.append(f"| {k} | {v} |")
    lines += ["", "| hash (12) | rows | classes | chains | category | confidence |", "|---|---:|---|---|---|---|"]
    for g in groups_out:
        lines.append(f"| {g['normalized_bytecode_sha256'][:12]} | {g['rows']} | "
                     f"{'/'.join(g['classes'])} | {len(g['chains'])} | {g['category']} | {g['confidence']} |")
    with open(os.path.join(OUT, "conflict_report.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print(json.dumps(cats, indent=1))
    print(f"[conflicts] wrote {OUT}")


if __name__ == "__main__":
    main()
