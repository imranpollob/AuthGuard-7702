# Provisional Retraining Report

**LABEL_SOURCE=LLM_PROVISIONAL. STATUS=PROVISIONAL_NOT_FOR_FINAL_CLAIMS.**

10 methods, all starting from the identical frozen `authguard_sequence_dense` checkpoint
(seed7702_fold0), fine-tuned/evaluated on Gold-Dev's 47 binary-labeled items only (never
Gold-Test), under a family-grouped 3-fold split × 3 seeds. 46 of 47 items are singleton
families, so this is effectively plain 3-fold CV — confirmed and logged at runtime. 3 of the
9 nominal (fold × seed) runs per method were skipped because that fold's validation split was
single-class (AUPRC undefined) — **n_runs=6, not 9, for every method**; this is a real
consequence of the tiny sample, not a bug, and is the central caveat of this report.

Script: `run_retraining_experiments.py`. Full per-run detail:
`results/llm_provisional/retraining/retraining_results.json`.

## Results (mean ± std validation AUPRC across 6 runs)

| Method | Mean AUPRC | Std | Notes |
|---|---|---|---|
| confidence_weighted | **0.969** | **0.017** | Best mean, lowest std — see Part 8 selection |
| source_plus_provisional_weighting | 0.962 | 0.020 | Down-weights source-rule/provisional disagreements |
| soft_label_confidence | 0.938 | 0.038 | Confidence-scaled soft targets |
| plain_finetune | 0.952 | 0.027 | Vanilla BCE fine-tune, no weighting |
| generalized_cross_entropy | 0.951 | 0.027 | GCE, q=0.7 |
| positive_unlabeled_nnpu | 0.947 | 0.050 | Treats 13 UNCERTAIN items as the nnPU "unlabeled" pool |
| label_smoothing_noise_aware | 0.916 | 0.058 | 0.9/0.05 label smoothing as a noise-robust approximation |
| threshold_recalibration_only | 0.911 | 0.047 | No weight updates — order-statistic threshold refit only |
| baseline_frozen | 0.911 | 0.047 | No change (identical to threshold_recalibration_only's AUPRC since AUPRC is threshold-free) |
| sequence_dense_weight_adjustment | 0.900 | 0.059 | Sequence encoder frozen, only dense/gate/fusion/head fine-tuned |

## Interpretation

- `confidence_weighted` (weighting each training example's BCE loss by the LLM's own stated
  confidence — high=1.0, medium=0.66, low=0.33) both improved mean AUPRC the most (+0.058
  over frozen baseline) and was the most stable (lowest std across the 6 CV runs) — a
  genuinely defensible signal, not cherry-picked on the mean alone.
- `sequence_dense_weight_adjustment` (freezing the pretrained sequence encoder) performed
  *worse* than the frozen baseline, suggesting the sequence view's pretrained representation
  is already carrying most of the useful signal and restricting fine-tuning to the dense/gate
  path alone isn't enough to adapt to Gold-Dev's different distribution.
- `positive_unlabeled_nnpu`'s comparatively wide std (0.050) reflects both the small labeled
  set and the additional variance from drawing the "unlabeled" batch from only 13 UNCERTAIN
  items each step.
- **These are all 47-item, 6-run estimates.** The differences between methods (e.g.
  confidence_weighted's 0.969 vs. plain_finetune's 0.952) are well within what small-sample
  noise could produce; no statistical significance test was run given how few runs exist per
  method (a paired bootstrap over 6 points would not be meaningful). Part 8 treats this as
  directional evidence, not a proven ranking.

## Family leakage check

`n_unique_families=46` for 47 items, confirmed no cross-fold family overlap by construction
(each family assigned to exactly one of the 3 folds). Separately verified Gold-Dev families
never overlap Gold-Test families (`test_family_isolation_between_gold_dev_and_gold_test`).
