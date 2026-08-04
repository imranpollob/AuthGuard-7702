"""Freeze a score-blind, exact-runtime-family sample for post-cutoff human review."""
from __future__ import annotations

import hashlib
import json
import os

import numpy as np
import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
V3 = os.path.join(REPO_ROOT, "revision_v3")
RESULTS_DIR = os.path.join(V3, "results", "postcutoff_snapshot")
SNAPSHOT_PATH = os.path.join(RESULTS_DIR, "ethereum_candidates.csv.gz")
SNAPSHOT_REPORT_PATH = os.path.join(RESULTS_DIR, "ethereum_snapshot_report.json")
MANIFEST_PATH = os.path.join(RESULTS_DIR, "postcutoff_review_manifest.csv")
LOCK_PATH = os.path.join(RESULTS_DIR, "postcutoff_review_lock.json")
SAMPLE_SIZE = 150
SAMPLE_SEED = 77022026


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def select_review_sample(
    snapshot: pd.DataFrame,
    *,
    sample_size: int = SAMPLE_SIZE,
    seed: int = SAMPLE_SEED,
) -> tuple[pd.DataFrame, dict]:
    """Sample unseen exact-runtime families without using labels or model outputs."""
    forbidden_markers = ("label", "score", "probability", "prediction", "decision")
    forbidden = sorted(
        column for column in snapshot.columns
        if any(marker in column.lower() for marker in forbidden_markers)
    )
    if forbidden:
        raise ValueError(
            "score-blind sampler refuses label/model-output columns: " + ", ".join(forbidden)
        )
    required = {
        "delegate_address", "authority_address", "historical_runtime_bytecode",
        "historical_bytecode_sha256", "postcutoff_exact_runtime_family",
        "is_candidate_unseen_family", "is_exact_historical_duplicate", "fetch_error",
        "historical_code_bytes", "authorization_count", "first_block", "first_tx_hash",
    }
    missing = required - set(snapshot.columns)
    if missing:
        raise ValueError(f"post-cutoff snapshot is missing fields: {sorted(missing)}")
    eligible = snapshot[
        snapshot["fetch_error"].isna()
        & (snapshot["historical_code_bytes"] > 0)
        & snapshot["is_candidate_unseen_family"].eq(True)  # noqa: E712
        & ~snapshot["is_exact_historical_duplicate"].eq(True)  # noqa: E712
    ].copy()
    eligible = eligible.sort_values(
        ["postcutoff_exact_runtime_family", "authorization_count", "delegate_address"],
        ascending=[True, False, True],
    ).drop_duplicates("postcutoff_exact_runtime_family", keep="first")

    rng = np.random.default_rng(seed)
    order = rng.permutation(len(eligible))
    selected = eligible.iloc[order[: min(sample_size, len(eligible))]].copy()
    selected = selected.sort_values("delegate_address").reset_index(drop=True)
    selected["item_id"] = "ethereum:" + selected["delegate_address"].str.lower()
    selected["sample_set"] = "postcutoff"
    selected["family_id"] = selected["postcutoff_exact_runtime_family"]
    selected["chain"] = "ethereum"
    selected["address"] = selected["delegate_address"].str.lower()
    selected["runtime_bytecode"] = selected["historical_runtime_bytecode"]
    selected["bytecode_sha256"] = selected["historical_bytecode_sha256"]
    manifest_columns = [
        "item_id", "sample_set", "family_id", "chain", "address", "runtime_bytecode",
        "bytecode_sha256", "authority_address", "authorization_count", "first_block",
        "first_tx_hash", "runtime_changed_since_first_authorization",
        "best_historical_family_similarity",
    ]
    report = {
        "sampling_status": (
            "COMPLETE" if len(eligible) >= sample_size else "UNDER_TARGET_TAKE_ALL_ELIGIBLE"
        ),
        "sample_seed": seed,
        "target_n": sample_size,
        "n_eligible_exact_runtime_families": int(len(eligible)),
        "n_selected": int(len(selected)),
        "selection": (
            "simple random sample without replacement over exact-runtime families after "
            "excluding canonical exact/similarity matches; representative is the most "
            "frequently authorized address, then lexical address"
        ),
        "claim_boundary": (
            "Exact-runtime deduplication and canonical similarity screening do not establish "
            "project-family independence. Cluster and adjudicate project provenance before "
            "any model retraining or scoring."
        ),
    }
    return selected[manifest_columns], report


def main() -> int:
    with open(SNAPSHOT_REPORT_PATH) as handle:
        snapshot_report = json.load(handle)
    snapshot_hash = _sha256_file(SNAPSHOT_PATH)
    if snapshot_report.get("status") != "FROZEN_POSTCUTOFF_CANDIDATE_SNAPSHOT_UNLABELED":
        raise RuntimeError("snapshot report does not preserve the required unlabeled status")
    if snapshot_report.get("snapshot_sha256") != snapshot_hash:
        raise RuntimeError("snapshot artifact hash does not match its frozen report")
    snapshot = pd.read_csv(SNAPSHOT_PATH)
    selected, report = select_review_sample(snapshot)
    manifest_tmp = MANIFEST_PATH + ".tmp"
    selected.to_csv(manifest_tmp, index=False, lineterminator="\n")
    os.replace(manifest_tmp, MANIFEST_PATH)
    report.update({
        "snapshot_sha256": snapshot_hash,
        "selected_bytecode_hashes_sha256": hashlib.sha256(
            "\n".join(sorted(selected["bytecode_sha256"])).encode()
        ).hexdigest(),
        "manifest": os.path.relpath(MANIFEST_PATH, REPO_ROOT),
        "manifest_sha256": _sha256_file(MANIFEST_PATH),
        "sampler_sha256": _sha256_file(__file__),
    })
    lock_tmp = LOCK_PATH + ".tmp"
    with open(lock_tmp, "w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    os.replace(lock_tmp, LOCK_PATH)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
