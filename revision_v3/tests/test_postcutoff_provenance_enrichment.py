from __future__ import annotations

import importlib.util

import pandas as pd
import pytest


def _load_module():
    path = __file__.replace(
        "tests/test_postcutoff_provenance_enrichment.py",
        "experiments/temporal_v2/enrich_postcutoff_provenance.py",
    )
    spec = importlib.util.spec_from_file_location("postcutoff_provenance_enrichment", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


enrichment = _load_module()


def _worklist():
    return pd.DataFrame([{
        "item_id": "ethereum:0xabc",
        "delegate_address": "0xabc",
        "delegate_explorer_url": "https://etherscan.io/address/0xabc",
        "authorization_tx_explorer_url": "https://etherscan.io/tx/0xaaa",
    }])


def test_summaries_strip_source_abi_and_bytecode():
    payload = {
        "is_verified": True,
        "name": "WalletImpl",
        "source_code": "secretly very large source",
        "abi": "large ABI",
        "deployed_bytecode": "0xdeadbeef",
        "compiler_settings": {"compilationTarget": {"Wallet.sol": "WalletImpl"}},
        "minimal_proxy_address_hash": "0xDEF",
    }
    summary = enrichment.summarize_response("blockscout_contract", 200, payload)
    assert summary["name"] == "WalletImpl"
    assert summary["compilation_targets"] == ["Wallet.sol:WalletImpl"]
    assert not ({"source_code", "abi", "deployed_bytecode"} & set(summary))


def test_collection_is_resumable_and_output_stays_nonadjudicative(tmp_path):
    calls = []

    def fake_fetch(url):
        calls.append(url)
        if "sourcify" in url:
            return 200, {
                "match": "exact_match",
                "compilation": {"name": "WalletImpl", "fullyQualifiedName": "W.sol:WalletImpl"},
                "proxyResolution": {"isProxy": True, "implementations": ["0xdef"]},
            }
        if "smart-contracts" in url:
            return 200, {"is_verified": True, "name": "WalletImpl", "source_code": "discard"}
        return 200, {"is_verified": True, "name": "Wallet", "public_tags": []}

    cache = tmp_path / "cache.jsonl"
    records = enrichment.collect_evidence(
        _worklist(), worklist_sha256="locked", cache_path=str(cache),
        fetcher=fake_fetch, delay_seconds=0,
    )
    assert len(calls) == 3
    records_again = enrichment.collect_evidence(
        _worklist(), worklist_sha256="locked", cache_path=str(cache),
        fetcher=fake_fetch, delay_seconds=0,
    )
    assert len(calls) == 3
    table = enrichment.build_evidence_table(_worklist(), records_again)
    assert table.iloc[0]["candidate_name_signals"] == "W.sol:WalletImpl;Wallet;WalletImpl"
    assert table.iloc[0]["candidate_related_addresses"] == "0xdef"
    assert "project_family" not in " ".join(table.columns)
    assert "source_code" not in cache.read_text()


def test_cache_rejects_different_frozen_worklist(tmp_path):
    cache = tmp_path / "cache.jsonl"
    enrichment.collect_evidence(
        _worklist(), worklist_sha256="one", cache_path=str(cache),
        fetcher=lambda _: (404, {}), delay_seconds=0,
    )
    with pytest.raises(ValueError, match="different frozen worklist"):
        enrichment.collect_evidence(
            _worklist(), worklist_sha256="two", cache_path=str(cache),
            fetcher=lambda _: (404, {}), delay_seconds=0,
        )


def test_enrichment_refuses_label_or_score_columns(tmp_path):
    frame = _worklist()
    frame["human_label"] = "UNSAFE"
    with pytest.raises(ValueError, match="refuses sensitive columns"):
        enrichment.collect_evidence(
            frame, worklist_sha256="locked", cache_path=str(tmp_path / "cache.jsonl"),
            fetcher=lambda _: (404, {}), delay_seconds=0,
        )


def test_explicit_retry_can_replace_cached_error_append_only(tmp_path):
    cache = tmp_path / "cache.jsonl"
    attempts = {"n": 0}

    def flaky_fetch(_):
        attempts["n"] += 1
        if attempts["n"] <= 3:
            raise TimeoutError("temporary")
        return 404, {}

    first = enrichment.collect_evidence(
        _worklist(), worklist_sha256="locked", cache_path=str(cache),
        fetcher=flaky_fetch, delay_seconds=0,
    )
    assert all(record["retrieval_status"] == "ERROR" for record in first.values())
    second = enrichment.collect_evidence(
        _worklist(), worklist_sha256="locked", cache_path=str(cache),
        fetcher=flaky_fetch, delay_seconds=0, retry_errors=True,
    )
    assert all(record["retrieval_status"] == "COMPLETE" for record in second.values())
    loaded = enrichment._load_cache(str(cache), "locked")
    assert all(record["retrieval_status"] == "COMPLETE" for record in loaded.values())
