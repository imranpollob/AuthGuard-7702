# Statistical Final Summary

## Direct answers

**A. Clean AUPRC vs Flat CNN.** Yes. The paired difference is +0.039 with 95% CI [+0.009, +0.073].

**B. Clean AUPRC vs XGBoost.** Yes. The paired difference is +0.091 with 95% CI [+0.045, +0.140].

**C. Clean Recall@5% vs Flat CNN.** Yes. The paired difference is +0.121 with 95% CI [+0.050, +0.190].

**D. Clean Recall@5% vs XGBoost.** Yes. The paired difference is +0.217 with 95% CI [+0.124, +0.314].

**E. F200 advantages.** Yes. AUPRC vs flat_cnn: Δ +0.385, 95% CI [+0.302, +0.472]; Recall@5% vs flat_cnn: Δ +0.556, 95% CI [+0.463, +0.655]; AUPRC vs hist_ngram_xgb: Δ +0.344, 95% CI [+0.286, +0.397]; Recall@5% vs hist_ngram_xgb: Δ +0.521, 95% CI [+0.442, +0.607].

**F. M3+F200 advantages.** Yes. AUPRC vs flat_cnn: Δ +0.387, 95% CI [+0.309, +0.468]; Recall@5% vs flat_cnn: Δ +0.561, 95% CI [+0.471, +0.659]; AUPRC vs hist_ngram_xgb: Δ +0.355, 95% CI [+0.296, +0.409]; Recall@5% vs hist_ngram_xgb: Δ +0.543, 95% CI [+0.467, +0.629].

**G. Paper-ready paired differences.**

| Analysis | Metric | Δ | 95% CI |
|---|---|---:|---:|
| clean: Seq vs flat_cnn | AUPRC | +0.039 | [+0.009, +0.073] |
| clean: Seq vs flat_cnn | Recall@5% | +0.121 | [+0.050, +0.190] |
| clean: Seq vs hist_ngram_xgb | AUPRC | +0.091 | [+0.045, +0.140] |
| clean: Seq vs hist_ngram_xgb | Recall@5% | +0.217 | [+0.124, +0.314] |
| F200: Seq vs flat_cnn | AUPRC | +0.385 | [+0.302, +0.472] |
| F200: Seq vs flat_cnn | Recall@5% | +0.556 | [+0.463, +0.655] |
| F200: Seq vs hist_ngram_xgb | AUPRC | +0.344 | [+0.286, +0.397] |
| F200: Seq vs hist_ngram_xgb | Recall@5% | +0.521 | [+0.442, +0.607] |
| M3+F200: Seq vs flat_cnn | AUPRC | +0.387 | [+0.309, +0.468] |
| M3+F200: Seq vs flat_cnn | Recall@5% | +0.561 | [+0.471, +0.659] |
| M3+F200: Seq vs hist_ngram_xgb | AUPRC | +0.355 | [+0.296, +0.409] |
| M3+F200: Seq vs hist_ngram_xgb | Recall@5% | +0.543 | [+0.467, +0.629] |
| AuthGuard-Seq F200_minus_M0 | AUPRC | -0.013 | [-0.030, -0.002] |
| AuthGuard-Seq F200_minus_M0 | Recall@5% | -0.104 | [-0.155, -0.067] |
| AuthGuard-Seq M3+F200_minus_M0 | AUPRC | -0.020 | [-0.037, -0.009] |
| AuthGuard-Seq M3+F200_minus_M0 | Recall@5% | -0.105 | [-0.158, -0.067] |

**H. Intervals crossing zero.** No primary, robustness, or clean-to-transformed interval crosses zero. One secondary interval—clean Recall@1% versus Flat CNN—crosses zero, so that optional low-FPR advantage is not statistically supported.

**I. Consistency with descriptive results.** Yes. Clean inference uses the completed baseline predictions and exactly reproduces the established 0.924, 0.885, and 0.833 fold→seed AUPRC means. Robustness comparisons use the matched robustness-run models. Clean-to-transformed changes use that run's M0 predictions so model weights, calibration, and thresholds remain paired. No pooled-score estimator replaces the descriptive headline numbers.

**J. Strongest statistically supported claim.** Under family-clustered, paired, three-seed inference, AuthGuard-Seq has higher clean AUPRC and Recall@5% than both Flat CNN and histogram+hashed-4-gram XGBoost. Its AUPRC and Recall@5% advantages also remain supported under F200 and M3+F200. These claims concern screening of source-analyzer-flagged EIP-7702 delegate risk and do not establish independently confirmed maliciousness or universal semantic robustness.

## Methodological issue affecting interpretation

The clean confirmatory predictions and robustness predictions come from separate neural training executions. Because the frozen GPU training path is not bitwise deterministic, robustness-run M0 differs modestly from the baseline run. Therefore clean confirmatory inference uses `baseline_v2`, whereas clean-to-transformed changes use the matched robustness-run M0. Mixing those sources would break the pairing. P-values and Holm-adjusted p-values are intentionally not reported; the predefined percentile confidence intervals are the primary inferential result.
