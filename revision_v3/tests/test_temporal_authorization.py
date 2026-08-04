from __future__ import annotations

import pandas as pd
import pytest

from temporal.authorization import authorization_message_hash, recover_authority
from temporal import collector
from revision_v3.experiments.temporal_v2.build_postcutoff_snapshot import (
    _count_false,
    aggregate_raw_authorizations,
    fetch_authority_runtime_records,
)
from revision_v3.experiments.temporal_v2 import build_postcutoff_snapshot


REAL_AUTHORIZATION = {
    "chainId": "0x1",
    "address": "0x56ef4d420533e3c4c7e79c64d1f958aa89d2c3a9",
    "nonce": "0x0",
    "yParity": "0x1",
    "r": "0xa38e672092b77ce343d002877394a8b7295ffb17a3f81e8899fc437c853f3a8c",
    "s": "0x5b2521d4bab2d75f37c814edd3e02e32770a2dccd18a02387305256df56222dd",
}


def test_recovers_real_eip7702_authority_vector():
    authority, message_hash = recover_authority(REAL_AUTHORIZATION)
    assert authority == "0xc571f7b4135c23846bd596b691ba0582545bd9ff"
    assert message_hash == (
        "0x448cb6c0f157a7a573003707f8d3e5d9ec32fbfd30c7bf64780f052d7f1063c2"
    )
    assert authorization_message_hash(1, REAL_AUTHORIZATION["address"], 0).hex() == message_hash[2:]


def test_streaming_aggregation_is_deterministic_and_excludes_revocations(tmp_path):
    path = tmp_path / "raw.csv"
    pd.DataFrame([
        {
            "block_number": 11, "block_timestamp_unix": 101, "tx_hash": "0x2",
            "tx_from": "0xSender2", "authorization_chain_id": "0x1",
            "delegate_address": "0x" + "22" * 20, "authorization_nonce": "0x1",
        },
        {
            "block_number": 10, "block_timestamp_unix": 100, "tx_hash": "0x1",
            "tx_from": "0xSender1", "authorization_chain_id": "0x1",
            "delegate_address": "0x" + "22" * 20, "authorization_nonce": "0x0",
        },
        {
            "block_number": 12, "block_timestamp_unix": 102, "tx_hash": "0x3",
            "tx_from": "0xSender3", "authorization_chain_id": "0x1",
            "delegate_address": "0x" + "00" * 20, "authorization_nonce": "0x2",
        },
    ]).to_csv(path, index=False)
    frame, counts = aggregate_raw_authorizations(str(path), chunksize=1)
    assert counts == {"n_raw_rows": 3, "n_zero_address_rows": 1}
    assert len(frame) == 1
    assert frame.iloc[0]["authorization_count"] == 2
    assert frame.iloc[0]["first_block"] == 10
    assert frame.iloc[0]["first_tx_hash"] == "0x1"


def test_collector_refuses_to_append_to_git_lfs_pointer(tmp_path, monkeypatch):
    monkeypatch.setattr(collector, "OUTPUT_DIR", str(tmp_path))
    pointer = tmp_path / "snapshot_ethereum_authorizations.csv"
    pointer.write_text(
        "version https://git-lfs.github.com/spec/v1\n"
        "oid sha256:" + "1" * 64 + "\nsize 100\n"
    )
    with pytest.raises(RuntimeError, match="Git-LFS pointer"):
        collector._row_writer("ethereum", "snapshot")


def test_snapshot_retries_cached_rpc_errors(tmp_path, monkeypatch):
    address = "0x" + "12" * 20
    aggregates = pd.DataFrame([{
        "delegate_address": address,
        "authorization_count": 1,
        "first_block": 10,
        "last_block": 10,
        "first_timestamp_unix": 100,
        "last_timestamp_unix": 100,
        "first_tx_hash": "0x" + "34" * 32,
        "first_tx_sender": "0x" + "56" * 20,
        "first_authorization_chain_id": "0x1",
        "first_authorization_nonce": "0x0",
    }])
    cache_path = tmp_path / "cache.jsonl"
    cache_path.write_text(
        '{"delegate_address":"' + address + '","fetch_error":"RpcError: timeout"}\n'
    )

    def succeed(record, chain):
        return {**record, "fetch_error": None, "historical_code_bytes": 1}

    monkeypatch.setattr(build_postcutoff_snapshot, "_fetch_authority_runtime_record", succeed)
    records = fetch_authority_runtime_records(aggregates, str(cache_path), max_workers=1)
    assert records[0]["fetch_error"] is None
    assert records[0]["historical_code_bytes"] == 1
    assert len(cache_path.read_text().splitlines()) == 2


def test_snapshot_does_not_retry_deterministically_invalid_signature(tmp_path, monkeypatch):
    address = "0x" + "12" * 20
    aggregates = pd.DataFrame([{"delegate_address": address}])
    cache_path = tmp_path / "cache.jsonl"
    cache_path.write_text(
        '{"delegate_address":"' + address
        + '","fetch_error":"ValueError: authorization r is outside range"}\n'
    )

    def should_not_run(record, chain):
        raise AssertionError("deterministic invalid tuple must not be retried")

    monkeypatch.setattr(
        build_postcutoff_snapshot, "_fetch_authority_runtime_record", should_not_run
    )
    records = fetch_authority_runtime_records(aggregates, str(cache_path), max_workers=1)
    assert records[0]["fetch_error"].startswith("ValueError:")
    assert len(cache_path.read_text().splitlines()) == 1


def test_object_boolean_false_count_is_never_bitwise_inverted():
    values = pd.Series([True, False, False], dtype=object)
    assert _count_false(values) == 2
