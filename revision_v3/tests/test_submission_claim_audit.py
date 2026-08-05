from __future__ import annotations

import csv
import hashlib
import importlib.util
import json


def _load_module():
    path = __file__.replace(
        "tests/test_submission_claim_audit.py",
        "experiments/reporting/audit_submission_claims.py",
    )
    spec = importlib.util.spec_from_file_location("submission_claim_audit", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


audit = _load_module()


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _complete_evidence(root):
    human = root / "revision_v3/results/human_final"
    post = root / "revision_v3/results/postcutoff_snapshot"
    training = root / "revision_v3/results/postcutoff_retraining"
    human.mkdir(parents=True)
    post.mkdir(parents=True)
    training.mkdir(parents=True)
    agreement = {
        "status": "COMPLETE_DUAL_REVIEW_AND_ADJUDICATION",
        "n_manifest_items": 1,
        "n_exactly_dual_reviewed": 1,
        "n_pending_adjudications": 0,
    }
    for sample in ("gold_test", "postcutoff"):
        (human / f"{sample}_agreement_status.json").write_text(json.dumps(agreement))
    with (post / "postcutoff_project_family_audit.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "item_id", "postcutoff_project_family_id", "provenance_status",
            "evidence_reference",
        ])
        writer.writeheader()
        writer.writerow({
            "item_id": "a", "postcutoff_project_family_id": "P1",
            "provenance_status": "CONFIRMED", "evidence_reference": "https://example.test",
        })
    (training / "postcutoff_training_manifest.json").write_text(json.dumps({
        "status": "FROZEN_POSTCUTOFF_RETRAINING_COMPLETE",
        "method_frozen_before_postcutoff_labels": True,
        "postcutoff_labels_accessed": False,
    }))
    (post / "postcutoff_review_unlock.json").write_text(json.dumps({
        "status": "POSTCUTOFF_REVIEW_UNLOCKED_AFTER_SCORING_FREEZE",
    }))


def test_claim_audit_passes_scoped_text_with_complete_evidence(tmp_path):
    _complete_evidence(tmp_path)
    tex = tmp_path / "main.tex"
    tex.write_text(
        "We evaluate a bounded triage method against named comparators under "
        "project-family-disjoint evaluation."
    )
    report = audit.audit_submission(tex, tmp_path)
    assert report["status"] == "READY_FOR_SUBMISSION_CLAIMS"
    assert report["n_blockers"] == 0


def test_claim_audit_flags_priority_stale_metrics_and_missing_evidence(tmp_path):
    tex = tmp_path / "main.tex"
    tex.write_text(
        "AuthGuard is the first machine-learning framework. It achieves 0.924 AUPRC, "
        "ranking first and establishing a practical system."
    )
    report = audit.audit_submission(tex, tmp_path)
    codes = {finding["code"] for finding in report["findings"]}
    assert report["status"] == "BLOCKED_UNSUPPORTED_OR_INCOMPLETE_CLAIMS"
    assert "UNVERIFIED_PRIORITY_CLAIM" in codes
    assert "STALE_V2_METRIC" in codes
    assert "UNSUPPORTED_GLOBAL_BASELINE_CLAIM" in codes
    assert "MISSING_HUMAN_AGREEMENT" in codes


def test_claim_audit_ignores_commented_out_claims(tmp_path):
    _complete_evidence(tmp_path)
    tex = tmp_path / "main.tex"
    tex.write_text("% the first machine-learning framework with 0.924 AUPRC\nScoped result.\n")
    report = audit.audit_submission(tex, tmp_path)
    assert report["status"] == "READY_FOR_SUBMISSION_CLAIMS"


def test_claim_audit_does_not_invert_explicit_safety_limitation(tmp_path):
    _complete_evidence(tmp_path)
    tex = tmp_path / "main.tex"
    tex.write_text("The advisory score does not certify authorization safety.\n")
    report = audit.audit_submission(tex, tmp_path)
    assert report["status"] == "READY_FOR_SUBMISSION_CLAIMS"


def test_claim_audit_accepts_documented_prelabel_provenance_exclusion(tmp_path):
    _complete_evidence(tmp_path)
    path = tmp_path / "revision_v3/results/postcutoff_snapshot/postcutoff_project_family_audit.csv"
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "item_id", "postcutoff_project_family_id", "provenance_status",
            "evidence_reference", "auditor_id", "exclusion_reason",
        ])
        writer.writeheader()
        writer.writerow({
            "item_id": "a", "postcutoff_project_family_id": "PF_DEV",
            "provenance_status": "EXCLUDED", "evidence_reference": "https://example.test",
            "auditor_id": "A1", "exclusion_reason": "USED_DURING_METHOD_DEVELOPMENT",
        })
    tex = tmp_path / "main.tex"
    tex.write_text("We report a bounded warning triage evaluation.")
    report = audit.audit_submission(tex, tmp_path)
    assert report["status"] == "READY_FOR_SUBMISSION_CLAIMS"


def test_claim_audit_accepts_hash_bound_nonattribution_conservative_holds(tmp_path):
    _complete_evidence(tmp_path)
    post = tmp_path / "revision_v3/results/postcutoff_snapshot"
    training = tmp_path / "revision_v3/results/postcutoff_retraining"
    conservative = post / "postcutoff_project_family_audit_conservative_v1.csv"
    with conservative.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "item_id", "postcutoff_project_family_id", "provenance_status",
            "evidence_reference", "evidence_notes", "auditor_id", "exclusion_reason",
        ])
        writer.writeheader()
        writer.writerow({
            "item_id": "a", "postcutoff_project_family_id": "PF_ANON_A",
            "provenance_status": "CONSERVATIVE_CLUSTER",
            "evidence_reference": "artifact:score-blind-linkage#A",
            "evidence_notes": "NO_BRAND_OWNERSHIP_CLAIM; overinclusive hold",
            "auditor_id": "CONSERVATIVE_PIPELINE", "exclusion_reason": "",
        })
    report = post / "postcutoff_conservative_family_hold_report.json"
    report.write_text(json.dumps({
        "status": "SCORE_BLIND_CONSERVATIVE_FAMILY_HOLD_AUDIT_MATERIALIZED",
        "audit_sha256": _sha(conservative), "n_items": 1,
        "status_counts": {"CONFIRMED": 0, "CONSERVATIVE_CLUSTER": 1, "EXCLUDED": 0},
        "claim_boundary": "Anonymous clusters authorize holds only; no brand attribution.",
    }))
    plan = post / "postcutoff_family_holdout_plan.json"
    plan.write_text(json.dumps({
        "status": "READY_FOR_PROJECT_FAMILY_RETRAINING_HOLDS",
        "audit_sha256": _sha(conservative),
    }))
    training_manifest = json.loads((training / "postcutoff_training_manifest.json").read_text())
    training_manifest["holdout_plan_sha256"] = _sha(plan)
    (training / "postcutoff_training_manifest.json").write_text(json.dumps(training_manifest))
    tex = tmp_path / "main.tex"
    tex.write_text("We report a leakage-reduced bounded warning triage evaluation.")
    result = audit.audit_submission(tex, tmp_path)
    assert result["status"] == "READY_FOR_SUBMISSION_CLAIMS"
    assert result["evidence_gates"]["project_family_audit"]["status"] == (
        "COMPLETE_CONSERVATIVE_RETRAINING_HOLDS"
    )
