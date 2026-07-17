#!/usr/bin/env python3
"""Refresh SHA-256 cells in existing per-phase report manifests.

Paths and roles are human-authored and never inferred here; this only prevents a documented
artifact from retaining a stale digest after an approved finalization edit.
"""
import csv
import glob
import hashlib
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    pattern = os.path.join(ROOT, "revision_v2", "reports", "phase_*_results_manifest.csv")
    refreshed = 0
    for manifest in sorted(glob.glob(pattern)):
        with open(manifest, newline="") as f:
            rows = list(csv.DictReader(f))
        for row in rows:
            path = os.path.join(ROOT, row["path"])
            if not os.path.isfile(path):
                raise SystemExit(f"missing report-manifest target: {row['path']}")
            row["sha256"] = sha256(path)
            refreshed += 1
        with open(manifest, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["path", "sha256", "role"],
                                    lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
    print(f"[refresh-report-manifests] refreshed {refreshed} entries")


if __name__ == "__main__":
    main()
