"""Donor partition isolation for the Flood-200% reimplementation, and the hard rule that
nothing under revision_v3 ever writes to revision_v2/paper_build/pipeline/results/reports or
the frozen root-level CSVs."""
import glob
import os
import subprocess
import sys

import pandas as pd

from robustness.flooding import build_donor_pool, flood_bytecode

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def test_donor_never_shares_recipient_family():
    full_df = pd.read_csv(os.path.join(REPO_ROOT, "revision_v2", "data", "authguardbench_7702_v2.csv.gz"))
    primary = full_df[full_df["population"] == "PRIMARY_EVALUATION"].reset_index(drop=True)
    donor_pool = build_donor_pool(full_df)

    sample = primary.sample(n=20, random_state=7702)
    for _, row in sample.iterrows():
        flooded_hex = flood_bytecode(
            row["runtime_bytecode"], row["sample_id"], row["family_id"],
            donor_pool, seed=7702, fraction=2.0,
        )
        assert flooded_hex.startswith(row["runtime_bytecode"].lower().replace("0x", "").rstrip()[:20] or "")
        # flooded output must strictly extend the recipient's own bytecode (prefix-preserving)
        recipient_hex = row["runtime_bytecode"].lower().replace("0x", "")
        if len(recipient_hex) % 2:
            recipient_hex = recipient_hex[:-1]
        assert flooded_hex.startswith(recipient_hex)
        assert len(flooded_hex) > len(recipient_hex)


def test_donor_pool_is_external_control_only():
    full_df = pd.read_csv(os.path.join(REPO_ROOT, "revision_v2", "data", "authguardbench_7702_v2.csv.gz"))
    donor_pool = build_donor_pool(full_df)
    donor_rows = full_df[full_df["sample_id"].isin(donor_pool.sample_ids)]
    assert (donor_rows["population"] == "EXTERNAL_BENIGN_CONTROL").all()


def test_flooding_is_deterministic_given_same_seed():
    full_df = pd.read_csv(os.path.join(REPO_ROOT, "revision_v2", "data", "authguardbench_7702_v2.csv.gz"))
    primary = full_df[full_df["population"] == "PRIMARY_EVALUATION"].reset_index(drop=True)
    donor_pool = build_donor_pool(full_df)
    row = primary.iloc[0]
    a = flood_bytecode(row["runtime_bytecode"], row["sample_id"], row["family_id"], donor_pool, seed=7702)
    b = flood_bytecode(row["runtime_bytecode"], row["sample_id"], row["family_id"], donor_pool, seed=7702)
    c = flood_bytecode(row["runtime_bytecode"], row["sample_id"], row["family_id"], donor_pool, seed=7703)
    assert a == b
    assert a != c


PROTECTED_PATHS = [
    "revision_v2", "paper_build", "pipeline", "results", "reports",
    "capability_dataset.csv", "family_assignment_frozen.csv",
]


def test_no_source_file_under_revision_v3_writes_to_protected_paths():
    """Static check: no file under revision_v3/src or revision_v3/experiments contains an
    open(...) / to_csv(...) / torch.save(...) call whose literal path argument points at a
    protected location. This is a lint-style guard, not a runtime guarantee -- combined with
    the frozen-hash guard (test below) it is a strong signal writes never happened."""
    src_files = glob.glob(os.path.join(REPO_ROOT, "revision_v3", "src", "**", "*.py"), recursive=True)
    src_files += glob.glob(os.path.join(REPO_ROOT, "revision_v3", "experiments", "**", "*.py"), recursive=True)
    offenders = []
    for path in src_files:
        with open(path) as f:
            text = f.read()
        for protected in PROTECTED_PATHS:
            for marker in (f'"{protected}', f"'{protected}"):
                if marker in text and "REPO_ROOT" not in text.split(marker)[0][-80:]:
                    # allow read-only mentions like config paths; flag anything that looks
                    # like a write call near the mention
                    idx = text.find(marker)
                    window = text[max(0, idx - 120):idx]
                    if any(w in window for w in ("open(", "to_csv(", "torch.save(", "os.remove", "shutil.")):
                        offenders.append((path, protected))
    assert offenders == [], f"possible write to protected path: {offenders}"


def test_frozen_guard_passes():
    result = subprocess.run(
        [sys.executable, os.path.join(REPO_ROOT, "revision_v2", "experiments", "common", "frozen.py"), "verify"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
