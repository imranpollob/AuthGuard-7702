# Phase 1 Failures and Deviations

- Confirmed protocol defect: v1 G-DET/G-MUT/G-VOL thresholds used in-sample fitting scores.
  Corrected v2 OOF thresholds are primary; v1 remains frozen for reconciliation only.
- Confirmed donor defect: v1 G-ADV reused one donor across training and test transformations.
  Donor-isolated v2 replaces it; v1 is labeled donor-confounded.
- Interrupted run: the first G-ADV v2 attempt stopped after fold 1 and retained no partial
  machine-readable result. The complete five-fold rerun is the sole v2 source.
- Cross-platform validation: Linux x86_64 XGBoost `hist` fits are deterministic but fail the
  1e-6 replay tolerance against macOS ARM64 frozen scores. Remaining experiments use within-host
  comparisons and report this deviation; frozen ARM results are not overwritten.
- Protocol ledger deviation: the committed donor-isolation v1.1 amendment predates all
  donor-isolated results, but its entry in `protocols.sha256` was not refreshed. Four other
  entries verify. The protocol and ledger remain untouched; the mismatch is disclosed.
- Scientific reversal: donor-isolated augmentation improves recall/AUPRC but significantly
  increases rather than decreases FPR. The prior false-positive-reduction claim is rejected.
