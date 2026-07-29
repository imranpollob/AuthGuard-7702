"""Canonical Revision v2 dataset loader for Revision v3.

Loads revision_v2/data/authguardbench_7702_v2.csv.gz as an immutable input: verifies its
SHA-256 against the recorded manifest before returning anything, and refuses to continue if
the file has changed since the manifest was built. Also exposes family/fold isolation checks
used both at load time and by the test suite.
"""
from __future__ import annotations

import hashlib
import json
import os

import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
CONFIG_PATH = os.path.join(REPO_ROOT, "revision_v3", "configs", "canonical_inputs.json")
MANIFEST_PATH = os.path.join(REPO_ROOT, "revision_v3", "data", "input_manifest.json")


class CanonicalInputChanged(RuntimeError):
    pass


def _sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return json.load(f)


def load_manifest() -> dict:
    if not os.path.exists(MANIFEST_PATH):
        raise FileNotFoundError(
            f"{MANIFEST_PATH} missing — run `python3 revision_v3/src/data/build_manifest.py` first"
        )
    with open(MANIFEST_PATH) as f:
        return json.load(f)


def load_primary_dataset(verify_hash: bool = True) -> pd.DataFrame:
    """Returns the 2,190-row PRIMARY_EVALUATION population with stored family_id/fold_id.

    Raises CanonicalInputChanged if the benchmark file's SHA-256 no longer matches the
    recorded manifest (the manifest itself is never regenerated implicitly — a changed hash
    is always treated as an error, not silently re-baselined).
    """
    config = load_config()
    manifest = load_manifest()
    benchmark_path = os.path.join(REPO_ROOT, config["benchmark_csv_gz"])

    if verify_hash:
        current_hash = _sha256_of(benchmark_path)
        expected_hash = manifest["sha256"]["benchmark_csv_gz"]
        if current_hash != expected_hash:
            raise CanonicalInputChanged(
                f"canonical benchmark hash changed: expected {expected_hash}, got {current_hash}. "
                "Refusing to load — Revision v3 treats revision_v2 data as immutable."
            )

    df = pd.read_csv(benchmark_path)
    primary = df[df["population"] == "PRIMARY_EVALUATION"].reset_index(drop=True)

    exp = config["expected_population"]
    assert len(primary) == exp["primary_rows"], (len(primary), exp["primary_rows"])
    assert int((primary["label"] == 1).sum()) == exp["primary_positive"]
    assert int((primary["label"] == 0).sum()) == exp["primary_negative"]
    assert primary["family_id"].nunique() == exp["primary_families"]
    assert primary["fold_id"].nunique() == exp["n_folds"]

    return primary


def assert_no_family_cross_fold(df: pd.DataFrame) -> None:
    """Every family_id must map to exactly one fold_id (no family straddles folds)."""
    per_family_folds = df.groupby("family_id")["fold_id"].nunique()
    offenders = per_family_folds[per_family_folds > 1]
    if len(offenders) > 0:
        raise AssertionError(f"{len(offenders)} families straddle multiple folds: {list(offenders.index[:10])}")


def assert_no_exact_bytecode_cross_fold(df: pd.DataFrame) -> None:
    """Every exact bytecode hash must map to exactly one fold_id."""
    per_hash_folds = df.groupby("bytecode_sha256")["fold_id"].nunique()
    offenders = per_hash_folds[per_hash_folds > 1]
    if len(offenders) > 0:
        raise AssertionError(
            f"{len(offenders)} exact-bytecode groups straddle multiple folds: {list(offenders.index[:10])}"
        )


def assert_no_conflicting_exact_bytecode_label(df: pd.DataFrame) -> None:
    """Every exact bytecode hash must map to exactly one label within the primary population."""
    per_hash_labels = df.groupby("bytecode_sha256")["label"].nunique()
    offenders = per_hash_labels[per_hash_labels > 1]
    if len(offenders) > 0:
        raise AssertionError(
            f"{len(offenders)} exact-bytecode groups carry conflicting labels: {list(offenders.index[:10])}"
        )


def fold_split(df: pd.DataFrame, test_fold: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Stored-fold protocol: test=test_fold, val=(test_fold+1)%5, train=remaining 3 folds."""
    n_folds = int(df["fold_id"].nunique())
    val_fold = (test_fold + 1) % n_folds
    test_df = df[df["fold_id"] == test_fold]
    val_df = df[df["fold_id"] == val_fold]
    train_df = df[~df["fold_id"].isin([test_fold, val_fold])]
    assert len(set(test_df["family_id"]) & set(train_df["family_id"])) == 0
    assert len(set(test_df["family_id"]) & set(val_df["family_id"])) == 0
    assert len(set(val_df["family_id"]) & set(train_df["family_id"])) == 0
    return train_df.reset_index(drop=True), val_df.reset_index(drop=True), test_df.reset_index(drop=True)


if __name__ == "__main__":
    data = load_primary_dataset()
    print(f"[loader] loaded {len(data)} primary rows, {data['family_id'].nunique()} families, "
          f"{data['fold_id'].nunique()} folds")
    assert_no_family_cross_fold(data)
    assert_no_exact_bytecode_cross_fold(data)
    assert_no_conflicting_exact_bytecode_label(data)
    print("[loader] all leakage/isolation invariants PASS")
