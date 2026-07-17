# Threshold Protocol v2 (frozen before any v2 result is read)

Seed: 7702. Applies to G-DET-v2, G-MUT-v2, G-VOL-v2, all Phase 3 baselines/ablations, and all
Phase 4 models. G-ADV-v2 keeps its dedicated-validation primary protocol (below) plus an
inner-OOF sensitivity arm.

## G-DET-v2 operating-threshold selection (per outer fold, per method)

1. Hold out outer family fold `f` (stored `outer_fold_primary` / `outer_fold_secondary`).
2. On the outer-training population only, build inner splits with a deterministic
   group-aware stratified splitter: `StratifiedGroupKFold(n_splits=4, shuffle=True,
   random_state=7702)` grouped by frozen `family_id`. Assert every inner validation fold
   contains both classes; if the assertion fails, fall back to a deterministic custom
   group-stratified allocator (greedy family assignment balancing class counts) and record
   the fallback in the run manifest.
3. Fit the method on each inner-training split; predict the inner-validation split;
   concatenate to inner out-of-fold (OOF) predictions covering the outer-training population.
4. Threshold = max-F1 over the OOF predictions (same `best_f1_threshold` sweep as v1, applied
   to OOF scores instead of in-sample scores).
5. Refit the method on the complete outer-training population.
6. Freeze the threshold; evaluate exactly once on outer test fold `f`.
7. Persist per-row test scores, thresholds, and predictions for every method.

Rule-based detectors (binary scores) keep threshold 0.5. Blocklist keeps 0.5.

## G-MUT-v2 / G-VOL-v2

- Thresholds: the clean-M0 G-DET-v2 threshold of the same outer fold and method (selected on
  outer-training OOF predictions only). Never optimized on transformed observations.
- The frozen clean threshold is applied unchanged to every transformed condition.
- Both recall (malicious recipients) and FPR (transformed negative recipients, new in v2)
  are reported wherever both classes are available.
- G-MUT (tiers M0–M3) and G-VOL (M3 + flooding fraction sweep) remain distinct protocols.

## G-ADV-v2

Primary (unchanged from v1, methodologically valid): per outer fold `f` — test = fold `f`;
validation = fold `(f+1) mod 5`, clean-M0 variants only; train-fit = remaining 3 folds;
threshold = max-F1 on validation scores.
Sensitivity arm: thresholds from inner family-grouped OOF within the 4 non-test folds
(train on 4 folds). Both arms labeled explicitly in outputs.

## Metrics and aggregation

- Per-fold: AUPRC, AUROC, F1, Precision, Recall, FPR (+ retained_vs_M0 for transformed).
- Aggregation: fold mean ± population std (ddof=0), kept clearly separate from
  family-clustered bootstrap CIs (protocol in `uncertainty_protocol_v2.md`).
- Framing: this correction addresses threshold-transfer validity and protocol consistency.
  It is not asserted that the v1 in-sample procedure inflated test metrics; v1→v2 deltas are
  reported descriptively.
