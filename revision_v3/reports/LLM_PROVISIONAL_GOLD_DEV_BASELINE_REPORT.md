# Provisional Gold-Dev Baseline Report

**LABEL_SOURCE=LLM_PROVISIONAL. STATUS=PROVISIONAL_NOT_FOR_FINAL_CLAIMS.**

Evaluates the 4 frozen continuous models plus the source static rule against the 60 Gold-Dev
items' LLM-provisional labels (Part 4). Script: `run_gold_dev_baseline.py`. Full output:
`results/llm_provisional/gold_dev_baseline/gold_dev_baseline_report.json`.

## Label distribution and coverage

60 items total: 42 UNSAFE, 5 SAFE, 13 UNCERTAIN (21.7% coverage excluded from binary metrics).

## Results (operating threshold = each model's own frozen `threshold_5pct`, mean across 15
Phase 1/2 checkpoints — NOT re-fit on Gold-Dev)

| Model | AUPRC | AUROC | Precision | Recall | Specificity | FPR | F1 | Balanced Acc | Brier | ECE |
|---|---|---|---|---|---|---|---|---|---|---|
| authguard_sequence_dense | 0.925 | 0.610 | 0.882 | 0.357 | 0.600 | 0.400 | 0.508 | 0.479 | 0.549 | 0.601 |
| authguard_reference_v3 | 0.923 | 0.571 | 0.882 | 0.357 | 0.600 | 0.400 | 0.508 | 0.479 | 0.559 | 0.578 |
| flat_cnn_matched_16384 | 0.922 | 0.614 | 0.882 | 0.357 | 0.600 | 0.400 | 0.508 | 0.479 | 0.559 | 0.588 |
| flat_cnn_16384 | 0.930 | 0.657 | 0.882 | 0.357 | 0.600 | 0.400 | 0.508 | 0.479 | 0.555 | 0.586 |
| source_static_rule | — | — | 0.882 | 0.357 | 0.600 | 0.400 | 0.508 | 0.479 | — | — |

Confusion matrix (identical across all 4 continuous models at their respective thresholds,
n=47): TP=15, FP=2, TN=3, FN=27.

## Notable findings

- **All 4 models produced the identical confusion matrix** at their own thresholds despite
  visibly different score distributions per item (spot-checked in the underlying JSON — e.g.
  `flat_cnn_16384` scores cluster near 0.95-0.97 while `authguard_sequence_dense` spans
  0.04-0.93 on the same items). This is plausible at n=47 (limited resolution) but is called
  out explicitly rather than silently reported as 4 independent results.
- **Recall (35.7%) is low relative to AUPRC (~0.92-0.93)** — a direct consequence of applying
  a threshold calibrated on the original Phase 1/2 validation-fold class balance to a Gold-Dev
  sample whose provisional-label positive rate (42/47 = 89%) is far higher than the training
  population's. This motivates Part 7's threshold-recalibration experiment.
- **Calibration is poor across the board** (Brier ~0.55, ECE ~0.58-0.60) — expected, given the
  same threshold-vs-population-shift issue; these numbers should not be read as evidence the
  underlying scores are bad rank-orderings (AUPRC says otherwise), only that the *probability
  calibration* transfers poorly to this specific 47-item sample.
- The source static rule matches the continuous models' confusion matrix exactly at this
  sample size — not itself informative beyond "both are limited by the same 47-item
  resolution"; see Part 9's larger Gold-Test comparison for a more resolved picture.
