# Submission Claim Audit

Status: **BLOCKED_UNSUPPORTED_OR_INCOMPLETE_CLAIMS**

Blocking findings: **20**

## Target contributions

- **C1:** A leakage-reduced evaluation resource for bytecode-only EIP-7702 pre-authorization screening, with temporal/research-family holds, explicit indeterminacy, and independently adjudicated labels.
  Readiness: Conservative non-attribution family holds and pre-label scoring are complete; FINAL only after dual review, adjudication, and agreement reporting.
- **C2:** A coverage-audited, guard-aware Delegation-Context representation linking reachable capabilities to typed guard evidence while preserving unresolved control flow.
  Readiness: Extractor validity is supported; representation superiority requires the preregistered full-minus-untyped interval on untouched human labels.
- **C3:** A deployment-realistic warning/NO_MODEL_WARNING/DEFER evaluation across real signer/delegate pairs and wholly new legitimate projects, without a safety-certification claim.
  Readiness: The weight-8 repair, decision contract, and three-project external evaluation are frozen; post-cutoff human outcomes remain pending.

## Findings

- **BLOCK UNVERIFIED_PRIORITY_CLAIM** (line 39): Replace priority language with a scoped contrast to named closest work, unless a documented systematic search supports it.
- **BLOCK STALE_V2_METRIC** (line 39): This value belongs to the superseded v2 evaluation; regenerate the table from the frozen v3 result artifacts.
- **BLOCK STALE_V2_PARAMETER_COUNT** (line 39): The manuscript still describes the superseded v2 architecture.
- **BLOCK UNSUPPORTED_GLOBAL_BASELINE_CLAIM** (line 39): Name the comparator, endpoint, population, and uncertainty interval; do not convert a benchmark ordering into a global superiority claim.
- **BLOCK DEPLOYMENT_OR_SAFETY_OVERCLAIM** (line 39): Describe a bounded advisory triage result; latency and retrospective accuracy do not establish deployment safety.
- **BLOCK STALE_V2_METRIC** (line 62): This value belongs to the superseded v2 evaluation; regenerate the table from the frozen v3 result artifacts.
- **BLOCK UNVERIFIED_PRIORITY_CLAIM** (line 66): Replace priority language with a scoped contrast to named closest work, unless a documented systematic search supports it.
- **BLOCK STALE_V2_PARAMETER_COUNT** (line 67): The manuscript still describes the superseded v2 architecture.
- **BLOCK UNSUPPORTED_GLOBAL_BASELINE_CLAIM** (line 67): Name the comparator, endpoint, population, and uncertainty interval; do not convert a benchmark ordering into a global superiority claim.
- **BLOCK STALE_V2_PARAMETER_COUNT** (line 228): The manuscript still describes the superseded v2 architecture.
- **BLOCK STALE_V2_PARAMETER_COUNT** (line 316): The manuscript still describes the superseded v2 architecture.
- **BLOCK STALE_V2_PARAMETER_COUNT** (line 319): The manuscript still describes the superseded v2 architecture.
- **BLOCK STALE_V2_PARAMETER_COUNT** (line 321): The manuscript still describes the superseded v2 architecture.
- **BLOCK STALE_V2_METRIC** (line 349): This value belongs to the superseded v2 evaluation; regenerate the table from the frozen v3 result artifacts.
- **BLOCK STALE_V2_METRIC** (line 387): This value belongs to the superseded v2 evaluation; regenerate the table from the frozen v3 result artifacts.
- **BLOCK STALE_V2_METRIC** (line 425): This value belongs to the superseded v2 evaluation; regenerate the table from the frozen v3 result artifacts.
- **BLOCK STALE_V2_PARAMETER_COUNT** (line 432): The manuscript still describes the superseded v2 architecture.
- **BLOCK STALE_V2_METRIC** (line 453): This value belongs to the superseded v2 evaluation; regenerate the table from the frozen v3 result artifacts.
- **BLOCK UNSUPPORTED_GLOBAL_BASELINE_CLAIM** (line 453): Name the comparator, endpoint, population, and uncertainty interval; do not convert a benchmark ordering into a global superiority claim.
- **BLOCK INCOMPLETE_HUMAN_AGREEMENT**: postcutoff requires two independent primary reviews per item and adjudication of every disagreement; observed status is NOT_READY_DUAL_REVIEW_OR_ADJUDICATION_INCOMPLETE.

## Evidence gates

```json
{
  "postcutoff_agreement": {
    "n_exactly_dual_reviewed": 0,
    "n_manifest_items": 150,
    "n_pending_adjudications": 0,
    "path": "/home/pollmix/Coding/AuthGuard-7702/revision_v3/results/human_final/postcutoff_agreement_status.json",
    "status": "NOT_READY_DUAL_REVIEW_OR_ADJUDICATION_INCOMPLETE"
  },
  "postcutoff_retraining": {
    "review_unlock": "/home/pollmix/Coding/AuthGuard-7702/revision_v3/results/postcutoff_snapshot/postcutoff_review_unlock.json",
    "status": "COMPLETE",
    "training_manifest": "/home/pollmix/Coding/AuthGuard-7702/revision_v3/results/postcutoff_retraining/postcutoff_training_manifest.json"
  },
  "project_family_audit": {
    "claim_boundary": "Anonymous clusters authorize conservative retraining holds only. They are not brand attribution, proof of project independence, or security labels.",
    "counts_match": true,
    "hashes_match": true,
    "holdout_plan": "/home/pollmix/Coding/AuthGuard-7702/revision_v3/results/postcutoff_snapshot/postcutoff_family_holdout_plan.json",
    "n_confirmed": 1,
    "n_conservative_clusters": 148,
    "n_excluded": 1,
    "n_invalid_conservative": 0,
    "n_invalid_exclusions": 0,
    "n_invalid_supported": 0,
    "n_invalid_terminal": 0,
    "n_items": 150,
    "path": "/home/pollmix/Coding/AuthGuard-7702/revision_v3/results/postcutoff_snapshot/postcutoff_project_family_audit_conservative_v1.csv",
    "report": "/home/pollmix/Coding/AuthGuard-7702/revision_v3/results/postcutoff_snapshot/postcutoff_conservative_family_hold_report.json",
    "status": "COMPLETE_CONSERVATIVE_RETRAINING_HOLDS"
  }
}
```
