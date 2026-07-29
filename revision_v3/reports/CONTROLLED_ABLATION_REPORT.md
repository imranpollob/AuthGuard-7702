# Controlled Ablation Report — Revision v3 Phase 1

All 9 models trained under the identical canonical protocol (stored 5 family-disjoint folds,
seeds 7702/7703/7704, class-weighted BCE, AdamW, early stopping on validation AUPRC,
temperature scaling + thresholds on validation only). Full data:
`revision_v3/results/controlled_ablation_summary.csv` (descriptive means ± SD across the 3
seed-level means), `controlled_ablation_fold_seed.csv` (135 rows = 9 models × 5 folds × 3
seeds), `controlled_ablation_predictions.csv.gz` (per-row test predictions),
`controlled_ablation_bootstrap.csv` (7 required paired family-clustered bootstrap
comparisons, 10,000 replicates each, method documented in
`run_controlled_bootstrap.py`'s docstring).

## 1. Descriptive results

| Model | Budget | AUPRC | Recall@5% FPR | Active params |
|---|---:|---:|---:|---:|
| **authguard_reference_v3** (= chunk_attention_16384) | 16,384 | 0.929 ± 0.015 | 0.843 ± 0.014 | 38,562 |
| flat_cnn_2048 | 2,048 | 0.879 ± 0.019 | 0.696 ± 0.015 | 154,177 |
| flat_cnn_8192 | 8,192 | 0.948 ± 0.005 | 0.860 ± 0.012 | 154,177 |
| flat_cnn_16384 | 16,384 | 0.951 ± 0.006 | 0.855 ± 0.035 | 154,177 |
| chunk_mean_2048 | 2,048 | 0.890 ± 0.022 | 0.753 ± 0.033 | 38,497 |
| chunk_attention_2048 | 2,048 | 0.920 ± 0.009 | 0.838 ± 0.022 | 38,562 |
| chunk_mean_8192 | 8,192 | 0.879 ± 0.033 | 0.759 ± 0.074 | 38,497 |
| chunk_attention_8192 | 8,192 | 0.928 ± 0.010 | 0.847 ± 0.015 | 38,562 |
| chunk_mean_16384 | 16,384 | 0.890 ± 0.033 | 0.782 ± 0.048 | 38,497 |
| chunk_max_16384 | 16,384 | 0.914 ± 0.011 | 0.807 ± 0.044 | 38,497 |

By raw point estimates, `flat_cnn_16384` and `flat_cnn_8192` numerically *exceed* the
hierarchical attention reference model. **This does not survive statistical testing** — see
below.

## 2. Family-clustered paired bootstrap (the numbers that actually decide the questions)

| Comparison | ΔAUPRC [95% CI] | Excludes 0? | ΔRecall@5% [95% CI] | Excludes 0? |
|---|---:|:---:|---:|:---:|
| chunk_attention_2048 − flat_cnn_2048 | +0.032 [−0.012, +0.078] | No | **+0.127 [+0.040, +0.219]** | **Yes** |
| chunk_attention_8192 − flat_cnn_8192 | −0.026 [−0.065, +0.009] | No | −0.009 [−0.050, +0.032] | No |
| chunk_attention_16384 − flat_cnn_16384 | −0.025 [−0.059, +0.002] | No | −0.009 [−0.055, +0.035] | No |
| **chunk_attention_16384 − chunk_mean_16384** | **+0.034 [+0.001, +0.070]** | **Yes** | **+0.072 [+0.018, +0.132]** | **Yes** |
| chunk_attention_16384 − chunk_max_16384 | +0.006 [−0.044, +0.058] | No | +0.037 [−0.009, +0.092] | No |
| chunk_attention_2048 − chunk_attention_8192 | −0.002 [−0.029, +0.022] | No | −0.013 [−0.065, +0.028] | No |
| chunk_attention_8192 − chunk_attention_16384 | +0.003 [−0.028, +0.032] | No | +0.002 [−0.037, +0.047] | No |

Method: for each seed, pool the 5 outer test folds' per-row calibrated scores (every primary
row is tested exactly once per seed); bootstrap resample bytecode families with replacement
(10,000 reps); average the resulting delta and CI bounds across the 3 seeds. Recall@5% uses
each row's own fold-frozen 5%-FPR threshold, never recomputed on resampled data.

## 3. Answers to the five ablation questions

**Does longer input coverage explain most of AuthGuard's improvement?** No support found.
`chunk_attention_2048` vs. `chunk_attention_8192` vs. `chunk_attention_16384` are all
statistically indistinguishable (both CIs cross zero at every budget step). Going from a
2,048-token budget to the full 16,384-token budget bought no significant AUPRC or Recall@5%
gain for the hierarchical model on this benchmark.

**Does hierarchy help at equal input budgets?** Mixed and budget-dependent. At the smallest
budget (2,048 tokens), `chunk_attention` beats `flat_cnn` significantly on Recall@5% FPR
(+0.127, CI excludes zero) though not significantly on AUPRC. At 8,192 and 16,384 tokens, the
point estimates numerically favor `flat_cnn`, but **neither difference is statistically
significant** (both CIs cross zero) — the honest conclusion is "no evidence hierarchy helps
at the larger budgets tested here," not "flat wins." A properly budget-scaled flat CNN
(154,177 active parameters vs. the hierarchical model's 38,562) is a legitimate,
competitive, much larger-capacity alternative at larger budgets, and this Phase 1 comparison
cannot rule out that the flat model's larger channel/kernel capacity — not the absence of
hierarchy — explains its numerically higher point estimates.

**Does attention outperform mean or max pooling?** Yes, over mean pooling: `chunk_attention_16384
− chunk_mean_16384` is significant on both AUPRC (+0.034, CI excludes zero) and Recall@5%
(+0.072, CI excludes zero). Attention does **not** significantly beat max pooling (both CIs
cross zero) — max pooling is a much cheaper (zero-parameter) aggregator that is statistically
indistinguishable from attention here.

**Is 16,384-token capacity necessary when the observed clean maximum is 10,795 opcodes (well
below 16,384, and the median is ~1,619)?** No evidence found that it is. The
budget-vs-budget comparisons above (item 1) show no significant gain from 2,048 → 16,384 for
the hierarchical model, consistent with most contracts already fitting comfortably inside a
2,048-token budget on clean data. The 16,384 capacity's value (if any) would have to come from
robustness to *transformed* (flooded) inputs that exceed smaller budgets — evaluated
separately in `MATCHED_ROBUSTNESS_REPORT.md`, not from clean-data coverage.

**What is the simplest defensible model?** `chunk_max_16384` (38,497 active parameters,
zero-parameter max-pooling aggregator) is statistically indistinguishable from
`chunk_attention_16384`/`authguard_reference_v3` on both metrics (CIs cross zero) while being
simpler (no attention-logit layer) and marginally cheaper. Given no significant advantage from
attention over max pooling, `chunk_max_16384` is the leanest model not contradicted by this
evidence. `chunk_mean_16384` is not competitive — it loses significantly to
`chunk_attention_16384` on both metrics.

## 4. Threats and caveats

- Point estimates and bootstrap conclusions diverge for the flat-vs-chunk-attention
  comparisons at 8,192/16,384 — reporting only the point estimates (as a headline table
  without CIs) would overstate the flat CNN's advantage. This report leads with the CIs.
- Single training run per (model, seed, fold) — no repeated-seed-within-fold variance
  estimate beyond the 3 outer seeds; GPU determinism was enabled (see
  `REFERENCE_VALIDATION_REPORT.md`) but is not independently re-verified for every model in
  this grid (only for `authguard_reference_v3`, via the two-run comparison).
- The flat CNN's parameter count (154,177) is architecture-fixed and does not scale with
  budget; a fairer "does hierarchy help" test would also control for parameter count, which
  this Phase 1 grid does not do (flagged as a Phase 2 follow-up).
