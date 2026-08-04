# Submission Claim Audit

Status: **BLOCKED_UNSUPPORTED_OR_INCOMPLETE_CLAIMS**

Blocking findings: **23**

## Target contributions

- **C1:** An authority-relative Delegation-Context Risk Graph that connects reachable sensitive capabilities to typed guard evidence while exposing bounded-analysis coverage.  
  Readiness: Currently supported only against inherited rule-derived labels; authority-specific value remains a post-cutoff hypothesis.
- **C2:** A coverage-gated EIP-7702 pre-authorization decision contract that returns WARN, LOW_OBSERVED_RISK, or DEFER and forbids incomplete analysis from producing low risk.  
  Readiness: The invariant is implemented; empirical usefulness requires final selective-risk results and honest reporting of deferral and false warnings.
- **C3:** A provenance-audited evaluation protocol combining family-disjoint training-era tests, legitimate project controls, and frozen post-cutoff authority/delegate pairs with pre-label retraining and project-family uncertainty.  
  Readiness: FINAL only after both human-review sets, the project audit, and the post-cutoff retraining freeze are complete.

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
- **BLOCK INCOMPLETE_PROJECT_FAMILY_AUDIT**: Every locked post-cutoff item needs a resolved project-family ID and auditable evidence before leakage-safe retraining.
- **BLOCK POSTCUTOFF_RETRAINING_NOT_FROZEN**: Complete the project-family holds, retrain, freeze checkpoints and label-free predictions, and create the verified review unlock before human review.
- **BLOCK INCOMPLETE_HUMAN_AGREEMENT**: gold_test requires two independent primary reviews per item and adjudication of every disagreement; observed status is NOT_READY_DUAL_REVIEW_OR_ADJUDICATION_INCOMPLETE.
- **BLOCK INCOMPLETE_HUMAN_AGREEMENT**: postcutoff requires two independent primary reviews per item and adjudication of every disagreement; observed status is NOT_READY_DUAL_REVIEW_OR_ADJUDICATION_INCOMPLETE.

## Evidence gates

```json
{
  "gold_test_agreement": {
    "n_exactly_dual_reviewed": 0,
    "n_manifest_items": 150,
    "n_pending_adjudications": 0,
    "path": "/home/pollmix/Coding/AuthGuard-7702/revision_v3/results/human_final/gold_test_agreement_status.json",
    "status": "NOT_READY_DUAL_REVIEW_OR_ADJUDICATION_INCOMPLETE"
  },
  "postcutoff_agreement": {
    "n_exactly_dual_reviewed": 0,
    "n_manifest_items": 150,
    "n_pending_adjudications": 0,
    "path": "/home/pollmix/Coding/AuthGuard-7702/revision_v3/results/human_final/postcutoff_agreement_status.json",
    "status": "NOT_READY_DUAL_REVIEW_OR_ADJUDICATION_INCOMPLETE"
  },
  "postcutoff_retraining": {
    "review_unlock": "/home/pollmix/Coding/AuthGuard-7702/revision_v3/results/postcutoff_snapshot/postcutoff_review_unlock.json",
    "status": "INCOMPLETE",
    "training_manifest": "/home/pollmix/Coding/AuthGuard-7702/revision_v3/results/postcutoff_retraining/postcutoff_training_manifest.json"
  },
  "project_family_audit": {
    "n_items": 150,
    "n_missing_evidence_reference": 150,
    "n_missing_project_family": 150,
    "n_unresolved": 150,
    "path": "/home/pollmix/Coding/AuthGuard-7702/revision_v3/results/postcutoff_snapshot/postcutoff_project_family_audit.csv",
    "status": "INCOMPLETE"
  }
}
```
