"""Builds revision_v3/data/input_manifest.json from the canonical Revision v2 benchmark.

Read-only: this script never writes anything under revision_v2/. It hashes and
summarizes revision_v2/data/authguardbench_7702_v2.csv.gz so that every later
Revision v3 script can refuse to run if the canonical input has changed.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
CONFIG_PATH = os.path.join(REPO_ROOT, "revision_v3", "configs", "canonical_inputs.json")
MANIFEST_PATH = os.path.join(REPO_ROOT, "revision_v3", "data", "input_manifest.json")


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build() -> dict:
    with open(CONFIG_PATH) as f:
        config = json.load(f)

    benchmark_path = os.path.join(REPO_ROOT, config["benchmark_csv_gz"])
    if not os.path.exists(benchmark_path):
        raise FileNotFoundError(f"canonical benchmark missing: {benchmark_path}")

    file_hash = sha256_of(benchmark_path)
    df = pd.read_csv(benchmark_path)

    missing_cols = [c for c in config["required_columns"] if c not in df.columns]
    if missing_cols:
        raise ValueError(f"canonical benchmark missing expected columns: {missing_cols}")

    primary = df[df["population"] == "PRIMARY_EVALUATION"]

    manifest = {
        "source_paths": {
            "benchmark_csv_gz": config["benchmark_csv_gz"],
        },
        "sha256": {
            "benchmark_csv_gz": file_hash,
        },
        "row_counts": {
            "total_rows": int(len(df)),
            "primary_rows": int(len(primary)),
            "external_benign_control_rows": int((df["population"] == "EXTERNAL_BENIGN_CONTROL").sum()),
            "qualitative_control_rows": int((df["population"] == "QUALITATIVE_CONTROL").sum()),
            "excluded_uncertain_input_rows": int((df["population"] == "EXCLUDED_UNCERTAIN_INPUT").sum()),
        },
        "label_counts": {
            "primary_positive": int((primary["label"] == 1).sum()),
            "primary_negative": int((primary["label"] == 0).sum()),
        },
        "family_counts": {
            "primary_families": int(primary["family_id"].nunique()),
        },
        "fold_counts": {
            "n_folds": int(primary["fold_id"].nunique()),
            "rows_per_fold": {str(k): int(v) for k, v in primary["fold_id"].value_counts().sort_index().items()},
        },
        "column_schema": list(df.columns),
        "expected_population": config["expected_population"],
    }

    exp = config["expected_population"]
    checks = {
        "primary_rows_match": manifest["row_counts"]["primary_rows"] == exp["primary_rows"],
        "primary_positive_match": manifest["label_counts"]["primary_positive"] == exp["primary_positive"],
        "primary_negative_match": manifest["label_counts"]["primary_negative"] == exp["primary_negative"],
        "primary_families_match": manifest["family_counts"]["primary_families"] == exp["primary_families"],
        "n_folds_match": manifest["fold_counts"]["n_folds"] == exp["n_folds"],
    }
    manifest["validation_checks"] = checks

    if not all(checks.values()):
        raise AssertionError(f"canonical input does not match expected population: {checks}")

    return manifest


def main() -> int:
    manifest = build()
    os.makedirs(os.path.dirname(MANIFEST_PATH), exist_ok=True)
    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
    print(f"[manifest] wrote {MANIFEST_PATH}")
    print(json.dumps(manifest["validation_checks"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
