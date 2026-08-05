# Corrected Bootstrap Report — Revision v3 Phase 2, Part 1

## What was wrong

Phase 1's bootstrap (`revision_v3/src/evaluation/bootstrap.py`,
`paired_family_bootstrap_ci`) ran an **independent** family-clustered bootstrap for each of
the 3 seeds separately, producing 3 separate `(delta, ci_low, ci_high)` triples, and then
averaged the three `ci_low` values and the three `ci_high` values together to report a single
"CI." This is not a valid confidence interval: percentile bounds are not linear functionals of
the underlying sampling distribution, so the average of three percentile bounds is not the
percentile bound of any single, coherent distribution. It also throws away the fact that all
three seeds are being applied to the *same* resampled set of families in spirit (the analyst's
intent), while treating each seed's resampling noise as if it were independent of the other
two.

## The fix

`revision_v3/src/evaluation/bootstrap_v2.py`, `seed_aware_paired_bootstrap_ci`: for **each**
of the 10,000 bootstrap replicates, one family multiset is drawn (with replacement) and reused
for all three seeds; the paired metric difference (model A − model B) is computed
independently per seed on that **same** resampled index set; the three seed-level differences
are averaged into one replicate-level number; the 95% CI is the 2.5th/97.5th percentile of the
resulting 10,000 replicate-level averaged differences. This produces one internally consistent
distribution and one valid interval, rather than three intervals mashed together after the
fact. Point estimates (the reported "delta") are unchanged in method — mean of the three
seeds' full-sample paired deltas — and are numerically identical to Phase 1's point estimates
(verified: e.g. chunk_attention_2048 − flat_cnn_2048 AUPRC delta = 0.032486 in both).
Recall@5% FPR continues to use each row's own fold-frozen threshold (computed once from
validation negatives, never recomputed on bootstrap-resampled data) — this was already correct
in Phase 1 and is preserved unchanged.

All 14 Phase 1 paired comparisons (7 controlled ablation, 4 model candidates, 3 matched
robustness) were recomputed. Full data:
`revision_v3/results/phase2_corrected_bootstrap/{controlled_ablation,model_candidate,matched_robustness}_bootstrap_corrected.csv`.

## Which Phase 1 significance conclusions changed

**4 of 14 comparisons flip from "CI crosses zero" (Phase 1) to "CI excludes zero" (corrected)
— all four became newly significant, none became newly non-significant.** The corrected
method's CIs are consistently narrower than Phase 1's averaged-bounds CIs (expected: sharing
one family resample across all three seeds removes an artificial widening the after-the-fact
averaging introduced), which is why previously-borderline results resolved to significant
rather than the reverse.

| # | Comparison | Metric | Phase 1 (averaged-after-the-fact) | Corrected (seed-aware) | Conclusion change |
|---|---|---|---|---|---|
| 1 | chunk_attention_16384 vs. flat_cnn_16384 | AUPRC | Δ=−0.025 [−0.059, +0.002], crosses 0 | Δ=−0.025 **[−0.051, −0.003]**, excludes 0 | **Not sig. → SIGNIFICANT.** `flat_cnn_16384` significantly beats `authguard_reference_v3` on clean AUPRC at their shared native budget. |
| 2 | chunk_attention_16384 vs. chunk_max_16384 | Recall@5% | Δ=+0.037 [−0.009, +0.092], crosses 0 | Δ=+0.037 **[+0.012, +0.068]**, excludes 0 | **Not sig. → SIGNIFICANT.** Attention pooling significantly beats max pooling on Recall@5% (AUPRC comparison remains not significant both ways). |
| 3 | authguard_sequence_ngram vs. authguard_reference_v3 | AUPRC | Δ=−0.029 [−0.066, +0.007], crosses 0 | Δ=−0.029 **[−0.054, −0.003]**, excludes 0 | **Not sig. → SIGNIFICANT.** The n-gram hybrid is significantly *worse* than the plain reference model. |
| 4 | authguard_all_views vs. authguard_reference_v3 | AUPRC | Δ=−0.035 [−0.079, +0.006], crosses 0 | Δ=−0.035 **[−0.064, −0.006]**, excludes 0 | **Not sig. → SIGNIFICANT.** The full 3-view hybrid is significantly *worse* than the plain reference model. |

**Finding #1 above is the most consequential for the project**: Phase 1's
`CONTROLLED_ABLATION_REPORT.md` explicitly stated "at 8,192 and 16,384 tokens... neither
difference is statistically significant... the honest conclusion is 'no evidence hierarchy
helps at the larger budgets'." Under the corrected bootstrap, the 16,384-budget comparison is
now significant **in favor of the flat CNN**. This is carried forward into
`PARAMETER_MATCHED_COMPARISON_REPORT.md` and `FINAL_MODEL_SELECTION.md`, since it bears
directly on whether hierarchy has a defensible clean-data advantage once budget is matched
(spoiler: parameter count was still not controlled at this stage — see Part 2).

## Which Phase 1 significance conclusions are unchanged

The remaining 10 of 14 comparisons keep the same significance direction as Phase 1, with the
corrected CIs uniformly narrower or comparable:

| Comparison | Metric | Status (both Phase 1 and corrected) |
|---|---|---|
| chunk_attention_2048 vs. flat_cnn_2048 | AUPRC | Not significant both |
| chunk_attention_2048 vs. flat_cnn_2048 | Recall@5% | **Significant both** (chunk_attention wins) |
| chunk_attention_8192 vs. flat_cnn_8192 | AUPRC, Recall@5% | Not significant both |
| chunk_attention_16384 vs. flat_cnn_16384 | Recall@5% | Not significant both |
| chunk_attention_16384 vs. chunk_mean_16384 | AUPRC, Recall@5% | **Significant both** (attention beats mean) |
| chunk_attention_16384 vs. chunk_max_16384 | AUPRC | Not significant both |
| chunk_attention_2048 vs. chunk_attention_8192 | AUPRC, Recall@5% | Not significant both |
| chunk_attention_8192 vs. chunk_attention_16384 | AUPRC, Recall@5% | Not significant both |
| authguard_multiscale vs. reference | AUPRC, Recall@5% | Not significant both |
| authguard_sequence_dense vs. reference | AUPRC, Recall@5% | Not significant both |
| All 3 matched-budget robustness (chunk_attention vs. flat_cnn, Flood-200% AUPRC) | AUPRC | **Significant both**, chunk_attention wins at every budget (CIs tighten but stay clearly excluding zero: e.g. 16,384 budget Δ=+0.049 [+0.017, +0.082] corrected vs. [+0.004, +0.096] Phase 1) |

## Exact corrected intervals (all 14 comparisons)

See `revision_v3/results/phase2_corrected_bootstrap/all_corrected_results.json` for the
complete machine-readable output (point deltas, per-seed point deltas, CI bounds,
`excludes_zero` flags) for every comparison. Summary tables above reproduce the 4 changed and
representative unchanged results; the three raw CSVs contain all 14.

## Binding rule for the rest of Phase 2

**Every subsequent significance claim in Phase 2 (Parts 2–4: parameter-matched comparison,
final robustness confirmation, final model selection) uses
`seed_aware_paired_bootstrap_ci` exclusively.** The Phase 1 `bootstrap.py` module and its
output files are left untouched for historical record but are no longer treated as the source
of truth for any significance claim.
