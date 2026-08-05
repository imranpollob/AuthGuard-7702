"""Build a frozen, resumable post-cutoff EIP-7702 candidate snapshot.

This stage does not assign security labels and does not score a model.  It aggregates the
already-collected authorization CSV, recovers the actual authorizing EOA from each delegate's
first observed authorization tuple, retrieves delegate code at that historical block and at
latest, and records overlap with canonical training families.  The result is candidate material
for independent review, not an external evaluation until family holds and labels are complete.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
V3 = os.path.join(REPO_ROOT, "revision_v3")
sys.path.insert(0, os.path.join(V3, "src"))

from features.disassembler import linear_sweep, normalize_hex, to_bytes  # noqa: E402
from features.hashing import opcode_kgrams  # noqa: E402
from temporal.authorization import recover_authority  # noqa: E402
from temporal.enrich import (  # noqa: E402
    FAMILY_SIMILARITY_THRESHOLD,
    jaccard,
)
from temporal.rpc_client import ChainClient, RpcError  # noqa: E402

RAW_PATH = os.path.join(V3, "temporal", "raw", "v2_window_ethereum_authorizations.csv")
CHECKPOINT_PATH = os.path.join(V3, "temporal", "checkpoints", "v2_window_ethereum.json")
RESULTS_DIR = os.path.join(V3, "results", "postcutoff_snapshot")
CACHE_PATH = os.path.join(RESULTS_DIR, "ethereum_authority_runtime_cache.jsonl")
SNAPSHOT_PATH = os.path.join(RESULTS_DIR, "ethereum_candidates.csv.gz")
REPORT_PATH = os.path.join(RESULTS_DIR, "ethereum_snapshot_report.json")
ZERO_ADDRESS = "0x" + "0" * 40


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _count_false(values: pd.Series) -> int:
    """Count false object-booleans without Python's integer bitwise inversion trap."""
    return int(values.eq(False).sum())  # noqa: E712


def aggregate_raw_authorizations(raw_path: str, chunksize: int = 200_000) -> tuple[pd.DataFrame, dict]:
    """Stream the large CSV and retain one provenance row plus counts per delegate."""
    aggregates: dict[str, dict] = {}
    n_rows = 0
    n_zero = 0
    columns = [
        "block_number", "block_timestamp_unix", "tx_hash", "tx_from",
        "authorization_chain_id", "delegate_address", "authorization_nonce",
    ]
    for chunk in pd.read_csv(raw_path, usecols=columns, chunksize=chunksize, dtype=str):
        n_rows += len(chunk)
        chunk["delegate_address"] = chunk["delegate_address"].str.lower()
        n_zero += int((chunk["delegate_address"] == ZERO_ADDRESS).sum())
        chunk = chunk[chunk["delegate_address"] != ZERO_ADDRESS].copy()
        chunk["block_number_int"] = chunk["block_number"].map(lambda value: int(value, 0))
        chunk["timestamp_int"] = chunk["block_timestamp_unix"].map(lambda value: int(value, 0))
        for address, group in chunk.groupby("delegate_address", sort=False):
            ordered = group.sort_values(["block_number_int", "tx_hash", "authorization_nonce"])
            first = ordered.iloc[0]
            current = aggregates.get(address)
            candidate_key = (
                int(first["block_number_int"]), str(first["tx_hash"]),
                str(first["authorization_nonce"]),
            )
            if current is None:
                aggregates[address] = {
                    "delegate_address": address,
                    "authorization_count": int(len(group)),
                    "first_block": int(group["block_number_int"].min()),
                    "last_block": int(group["block_number_int"].max()),
                    "first_timestamp_unix": int(group["timestamp_int"].min()),
                    "last_timestamp_unix": int(group["timestamp_int"].max()),
                    "first_tx_hash": str(first["tx_hash"]),
                    "first_tx_sender": str(first["tx_from"]).lower(),
                    "first_authorization_chain_id": str(first["authorization_chain_id"]),
                    "first_authorization_nonce": str(first["authorization_nonce"]),
                    "_first_key": candidate_key,
                }
            else:
                current["authorization_count"] += int(len(group))
                current["first_block"] = min(current["first_block"], int(group["block_number_int"].min()))
                current["last_block"] = max(current["last_block"], int(group["block_number_int"].max()))
                current["first_timestamp_unix"] = min(
                    current["first_timestamp_unix"], int(group["timestamp_int"].min())
                )
                current["last_timestamp_unix"] = max(
                    current["last_timestamp_unix"], int(group["timestamp_int"].max())
                )
                if candidate_key < current["_first_key"]:
                    current.update({
                        "first_tx_hash": str(first["tx_hash"]),
                        "first_tx_sender": str(first["tx_from"]).lower(),
                        "first_authorization_chain_id": str(first["authorization_chain_id"]),
                        "first_authorization_nonce": str(first["authorization_nonce"]),
                        "_first_key": candidate_key,
                    })
    records = []
    for record in aggregates.values():
        record = dict(record)
        record.pop("_first_key", None)
        records.append(record)
    frame = pd.DataFrame(records).sort_values("delegate_address").reset_index(drop=True)
    return frame, {"n_raw_rows": n_rows, "n_zero_address_rows": n_zero}


def _load_cache(path: str) -> dict[str, dict]:
    records = {}
    if not os.path.exists(path):
        return records
    with open(path) as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise RuntimeError(f"invalid snapshot cache line {line_number}: {error}") from error
            records[record["delegate_address"]] = record
    return records


def _matching_authorization(block: dict, aggregate: dict) -> dict:
    for transaction in block.get("transactions", []):
        if str(transaction.get("hash")).lower() != aggregate["first_tx_hash"].lower():
            continue
        for authorization in transaction.get("authorizationList", []):
            if (
                str(authorization.get("address")).lower() == aggregate["delegate_address"]
                and int(authorization.get("nonce"), 0)
                == int(aggregate["first_authorization_nonce"], 0)
            ):
                return authorization
    raise RuntimeError("first authorization tuple was not found in its recorded transaction")


def _fetch_authority_runtime_record(aggregate_row: dict, chain: str) -> dict:
    """Use one isolated client per worker so endpoint failover state is not shared."""
    client = ChainClient(chain)
    record = dict(aggregate_row)
    address = record["delegate_address"]
    try:
        block = client.get_block(int(record["first_block"]), full_transactions=True)
        authorization = _matching_authorization(block, record)
        authority, message_hash = recover_authority(authorization)
        historical_code = client.get_code(address, hex(int(record["first_block"])))
        latest_code = client.get_code(address, "latest")
        historical_normalized = normalize_hex(historical_code)
        latest_normalized = normalize_hex(latest_code)
        historical_bytes = to_bytes(historical_normalized)
        latest_bytes = to_bytes(latest_normalized)
        record.update({
            "authority_address": authority,
            "authority_message_hash": message_hash,
            "authority_equals_tx_sender": authority == record["first_tx_sender"],
            "historical_runtime_bytecode": "0x" + historical_normalized,
            "historical_code_bytes": len(historical_bytes),
            "historical_bytecode_sha256": hashlib.sha256(historical_bytes).hexdigest(),
            "latest_code_bytes": len(latest_bytes),
            "latest_bytecode_sha256": hashlib.sha256(latest_bytes).hexdigest(),
            "runtime_changed_since_first_authorization": historical_bytes != latest_bytes,
            "fetch_error": None,
        })
    except (RpcError, RuntimeError, ValueError, KeyError, TypeError) as error:
        record["fetch_error"] = f"{type(error).__name__}: {error}"
    return record


def fetch_authority_runtime_records(
    aggregates: pd.DataFrame,
    cache_path: str,
    *,
    chain: str = "ethereum",
    max_workers: int = 4,
    retry_cached_errors: bool = True,
) -> list[dict]:
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    cached = _load_cache(cache_path)
    pending = [
        record for record in aggregates.to_dict("records")
        if record["delegate_address"] not in cached
        or (
            retry_cached_errors
            and str(cached[record["delegate_address"]].get("fetch_error") or "").startswith(
                "RpcError:"
            )
        )
    ]
    with open(cache_path, "a") as cache_handle, ThreadPoolExecutor(max_workers=max_workers) as pool:
        fetched = pool.map(
            lambda record: _fetch_authority_runtime_record(record, chain),
            pending,
        )
        for completed_count, record in enumerate(fetched, 1):
            address = record["delegate_address"]
            cache_handle.write(json.dumps(record, sort_keys=True) + "\n")
            cache_handle.flush()
            cached[address] = record
            total_completed = len(aggregates) - len(pending) + completed_count
            if total_completed % 25 == 0 or completed_count == len(pending):
                print(
                    f"[postcutoff_snapshot] {total_completed}/{len(aggregates)}",
                    flush=True,
                )
    return [cached[address] for address in aggregates["delegate_address"]]


def build_complete_historical_runtime_index() -> dict:
    """Index every unique canonical runtime, not one representative per family."""
    path = os.path.join(REPO_ROOT, "revision_v2", "data", "authguardbench_7702_v2.csv.gz")
    canonical = pd.read_csv(
        path,
        usecols=["family_id", "bytecode_sha256", "runtime_bytecode"],
    ).sort_values(["family_id", "bytecode_sha256"])
    unique = canonical.drop_duplicates("bytecode_sha256", keep="first")
    entries = []
    hash_to_family = {}
    for row in unique.itertuples(index=False):
        tokens, _, _ = linear_sweep(normalize_hex(row.runtime_bytecode))
        entries.append((row.family_id, row.bytecode_sha256, opcode_kgrams(tokens, k=4)))
        hash_to_family[row.bytecode_sha256] = row.family_id
    return {"entries": entries, "hash_to_family": hash_to_family}


def add_family_provenance(frame: pd.DataFrame) -> pd.DataFrame:
    historical = build_complete_historical_runtime_index()
    output = frame.copy()
    family_matches = []
    for row in output.to_dict("records"):
        if row.get("fetch_error") or int(row.get("historical_code_bytes") or 0) == 0:
            family_matches.append((False, None, None, None))
            continue
        bytecode_hash = row["historical_bytecode_sha256"]
        if bytecode_hash in historical["hash_to_family"]:
            family_matches.append((True, historical["hash_to_family"][bytecode_hash], 1.0, False))
            continue
        tokens, _, _ = linear_sweep(normalize_hex(row["historical_runtime_bytecode"]))
        grams = opcode_kgrams(tokens, k=4)
        best_family = None
        best_similarity = -1.0
        for family_id, _, representative in historical["entries"]:
            similarity = jaccard(grams, representative)
            if similarity > best_similarity:
                best_similarity, best_family = similarity, family_id
        matched = best_family if best_similarity >= FAMILY_SIMILARITY_THRESHOLD else None
        family_matches.append((False, matched, best_similarity, matched is None))
    output[[
        "is_exact_historical_duplicate", "matched_historical_family",
        "best_historical_family_similarity", "is_candidate_unseen_family",
    ]] = pd.DataFrame(family_matches, index=output.index)

    valid_hashes = sorted({
        row["historical_bytecode_sha256"]
        for row in output.to_dict("records")
        if not row.get("fetch_error") and int(row.get("historical_code_bytes") or 0) > 0
    })
    family_by_hash = {value: f"T{index:04d}" for index, value in enumerate(valid_hashes, 1)}
    output["postcutoff_exact_runtime_family"] = output["historical_bytecode_sha256"].map(
        family_by_hash
    )
    return output


def main() -> int:
    os.makedirs(RESULTS_DIR, exist_ok=True)
    aggregates, raw_counts = aggregate_raw_authorizations(RAW_PATH)
    with open(CHECKPOINT_PATH) as handle:
        checkpoint = json.load(handle)
    if raw_counts["n_raw_rows"] != int(checkpoint["n_authorization_entries"]):
        raise RuntimeError(
            "raw authorization count does not match checkpoint: "
            f"{raw_counts['n_raw_rows']} != {checkpoint['n_authorization_entries']}"
        )
    records = fetch_authority_runtime_records(aggregates, CACHE_PATH, chain="ethereum")
    enriched = add_family_provenance(pd.DataFrame(records))
    enriched.to_csv(
        SNAPSHOT_PATH,
        index=False,
        compression={"method": "gzip", "mtime": 0},
        lineterminator="\n",
    )

    successful = enriched[enriched["fetch_error"].isna()]
    with_code = successful[successful["historical_code_bytes"] > 0]
    unseen = with_code[with_code["is_candidate_unseen_family"].fillna(False).astype(bool)]
    error_kinds = enriched.loc[
        enriched["fetch_error"].notna(), "fetch_error"
    ].map(lambda value: str(value).split(":", 1)[0]).value_counts().sort_index().to_dict()
    report = {
        "status": "FROZEN_POSTCUTOFF_CANDIDATE_SNAPSHOT_UNLABELED",
        "schema": "postcutoff-authority-snapshot-1.0",
        "chain": "ethereum",
        "raw_sha256": _sha256_file(RAW_PATH),
        "checkpoint_sha256": _sha256_file(CHECKPOINT_PATH),
        "snapshot_sha256": _sha256_file(SNAPSHOT_PATH),
        "builder_sha256": _sha256_file(__file__),
        "raw_counts": raw_counts,
        "checkpoint": checkpoint,
        "n_unique_nonzero_delegates": int(len(enriched)),
        "n_fetch_errors": int(enriched["fetch_error"].notna().sum()),
        "n_rpc_fetch_errors": int(error_kinds.get("RpcError", 0)),
        "n_invalid_authorization_tuples": int(error_kinds.get("ValueError", 0)),
        "n_no_code_at_first_authorization": int((successful["historical_code_bytes"] == 0).sum()),
        "n_with_historical_runtime": int(len(with_code)),
        "n_exact_historical_duplicates": int(with_code["is_exact_historical_duplicate"].sum()),
        "n_candidate_unseen_delegate_addresses": int(len(unseen)),
        "n_candidate_unseen_exact_runtime_families": int(
            unseen["postcutoff_exact_runtime_family"].nunique()
        ),
        "n_exact_postcutoff_runtime_families": int(
            with_code["postcutoff_exact_runtime_family"].nunique()
        ),
        "n_runtime_changed_since_first_authorization": int(
            with_code["runtime_changed_since_first_authorization"].sum()
        ),
        "n_authorities_distinct_from_transaction_sender": int(
            _count_false(successful["authority_equals_tx_sender"])
        ),
        "n_unique_recovered_authorities": int(successful["authority_address"].nunique()),
        "fetch_error_counts": error_kinds,
        "artifact": os.path.relpath(SNAPSHOT_PATH, REPO_ROOT),
        "canonical_similarity_audit": (
            "opcode-4-gram Jaccard against every unique canonical runtime; threshold 0.85"
        ),
        "claim_boundary": (
            "This is an unlabeled post-cutoff candidate snapshot. Similarity screening is a "
            "leakage audit, not proof of family independence; project-family clustering, "
            "independent labels, complete holds, and retraining are required before scoring."
        ),
        "historical_state_boundary": (
            "eth_getCode(address, first_block) observes end-of-block state, not transaction-"
            "index pre-state. Same-block code changes require transaction-level tracing."
        ),
    }
    with open(REPORT_PATH, "w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    print(json.dumps(report, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
