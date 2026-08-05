from __future__ import annotations

from revision_v3.experiments.external_controls.freeze_final_legitimate_projects import (
    classification_gate,
)


def _eligible_record() -> dict:
    return {
        "classification": "NEW_PROJECT_INDEPENDENT_IMPLEMENTATION",
        "project_overlap_audit": "CONFIRMED_ABSENT_FROM_V2_AND_DEVELOPMENT_REGISTRIES",
        "v2_address_overlap": False,
        "v2_runtime_overlap": False,
        "development_address_overlap": False,
        "development_runtime_overlap": False,
        "primary_manifest_overlap": False,
        "reserve_manifest_overlap": False,
        "verified_source": True,
        "contract_name": "Expected",
        "expected_contract_name": "Expected",
        "runtime_bytecode_sha256": "a" * 64,
        "expected_runtime_sha256": "a" * 64,
        "actual_use_requirement": "OBSERVED_POSTCUTOFF_AUTHORIZATIONS",
        "authorization_count": 12,
        "historical_runtime_matches_live": True,
    }


def test_clean_new_project_passes_fail_closed_gate():
    eligible, reason = classification_gate(_eligible_record())
    assert eligible
    assert "eligible" in reason


def test_known_project_cannot_be_promoted_by_new_exact_runtime():
    record = _eligible_record()
    record["classification"] = "NEW_IMPLEMENTATION_KNOWN_PROJECT"
    eligible, reason = classification_gate(record)
    assert not eligible
    assert "not a new project" in reason


def test_any_protected_population_overlap_fails():
    for field in [
        "v2_address_overlap",
        "v2_runtime_overlap",
        "development_address_overlap",
        "development_runtime_overlap",
        "primary_manifest_overlap",
        "reserve_manifest_overlap",
    ]:
        record = _eligible_record()
        record[field] = True
        eligible, reason = classification_gate(record)
        assert not eligible, field
        assert "overlaps" in reason


def test_observed_use_stratum_requires_stable_runtime_and_nonzero_use():
    record = _eligible_record()
    record["authorization_count"] = 0
    eligible, reason = classification_gate(record)
    assert not eligible
    assert "authorization" in reason

    record = _eligible_record()
    record["historical_runtime_matches_live"] = False
    eligible, reason = classification_gate(record)
    assert not eligible
    assert "changed" in reason


def test_deployment_only_project_may_enter_only_declared_descriptive_stratum():
    record = _eligible_record()
    record["classification"] = "NEW_PROJECT_OFFICIAL_IMPLEMENTATION"
    record["actual_use_requirement"] = "OFFICIAL_DEPLOYMENT_ONLY"
    record["authorization_count"] = 0
    record["historical_runtime_matches_live"] = False
    eligible, _ = classification_gate(record)
    assert eligible
