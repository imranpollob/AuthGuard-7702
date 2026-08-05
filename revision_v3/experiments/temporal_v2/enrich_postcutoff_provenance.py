"""Collect public, score-blind provenance leads for frozen post-cutoff delegates.

Queries the official Sourcify lookup API and the public Ethereum Blockscout API. Responses are
reduced to verification, name/tag, compiler, and proxy metadata; source text, ABI, bytecode,
security features, labels, and model outputs are never retained. The resumable cache is an
append-only JSONL file so an interrupted network pass can continue without repeating requests.

The generated CSV is an auditor aid. It never writes to the project-family audit and never
converts a provider name or verified-source match into a confirmed project family.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from typing import Callable

import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
BASE = os.path.join(REPO_ROOT, "revision_v3", "results", "postcutoff_snapshot")
DEFAULT_WORKLIST = os.path.join(BASE, "postcutoff_project_family_worklist.csv")
DEFAULT_WORKLIST_REPORT = os.path.join(BASE, "postcutoff_project_family_worklist_report.json")
DEFAULT_CACHE = os.path.join(BASE, "postcutoff_public_provenance_cache.jsonl")
DEFAULT_OUTPUT = os.path.join(BASE, "postcutoff_public_provenance_evidence.csv")
DEFAULT_REPORT = os.path.join(BASE, "postcutoff_public_provenance_evidence_report.json")

USER_AGENT = "AuthGuard-7702-academic-provenance-audit/1.0"
PROVIDERS = ("blockscout_address", "blockscout_contract", "sourcify")
FORBIDDEN_MARKERS = ("label", "score", "prediction", "decision", "reviewer", "adjudicat")


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path: str) -> dict:
    with open(path) as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def provider_url(provider: str, address: str) -> str:
    address = address.lower()
    if provider == "blockscout_address":
        return f"https://eth.blockscout.com/api/v2/addresses/{address}"
    if provider == "blockscout_contract":
        return f"https://eth.blockscout.com/api/v2/smart-contracts/{address}"
    if provider == "sourcify":
        return (
            f"https://sourcify.dev/server/v2/contract/1/{address}"
            "?fields=compilation,proxyResolution"
        )
    raise ValueError(f"unknown provenance provider: {provider}")


def fetch_json(url: str, *, timeout: float = 30.0, retries: int = 3) -> tuple[int, dict]:
    """Fetch JSON with bounded retry. A 404 is a valid negative lookup, not a run failure."""
    last_error: Exception | None = None
    for attempt in range(retries):
        request = urllib.request.Request(
            url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read(2_000_000)
                value = json.loads(body.decode("utf-8"))
                return int(response.status), value if isinstance(value, dict) else {"value": value}
        except urllib.error.HTTPError as error:
            body = error.read(200_000)
            try:
                value = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                value = {"error": body.decode("utf-8", errors="replace")[:1000]}
            if error.code == 404:
                return 404, value if isinstance(value, dict) else {"value": value}
            last_error = error
            if error.code != 429 and error.code < 500:
                break
        except (OSError, TimeoutError, json.JSONDecodeError) as error:
            last_error = error
        if attempt + 1 < retries:
            time.sleep(1.0 * (2 ** attempt))
    raise RuntimeError(f"public provenance lookup failed for {url}: {last_error}")


def _public_tags(value) -> list[str]:
    if not isinstance(value, list):
        return []
    tags = []
    for entry in value:
        if not isinstance(entry, dict):
            continue
        for key in ("display_name", "label"):
            if entry.get(key):
                tags.append(str(entry[key]).strip())
    return sorted(set(filter(None, tags)))


def summarize_response(provider: str, http_status: int, payload: dict) -> dict:
    """Retain only neutral provenance metadata; intentionally discard source/ABI/bytecode."""
    if http_status == 404:
        return {"lookup_status": "NOT_FOUND"}
    if http_status != 200:
        return {"lookup_status": f"HTTP_{http_status}"}
    if provider == "blockscout_address":
        token = payload.get("token") if isinstance(payload.get("token"), dict) else {}
        return {
            "lookup_status": "FOUND",
            "is_verified": payload.get("is_verified"),
            "name": payload.get("name"),
            "implementation_name": payload.get("implementation_name"),
            "implementation_address": payload.get("implementation_address"),
            "creator_address": payload.get("creator_address_hash"),
            "creation_transaction": payload.get("creation_transaction_hash"),
            "public_tags": _public_tags(payload.get("public_tags")),
            "token_name": token.get("name"),
            "token_symbol": token.get("symbol"),
        }
    if provider == "blockscout_contract":
        settings = payload.get("compiler_settings")
        settings = settings if isinstance(settings, dict) else {}
        targets = settings.get("compilationTarget")
        targets = targets if isinstance(targets, dict) else {}
        return {
            "lookup_status": "FOUND",
            "is_verified": payload.get("is_verified"),
            "is_fully_verified": payload.get("is_fully_verified"),
            "is_partially_verified": payload.get("is_partially_verified"),
            "is_verified_via_sourcify": payload.get("is_verified_via_sourcify"),
            "is_verified_via_eth_bytecode_db": payload.get("is_verified_via_eth_bytecode_db"),
            "name": payload.get("name"),
            "file_path": payload.get("file_path"),
            "compiler_version": payload.get("compiler_version"),
            "language": payload.get("language"),
            "verified_at": payload.get("verified_at"),
            "verified_twin_address": payload.get("verified_twin_address_hash"),
            "minimal_proxy_address": payload.get("minimal_proxy_address_hash"),
            "sourcify_repo_url": payload.get("sourcify_repo_url"),
            "compilation_targets": sorted(
                f"{path}:{name}" for path, name in targets.items()
            ),
        }
    if provider == "sourcify":
        compilation = payload.get("compilation")
        compilation = compilation if isinstance(compilation, dict) else {}
        proxy = payload.get("proxyResolution")
        proxy = proxy if isinstance(proxy, dict) else {}
        implementations = proxy.get("implementations")
        if not isinstance(implementations, list):
            implementations = []
        normalized_implementations = []
        for value in implementations:
            if isinstance(value, dict):
                address = value.get("address") or value.get("addressHash")
            else:
                address = value
            if address:
                normalized_implementations.append(str(address).lower())
        return {
            "lookup_status": "VERIFIED" if payload.get("match") else "NOT_FOUND",
            "match": payload.get("match"),
            "creation_match": payload.get("creationMatch"),
            "runtime_match": payload.get("runtimeMatch"),
            "verified_at": payload.get("verifiedAt"),
            "contract_name": compilation.get("name"),
            "fully_qualified_name": compilation.get("fullyQualifiedName"),
            "language": compilation.get("language"),
            "compiler": compilation.get("compiler"),
            "compiler_version": compilation.get("compilerVersion"),
            "is_proxy": proxy.get("isProxy"),
            "proxy_type": proxy.get("proxyType"),
            "implementation_addresses": sorted(set(normalized_implementations)),
        }
    raise ValueError(f"unknown provenance provider: {provider}")


def _load_cache(cache_path: str, worklist_sha256: str) -> dict[tuple[str, str], dict]:
    records: dict[tuple[str, str], dict] = {}
    if not os.path.exists(cache_path):
        return records
    with open(cache_path) as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"invalid cache JSON at line {line_number}: {error}") from error
            if record.get("worklist_sha256") != worklist_sha256:
                raise ValueError("provenance cache targets a different frozen worklist")
            key = (str(record.get("item_id")), str(record.get("provider")))
            if key in records and records[key].get("retrieval_status") != "ERROR":
                raise ValueError(f"duplicate provenance cache key after completed lookup: {key}")
            records[key] = record
    return records


def collect_evidence(
    worklist: pd.DataFrame,
    *,
    worklist_sha256: str,
    cache_path: str,
    fetcher: Callable[[str], tuple[int, dict]] = fetch_json,
    delay_seconds: float = 0.2,
    max_items: int | None = None,
    retry_errors: bool = False,
) -> dict[tuple[str, str], dict]:
    forbidden = sorted(
        column for column in worklist.columns
        if any(marker in column.lower() for marker in FORBIDDEN_MARKERS)
    )
    if forbidden:
        raise ValueError("provenance enrichment refuses sensitive columns: " + ", ".join(forbidden))
    required = {"item_id", "delegate_address"}
    if missing := required - set(worklist.columns):
        raise ValueError(f"worklist missing fields: {sorted(missing)}")
    if worklist["item_id"].duplicated().any():
        raise ValueError("worklist item IDs must be unique")
    selected = worklist.sort_values("item_id")
    if max_items is not None:
        selected = selected.head(max_items)
    records = _load_cache(cache_path, worklist_sha256)
    os.makedirs(os.path.dirname(os.path.abspath(cache_path)), exist_ok=True)
    with open(cache_path, "a") as cache:
        for row in selected.itertuples(index=False):
            item_id = str(row.item_id)
            address = str(row.delegate_address).lower()
            for provider in PROVIDERS:
                key = (item_id, provider)
                if key in records and not (
                    retry_errors and records[key].get("retrieval_status") == "ERROR"
                ):
                    continue
                url = provider_url(provider, address)
                try:
                    http_status, payload = fetcher(url)
                    summary = summarize_response(provider, http_status, payload)
                    record = {
                        "item_id": item_id,
                        "delegate_address": address,
                        "provider": provider,
                        "provider_url": url,
                        "http_status": http_status,
                        "retrieval_status": "COMPLETE",
                        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                        "worklist_sha256": worklist_sha256,
                        "summary": summary,
                    }
                except Exception as error:  # recorded fail-closed; rerun requires explicit retry flag
                    record = {
                        "item_id": item_id,
                        "delegate_address": address,
                        "provider": provider,
                        "provider_url": url,
                        "http_status": None,
                        "retrieval_status": "ERROR",
                        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                        "worklist_sha256": worklist_sha256,
                        "error_type": type(error).__name__,
                        "error": str(error)[:1000],
                        "summary": {"lookup_status": "ERROR"},
                    }
                cache.write(json.dumps(record, sort_keys=True) + "\n")
                cache.flush()
                records[key] = record
                if delay_seconds > 0:
                    time.sleep(delay_seconds)
    return records


def build_evidence_table(worklist: pd.DataFrame, records: dict[tuple[str, str], dict]) -> pd.DataFrame:
    rows = []
    for base in worklist.sort_values("item_id").to_dict("records"):
        item_id = str(base["item_id"])
        provider_records = {provider: records.get((item_id, provider)) for provider in PROVIDERS}
        names: set[str] = set()
        proxies: set[str] = set()
        references: set[str] = {
            str(base["delegate_explorer_url"]), str(base["authorization_tx_explorer_url"])
        }
        for provider, record in provider_records.items():
            if not record:
                continue
            if record.get("retrieval_status") == "COMPLETE":
                references.add(str(record["provider_url"]))
            summary = record.get("summary", {})
            for field in (
                "name", "implementation_name", "token_name", "token_symbol",
                "contract_name", "fully_qualified_name", "file_path",
            ):
                value = summary.get(field)
                if value:
                    names.add(str(value).strip())
            names.update(str(value).strip() for value in summary.get("public_tags", []) if value)
            names.update(
                str(value).strip() for value in summary.get("compilation_targets", []) if value
            )
            for field in ("implementation_address", "verified_twin_address", "minimal_proxy_address"):
                if summary.get(field):
                    proxies.add(str(summary[field]).lower())
            proxies.update(str(value).lower() for value in summary.get("implementation_addresses", []))
        row = {
            "item_id": item_id,
            "delegate_address": base["delegate_address"],
            "candidate_name_signals": ";".join(sorted(filter(None, names))),
            "candidate_related_addresses": ";".join(sorted(filter(None, proxies))),
            "evidence_reference_candidates": ";".join(sorted(references)),
            "blockscout_address_status": (
                provider_records["blockscout_address"] or {}
            ).get("summary", {}).get("lookup_status", "MISSING"),
            "blockscout_contract_status": (
                provider_records["blockscout_contract"] or {}
            ).get("summary", {}).get("lookup_status", "MISSING"),
            "sourcify_status": (
                provider_records["sourcify"] or {}
            ).get("summary", {}).get("lookup_status", "MISSING"),
            "all_provider_requests_complete": all(
                record is not None and record.get("retrieval_status") == "COMPLETE"
                for record in provider_records.values()
            ),
            "auditor_instruction": (
                "Treat all names, tags, twins, and proxy addresses as leads. Independently "
                "verify project ownership and deployment relationships before entering CONFIRMED."
            ),
        }
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worklist", default=DEFAULT_WORKLIST)
    parser.add_argument("--worklist-report", default=DEFAULT_WORKLIST_REPORT)
    parser.add_argument("--cache", default=DEFAULT_CACHE)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--report", default=DEFAULT_REPORT)
    parser.add_argument("--delay-seconds", type=float, default=0.2)
    parser.add_argument("--max-items", type=int)
    parser.add_argument("--retry-errors", action="store_true")
    args = parser.parse_args()

    worklist_hash = sha256_file(args.worklist)
    worklist_report = _json(args.worklist_report)
    if worklist_report.get("status") != "SCORE_BLIND_PROVENANCE_WORKLIST_COMPLETE":
        raise ValueError("provenance worklist report is not complete")
    if worklist_report.get("worklist_sha256") != worklist_hash:
        raise ValueError("provenance worklist hash differs from its report")
    worklist = pd.read_csv(args.worklist)
    records = collect_evidence(
        worklist,
        worklist_sha256=worklist_hash,
        cache_path=args.cache,
        delay_seconds=args.delay_seconds,
        max_items=args.max_items,
        retry_errors=args.retry_errors,
    )
    evidence = build_evidence_table(worklist, records)
    evidence.to_csv(args.output, index=False, lineterminator="\n")
    provider_counts = {
        provider: dict(sorted(Counter(
            (records.get((str(item_id), provider)) or {}).get("summary", {}).get(
                "lookup_status", "MISSING"
            )
            for item_id in worklist["item_id"]
        ).items()))
        for provider in PROVIDERS
    }
    n_errors = sum(
        record.get("retrieval_status") == "ERROR" for record in records.values()
    )
    report = {
        "status": (
            "COMPLETE_PUBLIC_PROVENANCE_LEADS"
            if len(records) == len(worklist) * len(PROVIDERS) and n_errors == 0
            else "INCOMPLETE_PUBLIC_PROVENANCE_LEADS"
        ),
        "n_items": len(worklist),
        "n_expected_provider_requests": len(worklist) * len(PROVIDERS),
        "n_cached_provider_requests": len(records),
        "n_request_errors": n_errors,
        "n_items_with_name_signals": int(evidence["candidate_name_signals"].fillna("").ne("").sum()),
        "n_items_with_related_address_signals": int(
            evidence["candidate_related_addresses"].fillna("").ne("").sum()
        ),
        "provider_lookup_status_counts": provider_counts,
        "worklist_sha256": worklist_hash,
        "cache_sha256": sha256_file(args.cache),
        "evidence_sha256": sha256_file(args.output),
        "collector_sha256": sha256_file(__file__),
        "claim_boundary": (
            "Public verification metadata supplies research leads only. It does not prove "
            "project ownership, related-family completeness, benignity, or maliciousness."
        ),
    }
    with open(args.report, "w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    print(json.dumps(report, indent=2, sort_keys=True), flush=True)
    return 0 if report["status"] == "COMPLETE_PUBLIC_PROVENANCE_LEADS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
