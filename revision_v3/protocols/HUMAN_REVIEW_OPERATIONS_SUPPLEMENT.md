# Post-Cutoff Human Review Operations Supplement

Status: pre-label operational supplement; it does not change the locked label taxonomy, reviewer
guide, evidence fields, manifest, models, thresholds, or statistical endpoints.

The semantic instructions remain the cryptographically locked
`revision_v3/human_eval/REVIEWER_GUIDE.md` (SHA-256
`d9cb38f496ac01f6fc649743a320617cfdeae0b1b14403ac6110ea8578d72c91`). If this supplement and the
locked guide conflict, stop the review and resolve the discrepancy without changing any submitted
label. This supplement adds reviewer-qualification, independence, and data-handling requirements
that the guide did not operationalize.

## Reviewer roster gate

Before review begins, copy `postcutoff_reviewer_roster_template.csv` to
`postcutoff_reviewer_roster.csv` and complete all three rows:

- R1 and R2 must be distinct primary reviewers with enough EVM bytecode or smart-contract security
  experience to identify caller restrictions, externally controlled calls, approvals,
  initialization, proxy resolution, and state-dependent uncertainty.
- R3 must be a distinct qualified adjudicator and must not be either primary reviewer.
- A stable pseudonym is acceptable if the identity mapping is retained privately for research
  integrity. The manuscript should report reviewer backgrounds and conflicts without disclosing
  unnecessary personal information.
- Every reviewer must attest that they will not inspect AuthGuard/DCRG scores, inherited labels,
  provisional labels, or another primary reviewer's judgment before submitting their own.
- Every reviewer must disclose project affiliations or other conflicts. A conflicted reviewer must
  be replaced for affected items or the conflict and handling must be reported.

The qualification statement should be factual and auditable; do not call a reviewer an expert
solely because they read the guide.

## Calibration without contaminating the primary set

R1, R2, and R3 must independently complete the guide's six synthetic examples and at least a small
separate pilot outside the 150 primary post-cutoff items. Discuss label-definition disagreements
only after each calibration judgment is recorded. Calibration may clarify the fixed taxonomy but
must not add a new label, modify the primary decision rule, inspect primary scores, or tune the
model. Record completion in the roster; do not import calibration judgments as primary labels.

## Independent review conduct

- Use separate browser profiles because the internal application stores the reviewer ID in a
  cookie. Confirm the visible reviewer ID before every session.
- R1 and R2 must not discuss an item until both final submissions exist. Drafts remain private.
- Review the actual reachable authorization behavior. Opcode presence, project popularity,
  verification status, a sensitive-name match, or an analyzer summary is not independently
  sufficient for `UNSAFE`.
- Consult explorer records, verified source, project documentation, and resolvable dependencies as
  needed, and record the specific sources in `evidence_consulted`.
- Use `INDETERMINATE` when semantics depend on unresolved proxy/state/external context. Use
  `NOT_BYTECODE_SCREENABLE` only when there is no inspectable delegate runtime.
- Final rationales must identify the concrete capability, caller/authority condition, and evidence
  boundary. The 20-character application minimum is a validity check, not an adequacy target.
- Final submissions are immutable. Corrections require a documented amendment; never edit the
  SQLite database manually.

## Adjudication

R3 is assigned only after two final primary labels disagree. R3 may then see both rationales,
independently inspect the evidence, and choose any fixed taxonomy label. Adjudication resolves the
final label; it does not erase the disagreement. Preserve and report both primary labels, raw
agreement, Cohen's kappa when defined, disagreement count, and adjudication count.

## Operational sequence

1. Complete and internally verify `postcutoff_reviewer_roster.csv`.
2. Run the readiness audit before any login or judgment:

   ```bash
   python3 revision_v3/experiments/human_label_evaluation/audit_postcutoff_review_readiness.py \
     --roster revision_v3/protocols/postcutoff_reviewer_roster.csv
   ```

   Do not begin unless it reports `READY_FOR_INDEPENDENT_HUMAN_REVIEW` with zero annotations.
3. Make a read-only backup of `revision_v3/annotation_app/annotation.db` and record its SHA-256.
4. Launch from the repository root:

   ```bash
   uvicorn app:app --app-dir revision_v3/annotation_app --host 127.0.0.1 --port 8420
   ```

   Keep the app on a trusted local/private interface; its typed reviewer ID is not an authentication
   boundary.
5. Monitor counts through `/admin/agreement.json` without inspecting item/model predictions. Back up
   the database after each review session.
6. When all primary reviews and required adjudications are final, stop the app and export:

   ```bash
   cd revision_v3/annotation_app
   python3 export.py postcutoff
   ```

7. Verify the agreement report and release against the frozen manifest with the fail-closed human
   evaluator before running any metric or opening model predictions.

## Paper reporting

Report reviewer backgrounds, calibration procedure, independence/blinding, evidence available,
agreement, disagreement categories, adjudication, indeterminate prevalence, conflicts, and any
amendments. Do not describe the labels as ground truth or expert consensus unless the actual roster
and procedure support those words. Prefer “independently reviewed and adjudicated security
judgments under the stated evidence protocol.”
