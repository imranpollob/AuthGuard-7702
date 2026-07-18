# Revision v2 Paired Statistical Analysis

## Estimator

This analysis uses a paired, fold-stratified family-clustered percentile bootstrap with 10,000 replicates and fixed seed 77022026. Within each outer test fold, every replicate samples that fold's frozen bytecode families with replacement and retains all observations belonging to each sampled family. The same family multiplicities are applied to both paired models, all three seeds, and paired clean/transformed conditions.

For each replicate, a metric is computed separately for every seed and fold. The five fold values are averaged to a seed-level value, and the seed-level values for 7702, 7703, and 7704 are averaged. The reported delta is AuthGuard-Seq minus the comparator; for clean-to-transformed analysis it is transformed minus M0. This exactly preserves the completed experiments' fold→seed→three-seed descriptive estimator. Prediction scores are never averaged across seeds.

Percentile 95% confidence intervals are the inferential result. P-values are not reported: using the sign frequency of an observed-centered bootstrap distribution as a null p-value would be misleading. Consequently Holm correction is not applicable. The four predefined primary comparisons remain explicitly separated from supporting and secondary analyses.

## Integrity checks

All 60 descriptive recomputations matched their completed summary values within 1e-10. Every model/condition/seed contained 2,190 held-out rows; sample IDs, family IDs, folds, labels, and seeds aligned with the official benchmark; all paired comparisons used identical observations; and no family crossed folds. The batched weighted-AUPRC implementation was checked against scikit-learn to 1e-12.

## Primary confirmatory comparisons

| Metric | Comparison | AuthGuard-Seq | Comparator | Δ | 95% CI | Supported? |
|---|---|---:|---:|---:|---:|---:|
| AUPRC | Seq vs flat_cnn | 0.924 | 0.885 | +0.039 | [+0.009, +0.073] | yes |
| Recall@5% | Seq vs flat_cnn | 0.833 | 0.712 | +0.121 | [+0.050, +0.190] | yes |
| AUPRC | Seq vs hist_ngram_xgb | 0.924 | 0.833 | +0.091 | [+0.045, +0.140] | yes |
| Recall@5% | Seq vs hist_ngram_xgb | 0.833 | 0.615 | +0.217 | [+0.124, +0.314] | yes |

## Secondary clean comparisons

| Metric | Comparison | Δ | 95% CI | Supported? |
|---|---|---:|---:|---:|
| Recall@1% | Seq vs flat_cnn | +0.095 | [-0.003, +0.185] | no |
| Recall@10% | Seq vs flat_cnn | +0.127 | [+0.070, +0.175] | yes |
| Brier | Seq vs flat_cnn | -0.027 | [-0.042, -0.013] | yes |
| Recall@1% | Seq vs hist_ngram_xgb | +0.249 | [+0.157, +0.345] | yes |
| Recall@10% | Seq vs hist_ngram_xgb | +0.208 | [+0.125, +0.275] | yes |
| Brier | Seq vs hist_ngram_xgb | -0.055 | [-0.077, -0.033] | yes |

## Supporting robustness comparisons

| Condition | Metric | Comparison | Δ | 95% CI | Supported? |
|---|---|---|---:|---:|---:|
| F200 | AUPRC | Seq vs flat_cnn | +0.385 | [+0.302, +0.472] | yes |
| F200 | Recall@5% | Seq vs flat_cnn | +0.556 | [+0.463, +0.655] | yes |
| F200 | AUPRC | Seq vs hist_ngram_xgb | +0.344 | [+0.286, +0.397] | yes |
| F200 | Recall@5% | Seq vs hist_ngram_xgb | +0.521 | [+0.442, +0.607] | yes |
| M3+F200 | AUPRC | Seq vs flat_cnn | +0.387 | [+0.309, +0.468] | yes |
| M3+F200 | Recall@5% | Seq vs flat_cnn | +0.561 | [+0.471, +0.659] | yes |
| M3+F200 | AUPRC | Seq vs hist_ngram_xgb | +0.355 | [+0.296, +0.409] | yes |
| M3+F200 | Recall@5% | Seq vs hist_ngram_xgb | +0.543 | [+0.467, +0.629] | yes |

## Clean-to-transformed AuthGuard-Seq changes

| Change | Metric | Observed change | 95% CI | Crosses zero? |
|---|---|---:|---:|---:|
| F200_minus_M0 | AUPRC | -0.013 | [-0.030, -0.002] | no |
| F200_minus_M0 | Recall@5% | -0.104 | [-0.155, -0.067] | no |
| M3+F200_minus_M0 | AUPRC | -0.020 | [-0.037, -0.009] | no |
| M3+F200_minus_M0 | Recall@5% | -0.105 | [-0.158, -0.067] | no |

## Interpretation

Confidence intervals quantify dependence-aware uncertainty for the predefined comparisons. They do not cure the benchmark's analyzer-derived label boundary, and robustness intervals do not turn M3+F200 into a semantics-preserving transformation. F200 retains only the previously documented bounded execution-fingerprint support.

Runtime: 37.1 seconds.
