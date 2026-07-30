"""Enrichment stage: takes a raw authorizations CSV (from collector.py), deduplicates
delegate addresses, retrieves runtime bytecode, computes exact-hash and opcode-4-gram
similarity against the frozen historical population (revision_v2's canonical benchmark),
and classifies each new delegate as an exact historical duplicate, a member of an existing
similarity family (Jaccard >= 0.85 against a family representative, matching the canonical
project's frozen threshold), or a previously unseen family.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "revision_v3", "src"))

from features.disassembler import normalize_hex, to_bytes  # noqa: E402
from features.hashing import opcode_kgrams  # noqa: E402
from features.disassembler import linear_sweep  # noqa: E402
from temporal.rpc_client import ChainClient, RpcError  # noqa: E402

FAMILY_SIMILARITY_THRESHOLD = 0.85


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def build_historical_family_representatives() -> dict:
    """One representative bytecode's opcode-4-gram set per historical family_id (first row
    per family, deterministic)."""
    v2_path = os.path.join(REPO_ROOT, "revision_v2", "data", "authguardbench_7702_v2.csv.gz")
    v2 = pd.read_csv(v2_path)
    v2 = v2.sort_values("sample_id")
    reps = v2.groupby("family_id").first().reset_index()
    family_grams = {}
    hash_to_family = {}
    exact_hashes = set(v2["bytecode_sha256"])
    for _, row in reps.iterrows():
        tokens, _, _ = linear_sweep(normalize_hex(row["runtime_bytecode"]))
        family_grams[row["family_id"]] = opcode_kgrams(tokens, k=4)
    for _, row in v2.iterrows():
        hash_to_family[row["bytecode_sha256"]] = row["family_id"]
    return {"family_grams": family_grams, "exact_hashes": exact_hashes, "hash_to_family": hash_to_family}


def enrich_authorizations(raw_csv_path: str, chain: str, out_csv_path: str,
                           max_delegates: int | None = None) -> pd.DataFrame:
    raw = pd.read_csv(raw_csv_path)
    unique_delegates = raw["delegate_address"].dropna().str.lower().unique()
    if max_delegates is not None:
        unique_delegates = unique_delegates[:max_delegates]

    historical = build_historical_family_representatives()
    client = ChainClient(chain)

    rows = []
    for address in unique_delegates:
        try:
            code_hex = client.get_code(address)
        except RpcError as e:
            rows.append({"address": address, "chain": chain, "fetch_error": str(e)})
            continue
        h = normalize_hex(code_hex)
        code_bytes = to_bytes(h)
        bytecode_sha256 = hashlib.sha256(code_bytes).hexdigest()
        tokens, _, _ = linear_sweep(h)
        grams = opcode_kgrams(tokens, k=4)

        is_exact_historical_duplicate = bytecode_sha256 in historical["exact_hashes"]
        matched_family = historical["hash_to_family"].get(bytecode_sha256)
        best_sim, best_family = 0.0, None
        if not is_exact_historical_duplicate:
            for fam_id, fam_grams in historical["family_grams"].items():
                sim = jaccard(grams, fam_grams)
                if sim > best_sim:
                    best_sim, best_family = sim, fam_id
        is_family_match = is_exact_historical_duplicate or best_sim >= FAMILY_SIMILARITY_THRESHOLD
        if is_exact_historical_duplicate:
            resolved_family = matched_family
        elif best_sim >= FAMILY_SIMILARITY_THRESHOLD:
            resolved_family = best_family
        else:
            resolved_family = None  # previously unseen family

        rows.append({
            "address": address, "chain": chain,
            "code_bytes": len(code_bytes), "opcode_count": len(tokens),
            "bytecode_sha256": bytecode_sha256,
            "is_exact_historical_duplicate": is_exact_historical_duplicate,
            "best_family_similarity": round(best_sim, 4),
            "matched_historical_family": resolved_family,
            "is_previously_unseen_family": resolved_family is None,
            "fetch_error": None,
        })

    df = pd.DataFrame(rows)
    df.to_csv(out_csv_path, index=False)
    return df


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("raw_csv")
    p.add_argument("chain")
    p.add_argument("out_csv")
    p.add_argument("--max-delegates", type=int, default=None)
    args = p.parse_args()
    result = enrich_authorizations(args.raw_csv, args.chain, args.out_csv, args.max_delegates)
    print(json.dumps({
        "n_delegates": len(result),
        "n_exact_historical_duplicates": int(result.get("is_exact_historical_duplicate", pd.Series(dtype=bool)).sum()),
        "n_previously_unseen_families": int(result.get("is_previously_unseen_family", pd.Series(dtype=bool)).sum()),
        "n_fetch_errors": int(result["fetch_error"].notna().sum()) if "fetch_error" in result else 0,
    }, indent=2))
