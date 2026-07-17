# Phase 0 Report — Workspace, Guards, Shared Harness

## Objectives
Branch isolation, frozen-artifact guard, environment capture, frozen v2 protocol documents,
shared corrected-protocol harness, and back-compat validation.

## Work completed
1. Branch `revision-v2` created; all new files under `revision_v2/`.
2. Frozen-file SHA-256 ledger built and verified: **144 files**
   (`revision_v2/audits/frozen_ledger.json`; guard script
   `revision_v2/experiments/common/frozen.py` — `verify` exits 1 on any change; wired into
   the harness as `verify_frozen_or_die()`).
3. Environment captured: `revision_v2/audits/{environment.json, pip_freeze.txt,
   requirements.txt}` — Python 3.13.9, numpy 2.3.4, pandas 3.0.3, scikit-learn 1.9.0,
   xgboost 3.3.0, macOS arm64.
4. Protocol documents frozen and hashed (`revision_v2/protocols/protocols.sha256`):
   threshold_protocol_v2, donor_isolation_protocol, gateA_success_criteria,
   gateB_success_criteria, uncertainty_protocol_v2. Gate criteria were written BEFORE any
   v2 result was produced.
5. Shared harness `revision_v2/experiments/common/harness.py`: task-aligned corpus + stored
   folds loader (frozen feature matrices reused, read-only), inner family-grouped
   stratified OOF threshold selection (StratifiedGroupKFold with both-class assertion +
   deterministic greedy fallback), refit-on-full-outer-train, single-test-pass evaluation,
   FPR-inclusive metrics, per-row score persistence, manifest writer.

## Tests
- `validate_harness.py`: v2 harness reproduces frozen task-aligned v1 per-fold AUPRCs for
  `authguard` and `opcode_xgb` with **max |diff| = 0.0** (tolerance 1e-6) → PASS
  (`revision_v2/audits/harness_validation.json`).
- Frozen guard: 144/144 files verified unchanged after all Phase 0 work.

## Resumed-host validation note (2026-07-16)

The exact PASS above is the original macOS ARM64 record and remains preserved as
`harness_validation_macos_arm.json`. On the resumed Linux x86_64 host, matched-library XGBoost
histogram fits are deterministic but differ from the ARM fold scores (maximum absolute
differences 0.022 AuthGuard and 0.055 opcode XGBoost), so current-host validation fails the
1e-6 cross-platform tolerance. Remaining experiments use within-host comparisons only; see
`cross_platform_validation.md`. This does not retroactively convert the original-host PASS into
a cross-platform PASS.

## Numerical results
None (infrastructure phase).

## Deviations / failures

- The resumed Linux host does not satisfy the 1e-6 macOS ARM replay tolerance; all new model
  comparisons are therefore within-host.
- A finalization audit found that `protocols.sha256` was not refreshed when the committed
  donor-isolation v1.1 amendment was made before donor-isolated results. Four of five entries
  verify. The immutable file and ledger remain unchanged; see `protocol_hash_validation.md`.

## Frozen-hash verification
PASS before and after phase (144 files).

## Next phase
Phase 1A (claim audit) and 1B (corrected-threshold reruns).
