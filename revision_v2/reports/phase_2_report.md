# Phase 2 Report — Minimum Construct-Validity Package

## Objectives
Characterize the 23 conflicting exact-bytecode groups; build a reproducible human
label-adjudication package (no fabricated labels); build a bounded execution-validation harness
for the transformations; report secondary controls at frozen v2 thresholds.

## 2A — Conflicting exact-bytecode analysis
Script `revision_v2/experiments/conflicts/analyze_conflicts.py --network` (read-only
eth_getCode, cached). Outputs: `conflict_report.{json,md}`, `conflict_dossier_rows.csv`,
`conflict_rpc_cache.json`, `abstention_eval.json`.

- 23 groups / 103 rows, all remain quarantined (no restoration to the primary task).
- Deterministic 5-way categorization (rule cascade recorded in the report):
  - context_dependent_behavior: 11
  - likely_label_inconsistency: 9
  - external_dependency_difference: 2
  - unresolved: 1
- Each group has a dossier: classes, chains, distinct addresses, family IDs, shipped USENIX
  rule-fact addresses (malicious vs negative), structural signals (delegatecall/proxy/storage/
  owner/sensitive-selector), on-chain getCode kind, category, confidence, rationale.
- Known-conflict escalation rule (`abstention_eval.json`): because all conflicts are already
  quarantined, the rule escalates 0% of retained decisions while covering 100% of the known
  ambiguous exact bytecodes — a zero-false-abstention safety net for previously-seen
  conflicts; generalization to unseen ambiguity is Gate B's role.
- Before/after-quarantine sensitivity: AuthGuard family AUPRC 0.856 (pre-quarantine original
  cohort) → 0.881 (post-quarantine task-aligned); quarantine did not inflate the headline.

## 2B — Manual adjudication support (NO coder-provided labels)
Script `revision_v2/experiments/label_audit/build_audit_package.py`. Outputs under
`revision_v2/artifact/label_audit/`: `evidence_packets.json`, three blinded reviewer forms
`review_form_R{1,2,3}_BLINDED.csv`, `reviewer_assignments.csv`, `REVIEWER_GUIDELINES.md`,
`sampling_manifest.json`, and `REVIEWER_KEY_do_not_distribute.csv` (held separate).
- 170 items across 7 strata (random positive/weak-negative, high-scoring FP, low-scoring FN,
  high-confidence correct, exact-bytecode conflict, highest-scoring benign_general), seeded
  and reproducible.
- `agreement.py` computes pairwise Cohen's kappa, Fleiss' kappa, majority adjudication, and a
  disagreement list once ≥2 completed forms are supplied; currently returns
  `status=pending_human_labels` and does not block the pipeline.

## 2C — Bounded execution-validation harness
Script `revision_v2/experiments/exec_validation/run_exec_validation.py` (anvil 0.2.0,
`anvil_setCode` + opcode-level `debug_traceCall`). No real attack replay is possible — the
USENIX artifact ships no attack tx hashes / victim state / exploit scripts — so we drive each
installed runtime with a fixed calldata suite (empty + dispatch selectors, zero args) and
compare execution fingerprints (revert, external calls + targets, SSTORE writes, logs, return
value, opcode count) between original and each transform over 10 representative malicious
delegates.
Results (`exec_validation.json`, `exec_validation_per_call.csv`):
- M1 (metadata rewrite): 10/10 contracts fully preserved across all tested calldata.
- M2 (address immediates + dead code): 10/10 preserved control-flow structure (call count,
  logs, storage), with call targets allowed to differ by construction.
- F200 (flooding): 10/10 fully preserved — trailing appended bytes never execute, confirming
  unreachability of the padding under the tested transactions.
- M3 (selector rewrite): divergence only at renamed sensitive selectors, which reroute to
  fallback — the intended effect that defeats the name rule; 2/10 contracts with no sensitive
  selectors in the tested suite showed full preservation.
Bounded claim (honest): *under the tested transactions, transformed variants preserved the
observed execution fingerprint for the stated counts*; no formal semantic-equivalence claim.

## 2D — Secondary controls at frozen v2 thresholds
Script `revision_v2/experiments/secondary_controls/run_controls.py`
(`secondary_controls.json`, `benign_AA_cases.csv`). Thresholds frozen by inner family-grouped
OOF on the primary population before scoring controls.
- benign_general (n=797), AuthGuard: FPR 0.119 (95/797), alerts/1000 = 119, p95 score 0.097,
  family-macro FPR 0.129. opcode_rf FPR 0.034 (higher threshold), opcode_xgb 0.221.
  The elevated AuthGuard FPR reflects the aggressive max-F1 operating point (low threshold);
  a higher-precision operating point exists (see Phase 6B operational analysis).
- benign_AA (n=5): all score ≈0.00 and are not flagged; reported as individual case
  observations only.

## Tests / integrity
Frozen guard verified 144/144 before and after every 2A–2D script. Read-only network only
(eth_getCode), cached.

## Reviewer issues addressed
2 (conflict characterization), 1 (adjudication package toward label validity), 4 (bounded
execution validity of transformations), 9 (secondary controls).

## Claims now supported
- The 23 conflicts are characterized, not merely quarantined; most are context/ dependency
  driven, a minority are likely label inconsistencies.
- Transformations preserve observed execution behavior on tested inputs (M1/M2/F200), with M3
  divergence being the intended selector reroute.
- Clean secondary-control FPR is measured at a stated operating point.

## Claims still unsupported
- Independent rule-free label ground truth (awaits human adjudication — package ready).
- Full behavioral/semantic equivalence of transformations (only bounded traces tested).

## Frozen-hash verification
PASS (144 files) after Phase 2.

## Next
Phase 3 (baselines/ablations/family/weighting) running; Phase 4 gates; then Phase 6.
