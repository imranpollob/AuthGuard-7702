#!/usr/bin/env python3
"""Frozen-artifact SHA-256 guard for Revision v2.

Usage:
  python3 revision_v2/experiments/common/frozen.py build   # write ledger (run ONCE at Phase 0)
  python3 revision_v2/experiments/common/frozen.py verify  # exit 1 if any frozen file changed

The ledger covers every v1 evidence file and every frozen code module the v2 experiments
import. Any mismatch is a HARD STOP for the revision program.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
LEDGER = os.path.join(ROOT, "revision_v2", "audits", "frozen_ledger.json")

FROZEN_FILES = [
    "capability_dataset.csv",
    "family_assignment_frozen.csv",
    "advtrain_results.json",
    "paired_results.csv",
    "benign_7702_bytecode.csv",
    "independent_malicious.csv",
    "uncertain_candidates.csv",
    "unverified_candidates.csv",
    "run_all.sh",
    "DECISIONS.md",
    "RESULTS_README.md",
    "results_summary.md",
]

FROZEN_DIRS = [
    "results",
    "reports",
    "pipeline",
    "paper_build/data_hygiene",
    "paper_build/statistics",
    "paper_build/runtime",
    "paper_build/overleaf",
    "paper_build/tables",
    "paper_build/figures",
    "paper_build/sections",
]

SKIP_BASENAMES = {".DS_Store"}


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def enumerate_frozen() -> list[str]:
    out = []
    for rel in FROZEN_FILES:
        p = os.path.join(ROOT, rel)
        if os.path.exists(p):
            out.append(rel)
    for d in FROZEN_DIRS:
        base = os.path.join(ROOT, d)
        for dirpath, _dirnames, filenames in os.walk(base):
            for fn in sorted(filenames):
                if fn in SKIP_BASENAMES or fn.endswith(".pyc"):
                    continue
                rel = os.path.relpath(os.path.join(dirpath, fn), ROOT)
                if "__pycache__" in rel:
                    continue
                out.append(rel)
    return sorted(set(out))


def build() -> None:
    ledger = {rel: sha256(os.path.join(ROOT, rel)) for rel in enumerate_frozen()}
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    with open(LEDGER, "w") as f:
        json.dump(ledger, f, indent=2, sort_keys=True)
    print(f"[frozen] ledger written: {len(ledger)} files -> {LEDGER}")


def verify() -> int:
    with open(LEDGER) as f:
        ledger = json.load(f)
    bad, missing = [], []
    for rel, expected in ledger.items():
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            missing.append(rel)
        elif sha256(p) != expected:
            bad.append(rel)
    if bad or missing:
        for rel in bad:
            print(f"[frozen] MODIFIED: {rel}")
        for rel in missing:
            print(f"[frozen] MISSING:  {rel}")
        print("[frozen] HARD STOP: frozen artifacts changed")
        return 1
    print(f"[frozen] OK: {len(ledger)} frozen files verified unchanged")
    return 0


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "verify"
    if mode == "build":
        build()
    else:
        sys.exit(verify())
