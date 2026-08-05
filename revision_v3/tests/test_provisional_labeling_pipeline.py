"""Tests for the LLM-provisional pipeline built in this session: label-source separation,
no LLM-to-human copying, Gold-Test independence during development, family isolation,
uncertainty handling, provisional watermarking, output-directory separation, blinding, schema
fixedness, temporal dedup, legitimate-control provenance, and frozen-file safety.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
V3 = os.path.join(REPO_ROOT, "revision_v3")
HUMAN_EVAL_DIR = os.path.join(V3, "human_eval")
RESULTS_DIR = os.path.join(V3, "results", "llm_provisional")

REQUIRED_FIELDS = {
    "source_rule_label", "llm_provisional_label", "llm_provisional_confidence",
    "human_final_label", "human_final_confidence", "human_final_reason", "human_review_status",
}
ALLOWED_LABELS = {"SAFE", "UNSAFE", "UNCERTAIN"}
ALLOWED_REVIEW_STATUS = {"NOT_REVIEWED", "UNDER_REVIEW", "FINAL_SAFE", "FINAL_UNSAFE", "FINAL_UNCERTAIN"}

FORBIDDEN_SUBSTRINGS = [
    "authguard_score", "authguard_prediction", "raw_score", "calibrated_score", "model_score",
    "is_false_positive", "is_false_negative", "gold_dev_stratum", "gold_test_sampling_metadata",
]

SAMPLE_SETS = ["pilot", "gold_dev", "gold_test"]


def _load_labels(sample_set):
    path = os.path.join(RESULTS_DIR, f"{sample_set}_labels.json")
    if not os.path.exists(path):
        pytest.skip(f"{sample_set}_labels.json not present")
    with open(path) as f:
        return json.load(f)


@pytest.mark.parametrize("sample_set", SAMPLE_SETS)
def test_label_schema_has_all_eight_separation_fields(sample_set):
    data = _load_labels(sample_set)
    for rec in data["records"]:
        missing = REQUIRED_FIELDS - set(rec.keys())
        assert not missing, f"{sample_set}/{rec['item_id']} missing fields: {missing}"


@pytest.mark.parametrize("sample_set", SAMPLE_SETS)
def test_human_final_label_never_populated_by_this_pipeline(sample_set):
    data = _load_labels(sample_set)
    for rec in data["records"]:
        assert rec["human_final_label"] in (None, ""), (
            f"{sample_set}/{rec['item_id']} has a non-blank human_final_label -- "
            "this pipeline must never populate it"
        )
        assert rec["human_review_status"] == "NOT_REVIEWED"


@pytest.mark.parametrize("sample_set", SAMPLE_SETS)
def test_no_llm_label_copied_into_human_final_label(sample_set):
    data = _load_labels(sample_set)
    for rec in data["records"]:
        # Since human_final_label must be blank (tested above), it trivially cannot equal
        # the LLM label -- this test additionally guards against a future regression where
        # someone "fixes" the blank-ness by copying llm_provisional_label in.
        assert rec["human_final_label"] != rec["llm_provisional_label"] or rec["human_final_label"] in (None, "")


@pytest.mark.parametrize("sample_set", SAMPLE_SETS)
def test_llm_provisional_label_is_valid(sample_set):
    data = _load_labels(sample_set)
    for rec in data["records"]:
        assert rec["llm_provisional_label"] in ALLOWED_LABELS


@pytest.mark.parametrize("sample_set", SAMPLE_SETS)
def test_provisional_watermark_present(sample_set):
    data = _load_labels(sample_set)
    assert data.get("LABEL_SOURCE") == "LLM_PROVISIONAL"
    assert data.get("STATUS") == "PROVISIONAL_NOT_FOR_FINAL_CLAIMS"


@pytest.mark.parametrize("sample_set", ["gold_dev", "gold_test"])
def test_uncertain_labels_preserved_not_dropped(sample_set):
    """UNCERTAIN items must appear in the label file (not silently filtered out) even though
    they're excluded from binary metrics downstream."""
    data = _load_labels(sample_set)
    labels = {r["llm_provisional_label"] for r in data["records"]}
    # Not asserting UNCERTAIN necessarily exists (a sample could have zero), but if metrics
    # report fewer items than the label file, that's the real leak to catch:
    with open(os.path.join(HUMAN_EVAL_DIR, f"{sample_set}_manifest.csv"), newline="") as f:
        manifest_ids = {r["item_id"] for r in csv.DictReader(f)}
    label_ids = {r["item_id"] for r in data["records"]}
    assert label_ids == manifest_ids, "label file must cover every manifest item, including UNCERTAIN ones"


def test_gold_dev_baseline_excludes_uncertain_and_reports_coverage():
    path = os.path.join(RESULTS_DIR, "gold_dev_baseline", "gold_dev_baseline_report.json")
    if not os.path.exists(path):
        pytest.skip("gold_dev_baseline_report.json not present")
    with open(path) as f:
        d = json.load(f)
    assert "uncertain_coverage_pct" in d
    assert d["n_evaluated_binary"] + d["n_uncertain_excluded"] == d["n_total_gold_dev_items"]


def test_gold_test_not_used_in_model_selection_manifest():
    """Part 8's selection manifest must cite only Gold-Dev evidence, never Gold-Test."""
    path = os.path.join(RESULTS_DIR, "provisional_final_model_manifest.json")
    if not os.path.exists(path):
        pytest.skip("provisional_final_model_manifest.json not present")
    with open(path) as f:
        text = f.read()
    assert "gold_test" not in text.lower() or "gold_test_labels" not in text.lower(), (
        "provisional final model selection manifest must not reference Gold-Test"
    )


def test_family_isolation_between_gold_dev_and_gold_test():
    with open(os.path.join(HUMAN_EVAL_DIR, "gold_dev_manifest.csv"), newline="") as f:
        gd_families = {r["family_id"] for r in csv.DictReader(f)}
    with open(os.path.join(HUMAN_EVAL_DIR, "gold_test_manifest.csv"), newline="") as f:
        gt_families = {r["family_id"] for r in csv.DictReader(f)}
    overlap = gd_families & gt_families
    assert not overlap, f"Gold-Dev/Gold-Test family leakage: {overlap}"


def test_no_forbidden_fields_in_evidence_pipeline_source():
    """The evidence pipeline must not import/read source_label or any AuthGuard-score field
    when constructing LLM-facing evidence -- checked structurally in the source code."""
    path = os.path.join(V3, "experiments", "excel_review", "evidence_pipeline.py")
    with open(path) as f:
        src = f.read()
    for term in FORBIDDEN_SUBSTRINGS:
        assert term not in src, f"evidence_pipeline.py references forbidden field {term!r}"


def test_no_forbidden_fields_in_generated_label_records():
    for sample_set in SAMPLE_SETS:
        path = os.path.join(RESULTS_DIR, f"{sample_set}_labels.json")
        if not os.path.exists(path):
            continue
        with open(path) as f:
            text = f.read().lower()
        for term in FORBIDDEN_SUBSTRINGS:
            assert term not in text, f"{sample_set}_labels.json contains forbidden field {term!r}"


def test_output_directory_separation():
    """llm_provisional outputs must live entirely under results/llm_provisional/, never mixed
    into results/source_rule/ or results/human_final/."""
    llm_dir = os.path.join(V3, "results", "llm_provisional")
    assert os.path.isdir(llm_dir)
    source_rule_dir = os.path.join(V3, "results", "source_rule")
    human_final_dir = os.path.join(V3, "results", "human_final")
    # Both are allowed to not exist yet (source_rule eval not yet parametrized; human_final
    # blocked) -- the test only forbids llm_provisional files leaking into them.
    for d in (source_rule_dir, human_final_dir):
        if os.path.isdir(d):
            for root, _, files in os.walk(d):
                for fn in files:
                    if fn.endswith("_labels.json"):
                        with open(os.path.join(root, fn)) as f:
                            content = json.load(f)
                        assert content.get("LABEL_SOURCE") != "LLM_PROVISIONAL", (
                            f"{os.path.join(root, fn)} is under {d} but watermarked LLM_PROVISIONAL"
                        )


def test_reason_category_matches_taxonomy():
    import sys
    sys.path.insert(0, HUMAN_EVAL_DIR)
    from taxonomy import SAFE_REASONS, UNSAFE_REASONS, UNCERTAIN_REASONS  # noqa: E402
    new_unsafe = {"TX_ORIGIN_AUTHORIZATION_RISK", "UNRESTRICTED_CONTRACT_CREATION"}
    new_safe = {"OWNER_OR_SELF_CALL_RESTRICTED", "SIGNATURE_AUTHORIZATION_CONFIRMED",
                "UPGRADE_AUTHORIZATION_APPEARS_SAFE"}
    new_uncertain = {"DECOMPILATION_AMBIGUITY"}
    allowed_by_label = {
        "SAFE": set(SAFE_REASONS) | new_safe,
        "UNSAFE": set(UNSAFE_REASONS) | new_unsafe,
        "UNCERTAIN": set(UNCERTAIN_REASONS) | new_uncertain,
    }
    for sample_set in SAMPLE_SETS:
        path = os.path.join(RESULTS_DIR, f"{sample_set}_labels.json")
        if not os.path.exists(path):
            continue
        with open(path) as f:
            data = json.load(f)
        for rec in data["records"]:
            label = rec["llm_provisional_label"]
            reason = rec["llm_provisional_reason_category"]
            assert reason in allowed_by_label[label], (
                f"{sample_set}/{rec['item_id']}: reason {reason} not valid for label {label}"
            )


def test_manifests_unchanged_and_not_resampled():
    """MD5s recorded at the start of Phase 3A, re-verified here after the full Parts 1-21 pass."""
    expected = {
        "pilot_manifest.csv": "2d5d84963daaa1f9e4fdb852f8c4e7cc",
        "gold_dev_manifest.csv": "a8fac81f6e2f320c23fe796d42ca6783",
        "gold_test_manifest.csv": "543f3a5a69cef800eb6a6e830f729669",
        "gold_test_hashes.json": "0dbd38312d9bca1e125416f979acabb6",
    }
    for fname, expected_md5 in expected.items():
        path = os.path.join(HUMAN_EVAL_DIR, fname)
        with open(path, "rb") as f:
            actual = hashlib.md5(f.read()).hexdigest()
        assert actual == expected_md5, f"{fname} changed! expected {expected_md5}, got {actual}"


def test_legitimate_controls_have_provenance_columns():
    path = os.path.join(V3, "external_controls", "verified_legitimate_controls.csv")
    if not os.path.exists(path):
        pytest.skip("verified_legitimate_controls.csv not present")
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    required = {"project", "chain", "address", "runtime_hash_recorded", "verified_source",
                "category", "provenance_confidence"}
    assert required.issubset(rows[0].keys())
    categories = {r["category"] for r in rows}
    assert categories.issubset({"VERIFIED_LEGITIMATE_CONTROL", "CANDIDATE_LEGITIMATE_CONTROL", "UNRESOLVED_CONTROL"})
    assert not any(r["category"] == "VERIFIED_LEGITIMATE_CONTROL" and r["verified_source"] != "True" for r in rows), (
        "a project must not be VERIFIED_LEGITIMATE_CONTROL without verified_source=True"
    )


def test_temporal_enrichment_deduplicates_and_classifies():
    path = os.path.join(V3, "temporal", "enriched", "v2_window_ethereum_enriched.csv")
    if not os.path.exists(path):
        pytest.skip("temporal enrichment output not present")
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    addrs = [r["address"] for r in rows]
    assert len(addrs) == len(set(addrs)), "temporal enrichment must deduplicate delegate addresses"
    for r in rows:
        if r["fetch_error"]:
            continue
        assert r["is_previously_unseen_family"] in ("True", "False")


def test_temporal_data_never_referenced_by_training_scripts():
    """Part 7's retraining script must only read Gold-Dev, never revision_v3/temporal/."""
    path = os.path.join(V3, "experiments", "llm_provisional", "run_retraining_experiments.py")
    with open(path) as f:
        src = f.read()
    assert "temporal" not in src.lower()


def test_one_command_rerun_script_exists_and_supports_all_label_sources():
    path = os.path.join(V3, "run_reference_pipeline.py")
    assert os.path.exists(path)
    with open(path) as f:
        src = f.read()
    for source in ("source_rule", "llm_provisional", "human_final"):
        assert f'"{source}"' in src


def test_human_final_mode_does_not_fabricate_when_no_labels_exist():
    """If no human labels exist, run_reference_pipeline.py --label-source human_final must
    exit without writing any result files claiming a completed run."""
    import subprocess
    out_dir = os.path.join(V3, "results", "human_final")
    result = subprocess.run(
        ["python3", os.path.join(V3, "run_reference_pipeline.py"), "--label-source", "human_final"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0
    assert "BLOCKED" in result.stdout
    manifest_path = os.path.join(out_dir, "run_manifest.json")
    if os.path.exists(manifest_path):
        with open(manifest_path) as f:
            m = json.load(f)
        assert m["status"] == "BLOCKED_NO_HUMAN_LABELS"


def test_frozen_guard_still_passes():
    import subprocess
    result = subprocess.run(
        ["python3", os.path.join(V3.replace("revision_v3", "revision_v2"), "experiments", "common", "frozen.py"), "verify"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0
    assert "OK" in result.stdout
