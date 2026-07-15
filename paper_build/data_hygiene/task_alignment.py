#!/usr/bin/env python3
"""Build the frozen AuthGuard-7702 task-alignment audits and v1 manifest.

This script never edits the original dataset or family artifacts. Network access, when
requested, is read-only eth_getCode and is cached under paper_build/data_hygiene.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import urllib.error
import urllib.request

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "paper_build", "data_hygiene")
DATA = os.path.join(ROOT, "capability_dataset.csv")
FAMILIES = os.path.join(ROOT, "family_assignment_frozen.csv")
CACHE = os.path.join(OUT, "designator_rpc_cache.json")

RPCS = {
    "ethereum": "https://ethereum-rpc.publicnode.com",
    "base": "https://base-rpc.publicnode.com",
    "bnb": "https://bsc-rpc.publicnode.com",
    "polygon": "https://polygon-bor-rpc.publicnode.com",
    "arbitrum": "https://arbitrum-one-rpc.publicnode.com",
    "optimism": "https://optimism-rpc.publicnode.com",
    "gnosis": "https://gnosis-rpc.publicnode.com",
}


def norm(raw: object) -> str:
    h = str(raw).lower().strip()
    if h.startswith("0x"):
        h = h[2:]
    return h[:-1] if len(h) % 2 else h


def sha(h: str) -> str:
    return hashlib.sha256(h.encode()).hexdigest()


def is_designator(h: str) -> bool:
    return len(h) == 46 and h.startswith("ef0100") and all(c in "0123456789abcdef" for c in h)


def rpc_getcode(chain: str, address: str) -> dict:
    url = RPCS[chain]
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_getCode",
                          "params": [address, "latest"]}).encode()
    req = urllib.request.Request(url, data=payload, headers={
        "Content-Type": "application/json",
        "User-Agent": "AuthGuard-7702 anonymous research audit (read-only eth_getCode)",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            obj = json.loads(resp.read().decode())
        code = obj.get("result", "0x")
        if not isinstance(code, str):
            code = "0x"
        return {"status": "ok", "code": code, "endpoint": url}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"status": f"error:{type(exc).__name__}", "code": "", "endpoint": url}


def original_fold_map(df: pd.DataFrame, classes: list[str]) -> dict[str, int]:
    sub = df[df["class"].isin(classes)].reset_index(drop=True)
    y = (sub["class"] == "malicious").astype(int).to_numpy()
    groups = sub["family_id"].to_numpy()
    out: dict[str, int] = {}
    for fold, (_, test) in enumerate(GroupKFold(5).split(sub, y, groups)):
        for family in np.unique(groups[test]):
            if family in out and out[family] != fold:
                raise AssertionError("family assigned to multiple outer folds")
            out[family] = fold
    return out


def label_provenance(label: str) -> str:
    return {
        "malicious": "USENIX eoa_detect artifact positive",
        "benign_cleared": "USENIX rule-silent weak negative",
        "benign_general": "general-contract benign-source subset",
        "benign_AA": "hand-verified account-abstraction control",
    }[label]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--network", action="store_true", help="read-only eth_getCode for targets")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    df = pd.read_csv(DATA)
    fam = pd.read_csv(FAMILIES)
    keys = ["address", "chain", "class"]
    if not df[keys].reset_index(drop=True).equals(fam[keys].reset_index(drop=True)):
        raise AssertionError("frozen family file is not row-aligned")
    df = df.copy()
    df["original_index"] = np.arange(len(df))
    df["family_id"] = fam["family_id"].to_numpy()
    df["_norm"] = df["bytecode"].map(norm)
    df["_hash"] = df["_norm"].map(sha)
    df["_addr"] = df["address"].str.lower()

    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    designator_idx = df.index[df["_norm"].map(is_designator)].tolist()
    target_keys = sorted({f"{df.at[i, 'chain']}:{'0x' + df.at[i, '_norm'][6:46]}"
                          for i in designator_idx})
    if args.network:
        for pos, key in enumerate(target_keys, 1):
            if key in cache and cache[key].get("status") == "ok":
                continue
            chain, target = key.split(":", 1)
            cache[key] = rpc_getcode(chain, target)
            print(f"[rpc {pos}/{len(target_keys)}] {key} -> {cache[key]['status']} "
                  f"{len(norm(cache[key].get('code', ''))) // 2}B", flush=True)
            time.sleep(0.15)
        with open(CACHE, "w") as f:
            json.dump(cache, f, indent=2, sort_keys=True)

    designator_rows = []
    recovered_by_index: dict[int, str] = {}
    designator_exclusions: dict[int, str] = {}
    for i in designator_idx:
        row = df.loc[i]
        target = "0x" + row["_norm"][6:46]
        matches = df[(df["chain"] == row["chain"]) & (df["_addr"] == target)]
        runtime_mask = ~matches["_norm"].map(is_designator) & matches["_norm"].str.len().gt(0)
        runtime_matches = matches.loc[runtime_mask]
        local_codes = sorted(runtime_matches["_norm"].unique())
        key = f"{row['chain']}:{target}"
        rpc = cache.get(key, {})
        rpc_norm = norm(rpc.get("code", ""))
        rpc_kind = ("runtime" if rpc_norm and not is_designator(rpc_norm)
                    else "designator" if is_designator(rpc_norm)
                    else "empty" if rpc.get("status") == "ok" else "unavailable")

        chosen = ""
        source = ""
        if len(local_codes) == 1:
            chosen, source = local_codes[0], "repository_dataset_target_row"
        elif len(local_codes) > 1:
            source = "repository_target_runtime_conflict"
        elif rpc_kind == "runtime":
            chosen, source = rpc_norm, "read_only_rpc_target_runtime"

        elsewhere = df[df["_hash"] == sha(chosen)] if chosen else df.iloc[0:0]
        other_families = sorted(set(elsewhere["family_id"]) - {row["family_id"]})
        if chosen and not other_families:
            decision = "replace_and_retain_candidate"
            recovered_by_index[i] = chosen
        elif chosen:
            decision = "exclude_recovered_cross_family_exact_duplicate"
            designator_exclusions[i] = decision
        else:
            decision = "exclude_unresolved_no_verified_runtime"
            designator_exclusions[i] = decision

        designator_rows.append({
            "original_index": i,
            "chain": row["chain"],
            "address": row["address"],
            "class": row["class"],
            "family_id": row["family_id"],
            "designator_target_address": target,
            "row_represents": ("delegating_account_self_target" if row["_addr"] == target
                               else "delegating_account"),
            "target_runtime_in_repository": bool(local_codes),
            "repository_target_row_count": len(matches),
            "repository_runtime_row_count": len(runtime_matches),
            "target_runtime_appears_elsewhere_in_dataset": bool(len(elsewhere)),
            "target_runtime_elsewhere_row_count": len(elsewhere),
            "target_runtime_elsewhere_families": ";".join(sorted(set(elsewhere["family_id"]))),
            "read_only_rpc_status": rpc.get("status", "not_queried"),
            "read_only_rpc_kind": rpc_kind,
            "runtime_recovery_source": source or "none",
            "recovered_runtime_sha256": sha(chosen) if chosen else "",
            "recovered_runtime_bytes": len(chosen) // 2 if chosen else 0,
            "task_alignment_decision": decision,
        })

    da = pd.DataFrame(designator_rows)
    da.to_csv(os.path.join(OUT, "designator_audit.csv"), index=False)

    # Candidate bytecode after permitted designator recovery, before conflict quarantine.
    candidate = df.copy()
    for i, h in recovered_by_index.items():
        candidate.at[i, "bytecode"] = "0x" + h
        candidate.at[i, "_norm"] = h
        candidate.at[i, "_hash"] = sha(h)
    candidate = candidate.drop(index=list(designator_exclusions)).copy()

    # Freeze the specified policy: every exact hash carrying >1 class is quarantined in full.
    class_counts = candidate.groupby("_hash")["class"].nunique()
    conflict_hashes = set(class_counts[class_counts > 1].index)
    conflict = candidate[candidate["_hash"].isin(conflict_hashes)].copy()
    conflict_rows = []
    original_conflict_hashes = set(
        df.groupby("_hash")["class"].nunique().loc[lambda x: x > 1].index
    )
    for h, group in conflict.groupby("_hash"):
        classes = sorted(group["class"].unique())
        category = ("unresolved_binary_label_conflict" if "malicious" in classes and len(classes) > 1
                    else "contextual_negative_subset_overlap")
        contexts = group[["chain", "address"]].drop_duplicates().shape[0] > 1
        for _, row in group.iterrows():
            conflict_rows.append({
                "normalized_bytecode_sha256": h,
                "conflict_stage": ("original" if h in original_conflict_hashes
                                   else "induced_by_designator_runtime_recovery"),
                "original_index": int(row["original_index"]),
                "address": row["address"],
                "chain": row["chain"],
                "class": row["class"],
                "family_id": row["family_id"],
                "group_row_count": len(group),
                "all_addresses": ";".join(group["address"].astype(str)),
                "all_chains": ";".join(group["chain"].astype(str)),
                "all_classes": ";".join(classes),
                "all_family_ids": ";".join(sorted(group["family_id"].unique())),
                "label_provenance": label_provenance(row["class"]),
                "different_accounts_or_contexts": bool(contexts),
                "evidence_assessment": category,
                "decision": "quarantine_entire_exact_bytecode_group",
            })
    pd.DataFrame(conflict_rows).to_csv(os.path.join(OUT, "conflicting_bytecodes.csv"), index=False)

    retained = candidate[~candidate["_hash"].isin(conflict_hashes)].copy()
    primary_folds = original_fold_map(df, ["malicious", "benign_cleared"])
    secondary_folds = original_fold_map(df, ["malicious", "benign_cleared", "benign_general"])
    retained["outer_fold_primary"] = retained["family_id"].map(primary_folds).astype("Int64")
    retained["outer_fold_secondary"] = retained["family_id"].map(secondary_folds).astype("Int64")
    retained["task_alignment_action"] = retained["original_index"].map(
        lambda i: "recovered_designator_runtime" if i in recovered_by_index else "retained_original")
    retained["original_bytecode_sha256"] = retained["original_index"].map(df["_hash"])
    retained["task_bytecode_sha256"] = retained["_hash"]
    target_map = {r["original_index"]: r["designator_target_address"] for r in designator_rows}
    retained["delegate_target_address"] = retained["original_index"].map(target_map).fillna("")

    drop_internal = ["_norm", "_hash", "_addr"]
    retained.drop(columns=drop_internal).to_csv(
        os.path.join(OUT, "task_aligned_dataset_v1.csv"), index=False)

    # Machine-readable manifest summary used by the frozen runners and reports.
    fg = retained.groupby("family_id")
    fam_classes = fg["class"].agg(lambda x: set(x))
    mal = retained[retained["class"] == "malicious"]
    mal_sizes = mal.groupby("family_id").size()
    exact_sizes = retained.groupby("task_bytecode_sha256").size()
    summary = {
        "original_rows": len(df),
        "designator_rows": len(designator_idx),
        "designator_verified_runtime_recovered": int(da["recovered_runtime_sha256"].ne("").sum()),
        "designator_recovered_retained": int((retained["task_alignment_action"] == "recovered_designator_runtime").sum()),
        "designator_recovered_cross_family_duplicate_excluded": int(
            (da["task_alignment_decision"] == "exclude_recovered_cross_family_exact_duplicate").sum()),
        "designator_unresolved_excluded": int(
            (da["task_alignment_decision"] == "exclude_unresolved_no_verified_runtime").sum()),
        "conflicting_exact_hash_groups_original": len(original_conflict_hashes),
        "conflicting_exact_hash_groups_candidate": len(conflict_hashes),
        "quarantined_conflict_rows": len(conflict),
        "retained_rows": len(retained),
        "retained_class_counts": retained["class"].value_counts().to_dict(),
        "retained_class_balance_malicious_fraction_primary": float(
            (retained[retained["class"].isin(["malicious", "benign_cleared"])]["class"] == "malicious").mean()),
        "retained_families": int(retained["family_id"].nunique()),
        "malicious_bearing_families": int(mal["family_id"].nunique()),
        "malicious_member_singleton_families": int((mal_sizes == 1).sum()),
        "global_singleton_families": int((fg.size() == 1).sum()),
        "cross_class_families": int(sum(len(x) > 1 for x in fam_classes)),
        "exact_duplicate_hash_groups": int((exact_sizes > 1).sum()),
        "exact_duplicate_rows": int(exact_sizes[exact_sizes > 1].sum()),
        "cross_class_exact_hash_groups_after_cleaning": int(
            (retained.groupby("task_bytecode_sha256")["class"].nunique() > 1).sum()),
    }
    with open(os.path.join(OUT, "task_aligned_manifest_summary.json"), "w") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
