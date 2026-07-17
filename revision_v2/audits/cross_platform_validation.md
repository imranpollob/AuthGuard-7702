# Cross-platform harness validation note (2026-07-16)

## What happened

The revision program resumed on a new machine (Linux x86_64, 12 cores) after the original
machine (macOS ARM64) was shut down mid-run. Per protocol,
`revision_v2/experiments/common/validate_harness.py` was re-run before any further experiments.

**Result: FAIL at the 1e-6 tolerance.** Per-fold AUPRC differences vs the frozen v1
macOS-ARM numbers: authguard max |diff| = 2.19e-02, opcode_xgb max |diff| = 5.55e-02
(mean-AUPRC differences: authguard 0.0038, opcode_xgb 0.0164).

## Diagnosis

- The feature matrices are loaded from frozen `.npz` files (byte-identical; frozen guard
  passes: 144/144). Divergence is therefore inside model fitting.
- The run is **fully deterministic on this machine**: two independent validation runs agree
  to 0.0 on every fold; `n_jobs=4` vs `n_jobs=12` agree to 0.0.
- Library versions were matched to the original manifests (numpy 2.3.4, pandas 3.0.3,
  scikit-learn 1.9.0, xgboost 3.3.0); Python 3.13.8 vs 3.13.9 (closest available).
- Conclusion: **XGBoost floating-point / histogram divergence across CPU architectures**
  (macOS ARM64 wheel vs Linux x86_64 wheel). This is a known property of XGBoost `hist`
  training; per-fold AUPRC on ~450-sample test folds amplifies small score perturbations.

## Environment records

- `harness_validation_macos_arm.json` — original Phase-0 PASS record (git 3a46bf3).
- `harness_validation_linux_x86.json` — this machine's record (FAIL at 1e-6; deterministic).
- `harness_validation.json` — latest run on the current machine.

## Decision (protocol-consistent)

1. Frozen v1/early-v2 results (gdet_v2, gmut_v2, gvol_v2, uncertainty, family_sensitivity,
   weighting, gateA, secondary_controls, operational) computed on macOS ARM are **kept as-is**
   and remain the manuscript's source for those tables.
2. Remaining experiments (G-ADV v2, baselines/ablations incl. first-STOP investigation,
   Gate B) run on this machine. **All of their conclusions rest on within-run comparisons**
   (aug vs no-aug; baseline vs AuthGuard refit in the same run; ablation vs full-773 in the
   same run), so cross-platform offsets cancel by construction. No cross-machine number is
   compared against another cross-machine number anywhere in the manuscript.
3. The first-STOP shortcut investigation **recomputes both the first-STOP representation and
   the AuthGuard full-view on this machine in the same script** rather than reusing the
   macOS Gate-A values.
4. `n_jobs` raised 4→12 in `harness.py` (verified bit-identical results; see above).
5. This deviation is reported in the Phase 3/4 reports and in
   `final_reproducibility_audit.md`: exact per-fold reproduction of the published numbers
   requires the recorded platform (macOS ARM64) + recorded library versions; on other
   platforms, expect per-fold AUPRC shifts up to ~0.05 with unchanged conclusions.
