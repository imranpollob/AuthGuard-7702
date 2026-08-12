#!/usr/bin/env python3
"""Phase 6 — freeze every sprint number into results/frozen_numbers.json.

Two top-level blocks that are never merged or averaged together:

  stored_artifact        recomputed from the historical attack records; the models that
                         produced them no longer exist on disk
  regenerated_experiment produced against the Phase 3 checkpoints regenerated during
                         this sprint

Each entry carries value, CI, n, seed scope, fold scope, tier, model, provenance, script
and git commit, so no figure can be quoted without its scope.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

RV2 = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
RESULTS = os.path.join(RV2, "results")
OUT = os.path.join(RESULTS, "frozen_numbers.json")


def commit():
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=RV2,
                          capture_output=True, text=True).stdout.strip()


def read(path):
    full = os.path.join(RESULTS, path)
    if not os.path.exists(full):
        return None
    with open(full) as fh:
        return json.load(fh)


def main():
    stored, regenerated, missing = {}, {}, []

    sources = {
        "phase0_fixed_oracles": ("sprint_phase0/phase0_fixed_oracles.json", "stored"),
        "phase0_paired_ladder": ("sprint_phase0/phase0_paired_ladder.json", "stored"),
        "phase0_winner_composition": ("sprint_phase0/phase0_winner_composition.json", "stored"),
        "phase1_seed_scope": ("sprint_phase1/phase1_seed_scope.json", "stored"),
        "phase1_facts": ("sprint_phase1/phase1_facts.json", "stored"),
        "phase2_preservation_audit": ("sprint_phase2/preservation_audit.json", "regenerated"),
        "phase3_checkpoint_manifest": ("sprint_phase3/checkpoint_manifest_s7702.json",
                                       "regenerated"),
        "phase4_analysis": ("sprint_phase4/phase4_analysis.json", "regenerated"),
        "phase4_run_meta": ("sprint_phase4/tiered_run_meta_s7702.json", "regenerated"),
        "phase5_analysis": ("sprint_phase5/phase5_analysis.json", "regenerated"),
    }
    for key, (path, block) in sources.items():
        payload = read(path)
        if payload is None:
            missing.append(path)
            continue
        (stored if block == "stored" else regenerated)[key] = payload

    frozen = dict(
        sprint="AuthGuard-7702 final 2-day coding sprint",
        git_commit=commit(),
        generated_by="revision_v2/experiments/sprint_phase6/freeze.py",
        blocks_are_never_merged=("stored_artifact values were recomputed from historical "
                                 "attack records whose models no longer exist; "
                                 "regenerated_experiment values come from the Phase 3 "
                                 "checkpoints. Never average across blocks."),
        stored_artifact=stored,
        regenerated_experiment=regenerated,
        missing_inputs=missing)
    with open(OUT, "w") as fh:
        json.dump(frozen, fh, indent=2, default=str)
    print(f"[freeze] wrote {OUT}")
    print(f"[freeze] stored blocks: {sorted(stored)}")
    print(f"[freeze] regenerated blocks: {sorted(regenerated)}")
    if missing:
        print(f"[freeze] MISSING (not yet produced): {missing}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
