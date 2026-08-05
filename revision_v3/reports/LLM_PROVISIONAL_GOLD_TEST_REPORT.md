# Provisional Gold-Test Report

**LABEL_SOURCE=LLM_PROVISIONAL. STATUS=PROVISIONAL_NOT_FOR_FINAL_CLAIMS.**

Evaluated once, after the provisional model was frozen using Gold-Dev only (Part 8). The
model was not modified after viewing these results. Script: `run_gold_test_evaluation.py`.
Full output: `results/llm_provisional/gold_test/gold_test_report.json`.

## Coverage

150 total Gold-Test items: 131 UNSAFE, 7 SAFE, 12 UNCERTAIN (8.0% uncertainty exclusion
rate). 138 items evaluated in binary metrics.

## Results (ranked by AUPRC, with 95% family-clustered bootstrap CIs)

| Rank | Model | AUPRC | 95% CI | AUROC | Precision | Recall | FPR | F1 | Balanced Acc | Brier | ECE |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | provisional_final_model | 0.968 | [0.915, 0.999] | 0.756 | 0.956 | **1.000** | **0.857** | 0.978 | 0.571 | 0.050 | 0.058 |
| 2 | flat_cnn_16384 | 0.965 | [0.928, 0.993] | 0.599 | 0.939 | 0.351 | 0.429 | 0.511 | 0.575 | — | — |
| 3 | authguard_sequence_dense | 0.963 | [0.928, 0.991] | 0.537 | 0.936 | 0.336 | 0.429 | 0.494 | 0.562 | — | — |
| 4 | flat_cnn_matched_16384 | 0.962 | [0.923, 0.991] | 0.546 | 0.939 | 0.351 | 0.429 | 0.511 | 0.590 | — | — |
| 5 | authguard_reference_v3 | 0.959 | [0.919, 0.990] | 0.513 | 0.938 | 0.344 | 0.429 | 0.503 | 0.576 | — | — |
| — | source_static_rule | — | — | — | 0.978 | 0.344 | 0.143 | 0.508 | 0.600 | — | — |

Confusion matrices: `provisional_final_model` TP=131 FP=6 TN=1 FN=0; `authguard_sequence_dense`
TP=44 FP=3 TN=4 FN=87; `source_static_rule` TP=45 FP=1 TN=6 FN=86 (n=138 for the 4 frozen
continuous models via the mean-threshold operating point; n=138 for the rule).

## The central finding: AUPRC ranking is not the whole story

`provisional_final_model` ranks #1 by AUPRC (0.968), inside every other model's CI, so the
*rank ordering* is not statistically distinguishable from the frozen baseline at this sample
size. But at its **operating threshold** (frozen during Part 8, derived from a ~9-item
calibration split), it predicts UNSAFE for 137/138 items — recall 1.0, FPR 0.857. This is a
degenerate, unusable operating point despite a competitive AUPRC, and is flagged here exactly
because it would be easy to over-read "wins on AUPRC" without checking the threshold
separately. The frozen `authguard_sequence_dense`, by contrast, has a much more conservative
operating point (FPR 0.429, same as the other 3 architecture-only-differing models — all four
share essentially the same threshold-selection procedure and land at the identical FPR).

**Practical reading**: AUPRC differences among the 5 models are not distinguishable given
overlapping 95% CIs; the source static rule has the best precision/FPR trade-off of any
method compared here (precision 0.978, FPR 0.143) at the cost of the same recall ceiling
(~0.34-0.35) every method in this table shares.

## Uncertainty exclusion

12/150 (8.0%) items were LLM-provisional UNCERTAIN and excluded from the table above; see
`LLM_PROVISIONAL_LABELING_PROTOCOL.md`'s uncertainty policy for how these are handled
downstream (never silently dropped — preserved in `gold_test_labels.json`).
