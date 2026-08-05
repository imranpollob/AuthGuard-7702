"""Freeze an untouched replication reserve disjoint from the first post-cutoff review set.

The first post-cutoff sample and every exact runtime family it contains are excluded. Selection
sees neither security labels nor model outputs. This reserve is not needed for the primary test;
it is available for replication or replacement and still requires project-family audit,
independent dual review, pre-label scoring, and adjudication before use.
"""
from __future__ import annotations

import hashlib
import json
import os

import pandas as pd

from sample_postcutoff_review import _sha256_file, select_review_sample

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
V3 = os.path.join(REPO_ROOT, "revision_v3")
RESULTS_DIR = os.path.join(V3, "results", "confirmatory_snapshot")
POST_DIR = os.path.join(V3, "results", "postcutoff_snapshot")
SNAPSHOT_PATH = os.path.join(POST_DIR, "ethereum_candidates.csv.gz")
SNAPSHOT_REPORT_PATH = os.path.join(POST_DIR, "ethereum_snapshot_report.json")
FIRST_POSTCUTOFF_MANIFEST_PATH = os.path.join(POST_DIR, "postcutoff_review_manifest.csv")
MANIFEST_PATH = os.path.join(RESULTS_DIR, "confirmatory_review_manifest.csv")
LOCK_PATH = os.path.join(RESULTS_DIR, "confirmatory_review_lock.json")
SAMPLE_SIZE = 150
SAMPLE_SEED = 77022027


def main() -> int:
    if os.path.exists(MANIFEST_PATH) or os.path.exists(LOCK_PATH):
        raise FileExistsError("confirmatory review sample is already frozen")
    with open(SNAPSHOT_REPORT_PATH) as handle:
        snapshot_report = json.load(handle)
    snapshot_hash = _sha256_file(SNAPSHOT_PATH)
    if snapshot_report.get("status") != "FROZEN_POSTCUTOFF_CANDIDATE_SNAPSHOT_UNLABELED":
        raise RuntimeError("source snapshot is not a frozen unlabeled candidate snapshot")
    if snapshot_report.get("snapshot_sha256") != snapshot_hash:
        raise RuntimeError("source snapshot hash differs from its frozen report")

    first_postcutoff = pd.read_csv(FIRST_POSTCUTOFF_MANIFEST_PATH)
    if first_postcutoff["family_id"].isna().any() or first_postcutoff["family_id"].duplicated().any():
        raise ValueError("first post-cutoff manifest must contain unique exact-runtime families")
    excluded_families = set(first_postcutoff["family_id"].astype(str))
    excluded_items = set(first_postcutoff["item_id"].astype(str))
    selected, report = select_review_sample(
        pd.read_csv(SNAPSHOT_PATH),
        sample_size=SAMPLE_SIZE,
        seed=SAMPLE_SEED,
        excluded_family_ids=excluded_families,
        sample_set="confirmatory",
    )
    if set(selected["family_id"].astype(str)) & excluded_families:
        raise RuntimeError("reserve selection overlaps the first post-cutoff runtime family")
    if set(selected["item_id"].astype(str)) & excluded_items:
        raise RuntimeError("reserve selection overlaps a first post-cutoff item")
    if len(selected) != SAMPLE_SIZE:
        raise RuntimeError("insufficient disjoint candidates for the frozen confirmatory target")

    os.makedirs(RESULTS_DIR, exist_ok=True)
    selected.to_csv(MANIFEST_PATH, index=False, lineterminator="\n")
    report.update({
        "sampling_status": "FROZEN_UNTOUCHED_CONFIRMATORY_SAMPLE",
        "snapshot_sha256": snapshot_hash,
        "source_snapshot_sha256": snapshot_hash,
        "first_postcutoff_manifest": os.path.relpath(FIRST_POSTCUTOFF_MANIFEST_PATH, REPO_ROOT),
        "first_postcutoff_manifest_sha256": _sha256_file(FIRST_POSTCUTOFF_MANIFEST_PATH),
        "first_postcutoff_item_ids_sha256": hashlib.sha256(
            "\n".join(sorted(excluded_items)).encode()
        ).hexdigest(),
        "first_postcutoff_family_ids_sha256": hashlib.sha256(
            "\n".join(sorted(excluded_families)).encode()
        ).hexdigest(),
        "manifest": os.path.relpath(MANIFEST_PATH, REPO_ROOT),
        "manifest_sha256": _sha256_file(MANIFEST_PATH),
        "sampler_sha256": _sha256_file(__file__),
        "independence_boundary": (
            "No reserve item or exact runtime family appears in the first post-cutoff review "
            "sample. Both post-cutoff samples are disjoint from the separate 150-item Gold-Test "
            "proxy whose provisional labels informed method development."
        ),
    })
    with open(LOCK_PATH, "w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
