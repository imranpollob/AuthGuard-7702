"""Fail-closed audit of submission claims against Revision v3 evidence gates.

This is not a prose-quality checker.  It catches claims that the current artifacts cannot
support and refuses a READY status until the preregistered post-cutoff human evaluation and
retraining provenance chain are complete. Gold-Test is development evidence and is not allowed
to become a second confirmatory gate after its provisional labels informed method selection.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]

CLAIM_RULES = (
    (
        "UNVERIFIED_PRIORITY_CLAIM",
        re.compile(r"\b(first|the first)\s+machine[- ]learning\s+(framework|system|method)", re.I),
        "Replace priority language with a scoped contrast to named closest work, unless a "
        "documented systematic search supports it.",
    ),
    (
        "STALE_V2_METRIC",
        re.compile(r"\b(?:0\.924|0\.833|0\.963|0\.072|4\.121)\b"),
        "This value belongs to the superseded v2 evaluation; regenerate the table from the "
        "frozen v3 result artifacts.",
    ),
    (
        "STALE_V2_PARAMETER_COUNT",
        re.compile(r"\b181[, ]?877\b"),
        "The manuscript still describes the superseded v2 architecture.",
    ),
    (
        "UNSUPPORTED_GLOBAL_BASELINE_CLAIM",
        re.compile(r"\b(ranking first|outperforms? (?:all|six|every)|state[- ]of[- ]the[- ]art)\b", re.I),
        "Name the comparator, endpoint, population, and uncertainty interval; do not convert "
        "a benchmark ordering into a global superiority claim.",
    ),
    (
        "DEPLOYMENT_OR_SAFETY_OVERCLAIM",
        re.compile(
            r"\b(establish(?:es|ed)? .*\bpractical|secure blockchain account delegation|"
            r"certif(?:y|ies|ied) (?:authorization )?safety|production[- ]ready)\b",
            re.I,
        ),
        "Describe a bounded advisory triage result; latency and retrospective accuracy do "
        "not establish deployment safety.",
    ),
)


def _json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _finding(code: str, message: str, *, severity: str = "BLOCK", **extra) -> dict:
    return {"severity": severity, "code": code, "message": message, **extra}


def _claim_findings(tex_path: Path) -> list[dict]:
    lines = tex_path.read_text(errors="replace").splitlines()
    findings: list[dict] = []
    for line_number, line in enumerate(lines, start=1):
        if line.lstrip().startswith("%"):
            continue
        for code, pattern, remediation in CLAIM_RULES:
            matches = list(pattern.finditer(line))
            if code == "DEPLOYMENT_OR_SAFETY_OVERCLAIM":
                matches = [
                    match for match in matches
                    if not re.search(
                        r"\b(?:no|not|never|cannot|does not|do not)\b[^.;:]{0,80}$",
                        line[max(0, match.start() - 100):match.start()],
                        re.I,
                    )
                ]
            if matches:
                findings.append(_finding(
                    code,
                    remediation,
                    source=str(tex_path),
                    line=line_number,
                    excerpt=line.strip()[:300],
                ))
    return findings


def _agreement_gate(root: Path, sample_set: str) -> tuple[dict, dict]:
    path = root / "revision_v3" / "results" / "human_final" / f"{sample_set}_agreement_status.json"
    report = _json(path)
    expected = "COMPLETE_DUAL_REVIEW_AND_ADJUDICATION"
    if report is None:
        return {"status": "MISSING", "path": str(path)}, _finding(
            "MISSING_HUMAN_AGREEMENT", f"Missing {sample_set} agreement report: {path}"
        )
    observed = str(report.get("status", "MISSING"))
    summary = {
        "status": observed,
        "path": str(path),
        "n_manifest_items": report.get("n_manifest_items"),
        "n_exactly_dual_reviewed": report.get("n_exactly_dual_reviewed"),
        "n_pending_adjudications": report.get("n_pending_adjudications"),
    }
    if observed != expected:
        return summary, _finding(
            "INCOMPLETE_HUMAN_AGREEMENT",
            f"{sample_set} requires two independent primary reviews per item and adjudication "
            f"of every disagreement; observed status is {observed}.",
        )
    return summary, {}


def _project_family_gate(root: Path) -> tuple[dict, dict]:
    base = root / "revision_v3" / "results" / "postcutoff_snapshot"
    conservative_path = base / "postcutoff_project_family_audit_conservative_v1.csv"
    conservative_report_path = base / "postcutoff_conservative_family_hold_report.json"
    holdout_plan_path = base / "postcutoff_family_holdout_plan.json"
    training_manifest_path = (
        root / "revision_v3" / "results" / "postcutoff_retraining"
        / "postcutoff_training_manifest.json"
    )
    conservative_report = _json(conservative_report_path)
    holdout_plan = _json(holdout_plan_path)
    training_manifest = _json(training_manifest_path)
    if conservative_report is not None:
        try:
            with conservative_path.open(newline="") as handle:
                rows = list(csv.DictReader(handle))
        except OSError:
            rows = []
        confirmed = [row for row in rows if row.get("provenance_status") == "CONFIRMED"]
        conservative = [
            row for row in rows if row.get("provenance_status") == "CONSERVATIVE_CLUSTER"
        ]
        excluded = [row for row in rows if row.get("provenance_status") == "EXCLUDED"]
        invalid_terminal = [
            row for row in rows
            if row.get("provenance_status") not in {
                "CONFIRMED", "CONSERVATIVE_CLUSTER", "EXCLUDED"
            }
        ]
        invalid_supported = [
            row for row in confirmed + conservative
            if not row.get("postcutoff_project_family_id", "").strip()
            or not row.get("evidence_reference", "").strip()
            or not row.get("auditor_id", "").strip()
        ]
        invalid_conservative = [
            row for row in conservative
            if "NO_BRAND_OWNERSHIP_CLAIM" not in row.get("evidence_notes", "")
        ]
        invalid_exclusions = [
            row for row in excluded
            if not row.get("auditor_id", "").strip()
            or not row.get("exclusion_reason", "").strip()
        ]
        hashes_match = bool(
            rows
            and conservative_report.get("audit_sha256") == _sha256_file(conservative_path)
            and holdout_plan is not None
            and holdout_plan.get("status") == "READY_FOR_PROJECT_FAMILY_RETRAINING_HOLDS"
            and holdout_plan.get("audit_sha256") == conservative_report.get("audit_sha256")
            and training_manifest is not None
            and training_manifest.get("holdout_plan_sha256") == _sha256_file(holdout_plan_path)
        )
        counts_match = bool(
            len(rows) == conservative_report.get("n_items")
            and len(confirmed) == conservative_report.get("status_counts", {}).get("CONFIRMED")
            and len(conservative) == conservative_report.get("status_counts", {}).get(
                "CONSERVATIVE_CLUSTER"
            )
            and len(excluded) == conservative_report.get("status_counts", {}).get("EXCLUDED")
        )
        okay = bool(
            rows and conservative_report.get("status")
            == "SCORE_BLIND_CONSERVATIVE_FAMILY_HOLD_AUDIT_MATERIALIZED"
            and hashes_match and counts_match and not invalid_terminal
            and not invalid_supported and not invalid_conservative and not invalid_exclusions
        )
        summary = {
            "status": (
                "COMPLETE_CONSERVATIVE_RETRAINING_HOLDS" if okay else "INCOMPLETE"
            ),
            "path": str(conservative_path),
            "report": str(conservative_report_path),
            "holdout_plan": str(holdout_plan_path),
            "n_items": len(rows),
            "n_confirmed": len(confirmed),
            "n_conservative_clusters": len(conservative),
            "n_excluded": len(excluded),
            "n_invalid_terminal": len(invalid_terminal),
            "n_invalid_supported": len(invalid_supported),
            "n_invalid_conservative": len(invalid_conservative),
            "n_invalid_exclusions": len(invalid_exclusions),
            "hashes_match": hashes_match,
            "counts_match": counts_match,
            "claim_boundary": conservative_report.get("claim_boundary"),
        }
        if okay:
            return summary, {}
        return summary, _finding(
            "INCOMPLETE_CONSERVATIVE_FAMILY_HOLDS",
            "Conservative anonymous research-family holds must be terminal, evidence-linked, "
            "explicitly non-attributional, hash-bound to the hold plan, and consumed by the "
            "frozen retraining manifest.",
        )

    path = base / "postcutoff_project_family_audit.csv"
    try:
        with path.open(newline="") as handle:
            rows = list(csv.DictReader(handle))
    except OSError:
        return {"status": "MISSING", "path": str(path)}, _finding(
            "MISSING_PROJECT_FAMILY_AUDIT", f"Missing post-cutoff project-family audit: {path}"
        )
    unresolved = [
        row for row in rows
        if row.get("provenance_status") not in {"CONFIRMED", "EXCLUDED"}
    ]
    confirmed = [row for row in rows if row.get("provenance_status") == "CONFIRMED"]
    excluded = [row for row in rows if row.get("provenance_status") == "EXCLUDED"]
    missing_project = [
        row for row in confirmed
        if not row.get("postcutoff_project_family_id", "").strip()
    ]
    missing_evidence = [
        row for row in confirmed if not row.get("evidence_reference", "").strip()
    ]
    invalid_exclusions = [
        row for row in excluded
        if not row.get("auditor_id", "").strip()
        or not row.get("exclusion_reason", "").strip()
    ]
    summary = {
        "status": "COMPLETE" if rows and not unresolved and not missing_project and not missing_evidence else "INCOMPLETE",
        "path": str(path),
        "n_items": len(rows),
        "n_unresolved": len(unresolved),
        "n_missing_project_family": len(missing_project),
        "n_missing_evidence_reference": len(missing_evidence),
        "n_excluded": len(excluded),
        "n_invalid_exclusions": len(invalid_exclusions),
    }
    if invalid_exclusions:
        summary["status"] = "INCOMPLETE"
    if summary["status"] != "COMPLETE":
        return summary, _finding(
            "INCOMPLETE_PROJECT_FAMILY_AUDIT",
            "Every locked post-cutoff item must be either a provenance-confirmed project-family "
            "member or a documented pre-label exclusion before leakage-safe retraining.",
        )
    return summary, {}


def _postcutoff_training_gate(root: Path) -> tuple[dict, dict]:
    base = root / "revision_v3" / "results"
    manifest_path = base / "postcutoff_retraining" / "postcutoff_training_manifest.json"
    unlock_path = base / "postcutoff_snapshot" / "postcutoff_review_unlock.json"
    manifest = _json(manifest_path)
    unlock = _json(unlock_path)
    okay = (
        manifest is not None
        and manifest.get("status") == "FROZEN_POSTCUTOFF_RETRAINING_COMPLETE"
        and manifest.get("method_frozen_before_postcutoff_labels") is True
        and manifest.get("postcutoff_labels_accessed") is False
        and unlock is not None
        and unlock.get("status") == "POSTCUTOFF_REVIEW_UNLOCKED_AFTER_SCORING_FREEZE"
    )
    summary = {
        "status": "COMPLETE" if okay else "INCOMPLETE",
        "training_manifest": str(manifest_path),
        "review_unlock": str(unlock_path),
    }
    if not okay:
        return summary, _finding(
            "POSTCUTOFF_RETRAINING_NOT_FROZEN",
            "Complete the project-family holds, retrain, freeze checkpoints and label-free "
            "predictions, and create the verified review unlock before human review.",
        )
    return summary, {}


def audit_submission(tex_path: str | os.PathLike[str], repo_root: str | os.PathLike[str] = REPO_ROOT) -> dict:
    tex = Path(tex_path).resolve()
    root = Path(repo_root).resolve()
    findings = _claim_findings(tex)
    evidence: dict[str, dict] = {}
    for name, gate in (
        ("project_family_audit", _project_family_gate),
        ("postcutoff_retraining", _postcutoff_training_gate),
    ):
        evidence[name], finding = gate(root)
        if finding:
            findings.append(finding)
    for sample_set in ("postcutoff",):
        evidence[f"{sample_set}_agreement"], finding = _agreement_gate(root, sample_set)
        if finding:
            findings.append(finding)

    blockers = [finding for finding in findings if finding["severity"] == "BLOCK"]
    return {
        "status": "READY_FOR_SUBMISSION_CLAIMS" if not blockers else "BLOCKED_UNSUPPORTED_OR_INCOMPLETE_CLAIMS",
        "tex_path": str(tex),
        "n_blockers": len(blockers),
        "findings": findings,
        "evidence_gates": evidence,
        "target_contributions": [
            {
                "id": "C1",
                "claim": "A leakage-reduced evaluation resource for bytecode-only EIP-7702 pre-authorization screening, with temporal/research-family holds, explicit indeterminacy, and independently adjudicated labels.",
                "readiness": "Conservative non-attribution family holds and pre-label scoring are complete; FINAL only after dual review, adjudication, and agreement reporting.",
            },
            {
                "id": "C2",
                "claim": "A coverage-audited, guard-aware Delegation-Context representation linking reachable capabilities to typed guard evidence while preserving unresolved control flow.",
                "readiness": "Extractor validity is supported; representation superiority requires the preregistered full-minus-untyped interval on untouched human labels.",
            },
            {
                "id": "C3",
                "claim": "A deployment-realistic warning/NO_MODEL_WARNING/DEFER evaluation across real signer/delegate pairs and wholly new legitimate projects, without a safety-certification claim.",
                "readiness": "The weight-8 repair, decision contract, and three-project external evaluation are frozen; post-cutoff human outcomes remain pending.",
            },
        ],
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# Submission Claim Audit",
        "",
        f"Status: **{report['status']}**",
        "",
        f"Blocking findings: **{report['n_blockers']}**",
        "",
        "## Target contributions",
        "",
    ]
    for item in report["target_contributions"]:
        lines.extend([
            f"- **{item['id']}:** {item['claim']}",
            f"  Readiness: {item['readiness']}",
        ])
    lines.extend(["", "## Findings", ""])
    if not report["findings"]:
        lines.append("No blocking claim/evidence mismatch detected.")
    for finding in report["findings"]:
        location = ""
        if "line" in finding:
            location = f" (line {finding['line']})"
        lines.append(f"- **{finding['severity']} {finding['code']}**{location}: {finding['message']}")
    lines.extend(["", "## Evidence gates", "", "```json", json.dumps(report["evidence_gates"], indent=2, sort_keys=True), "```", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("tex_path")
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--json-output")
    parser.add_argument("--markdown-output")
    args = parser.parse_args()
    report = audit_submission(args.tex_path, args.repo_root)
    if args.json_output:
        Path(args.json_output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if args.markdown_output:
        Path(args.markdown_output).write_text(render_markdown(report))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "READY_FOR_SUBMISSION_CLAIMS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
