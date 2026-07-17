#!/usr/bin/env python3
"""Verify every per-phase result-manifest SHA-256 against the current workspace."""
import csv
import glob
import hashlib
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    failures = []
    checked = 0
    pattern = os.path.join(ROOT, "revision_v2", "reports", "phase_*_results_manifest.csv")
    for manifest in sorted(glob.glob(pattern)):
        with open(manifest, newline="") as f:
            for row in csv.DictReader(f):
                path = os.path.join(ROOT, row["path"])
                checked += 1
                if not os.path.exists(path):
                    failures.append(f"MISSING {row['path']}")
                elif sha256(path) != row["sha256"]:
                    failures.append(f"HASH_MISMATCH {row['path']}")
    if failures:
        print("\n".join(failures), file=sys.stderr)
        raise SystemExit(1)
    print(f"OK: {checked} phase-manifest entries verified")


if __name__ == "__main__":
    main()
