"""Fail-closed audit of submission claims against Revision v3 evidence gates.

This is not a prose-quality checker.  It catches claims that the current artifacts cannot
support and refuses a READY status until the two human-reviewed evaluation sets and the
post-cutoff retraining provenance chain are complete.
"""
from __future__ import annotations

import argparse
import csv
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
    path = root / "revision_v3" / "results" / "postcutoff_snapshot" / "postcutoff_project_family_audit.csv"
    try:
        with path.open(newline="") as handle:
            rows = list(csv.DictReader(handle))
    except OSError:
        return {"status": "MISSING", "path": str(path)}, _finding(
            "MISSING_PROJECT_FAMILY_AUDIT", f"Missing post-cutoff project-family audit: {path}"
        )
    # The holdout-plan validator's only admissible zero-exclusion terminal state is CONFIRMED.
    unresolved = [row for row in rows if row.get("provenance_status") != "CONFIRMED"]
    missing_project = [row for row in rows if not row.get("postcutoff_project_family_id", "").strip()]
    missing_evidence = [row for row in rows if not row.get("evidence_reference", "").strip()]
    summary = {
        "status": "COMPLETE" if rows and not unresolved and not missing_project and not missing_evidence else "INCOMPLETE",
        "path": str(path),
        "n_items": len(rows),
        "n_unresolved": len(unresolved),
        "n_missing_project_family": len(missing_project),
        "n_missing_evidence_reference": len(missing_evidence),
    }
    if summary["status"] != "COMPLETE":
        return summary, _finding(
            "INCOMPLETE_PROJECT_FAMILY_AUDIT",
            "Every locked post-cutoff item needs a resolved project-family ID and auditable "
            "evidence before leakage-safe retraining.",
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
    for sample_set in ("gold_test", "postcutoff"):
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
                "claim": "An authority-relative Delegation-Context Risk Graph that connects reachable sensitive capabilities to typed guard evidence while exposing bounded-analysis coverage.",
                "readiness": "Currently supported only against inherited rule-derived labels; authority-specific value remains a post-cutoff hypothesis.",
            },
            {
                "id": "C2",
                "claim": "A coverage-gated EIP-7702 pre-authorization decision contract that returns WARN, LOW_OBSERVED_RISK, or DEFER and forbids incomplete analysis from producing low risk.",
                "readiness": "The invariant is implemented; empirical usefulness requires final selective-risk results and honest reporting of deferral and false warnings.",
            },
            {
                "id": "C3",
                "claim": "A provenance-audited evaluation protocol combining family-disjoint training-era tests, legitimate project controls, and frozen post-cutoff authority/delegate pairs with pre-label retraining and project-family uncertainty.",
                "readiness": "FINAL only after both human-review sets, the project audit, and the post-cutoff retraining freeze are complete.",
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
        lines.extend([f"- **{item['id']}:** {item['claim']}  ", f"  Readiness: {item['readiness']}"])
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
