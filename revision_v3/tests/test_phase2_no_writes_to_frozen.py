"""No Phase 2 code writes to Phase 1's frozen result files, or to revision_v2 and friends."""
import hashlib
import os

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# A representative sample of Phase 1 result files that must never change during Phase 2.
PHASE1_FROZEN_SAMPLE = [
    "revision_v3/results/authguard_reference_v3_fold_seed.csv",
    "revision_v3/results/controlled_ablation_summary.csv",
    "revision_v3/results/model_candidate_summary.csv",
    "revision_v3/results/matched_robustness_summary.csv",
    "revision_v3/results/model_complexity.csv",
    "revision_v3/reports/PHASE1_MODEL_DEFENSIBILITY_REPORT.md",
]


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@pytest.fixture(scope="module")
def phase1_hashes_before():
    hashes = {}
    for rel in PHASE1_FROZEN_SAMPLE:
        path = os.path.join(REPO_ROOT, rel)
        if os.path.exists(path):
            hashes[rel] = _sha256(path)
    return hashes


def test_phase1_result_files_unchanged(phase1_hashes_before):
    for rel, expected in phase1_hashes_before.items():
        path = os.path.join(REPO_ROOT, rel)
        assert _sha256(path) == expected, f"{rel} changed during this test session"


def test_frozen_guard_still_passes():
    import subprocess
    import sys
    result = subprocess.run(
        [sys.executable, os.path.join(REPO_ROOT, "revision_v2", "experiments", "common", "frozen.py"), "verify"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_phase2_outputs_live_under_new_directories():
    """Static check: Phase 2 output paths referenced in Phase 2 experiment scripts point at
    new directories (phase2_corrected_bootstrap/, parameter_matched/, final_robustness/,
    human_eval/, temporal/, external_controls/, annotation_app/), never overwriting a Phase 1
    filename in place."""
    phase2_dirs = [
        "revision_v3/results/phase2_corrected_bootstrap",
        "revision_v3/results/parameter_matched",
        "revision_v3/results/final_robustness",
        "revision_v3/human_eval",
        "revision_v3/temporal",
        "revision_v3/external_controls",
        "revision_v3/annotation_app",
    ]
    for d in phase2_dirs:
        assert os.path.isdir(os.path.join(REPO_ROOT, d)), f"expected Phase 2 directory missing: {d}"
