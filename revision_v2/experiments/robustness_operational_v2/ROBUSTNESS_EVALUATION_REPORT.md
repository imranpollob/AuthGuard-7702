# Robustness Evaluation Report

## Protocol

The evaluation uses the 2,190-row PRIMARY_EVALUATION population (727 source-flagged and 1,463 source-unflagged delegates), its frozen family-disjoint folds, seeds 7702/7703/7704, and all five outer folds. For test fold f, validation is (f+1) mod 5 and the other three folds train the model. Models train only on clean bytecode. Temperature and 1%, 5%, and 10% thresholds come only from clean validation data and are applied unchanged to M0, F200, and M3+F200 test rows.

F200 appends STOP followed by donor-isolated executable bytes totaling approximately 200% of the recipient executable-region size. The existing bounded audit observed fingerprint preservation on all 100 calls across 10 delegates; this is bounded evidence, not formal equivalence. M3+F200 additionally rewrites metadata, PUSH20 address immediates, and PUSH4 selectors before 200% flooding. Because those rewrites can change behavior, M3+F200 is a representation-stress condition, not a universally semantics-preserving transformation.

Donor-isolation audit: **PASS**; 4,380 recipient-condition pairs and 8,450 donor segments were recorded, with zero same-family or wrong-partition rows.

## Results

| Model | Condition | AUPRC | AUROC | R@1 / FPR@1 | R@5 / FPR@5 | R@10 / FPR@10 | Brier |
|---|---|---:|---:|---:|---:|---:|---:|
| authguard_seq | M0 | 0.932 ± 0.006 | 0.967 ± 0.008 | 0.510 ± 0.085 / 0.015 ± 0.002 | 0.851 ± 0.015 / 0.049 ± 0.007 | 0.921 ± 0.042 / 0.117 ± 0.005 | 0.067 ± 0.005 |
| authguard_seq | F200 | 0.920 ± 0.007 | 0.948 ± 0.012 | 0.277 ± 0.019 / 0.005 ± 0.000 | 0.747 ± 0.024 / 0.045 ± 0.012 | 0.884 ± 0.020 / 0.138 ± 0.003 | 0.091 ± 0.003 |
| authguard_seq | M3+F200 | 0.912 ± 0.005 | 0.947 ± 0.008 | 0.288 ± 0.017 / 0.007 ± 0.000 | 0.745 ± 0.023 / 0.053 ± 0.006 | 0.887 ± 0.011 / 0.149 ± 0.012 | 0.093 ± 0.001 |
| flat_cnn | M0 | 0.890 ± 0.011 | 0.939 ± 0.009 | 0.478 ± 0.035 / 0.013 ± 0.004 | 0.715 ± 0.023 / 0.059 ± 0.003 | 0.791 ± 0.048 / 0.094 ± 0.014 | 0.100 ± 0.006 |
| flat_cnn | F200 | 0.535 ± 0.013 | 0.662 ± 0.009 | 0.094 ± 0.003 / 0.005 ± 0.001 | 0.191 ± 0.010 / 0.048 ± 0.006 | 0.275 ± 0.031 / 0.104 ± 0.025 | 0.223 ± 0.003 |
| flat_cnn | M3+F200 | 0.525 ± 0.011 | 0.660 ± 0.010 | 0.094 ± 0.005 / 0.003 ± 0.001 | 0.185 ± 0.013 / 0.043 ± 0.004 | 0.257 ± 0.028 / 0.102 ± 0.024 | 0.224 ± 0.003 |
| hist_ngram_xgb | M0 | 0.833 ± 0.004 | 0.907 ± 0.002 | 0.320 ± 0.019 / 0.012 ± 0.003 | 0.615 ± 0.015 / 0.071 ± 0.006 | 0.709 ± 0.025 / 0.112 ± 0.014 | 0.127 ± 0.003 |
| hist_ngram_xgb | F200 | 0.576 ± 0.003 | 0.720 ± 0.003 | 0.030 ± 0.003 / 0.002 ± 0.001 | 0.226 ± 0.014 / 0.052 ± 0.006 | 0.317 ± 0.010 / 0.096 ± 0.004 | 0.217 ± 0.001 |
| hist_ngram_xgb | M3+F200 | 0.557 ± 0.007 | 0.717 ± 0.006 | 0.023 ± 0.005 / 0.003 ± 0.002 | 0.202 ± 0.014 / 0.057 ± 0.007 | 0.313 ± 0.012 / 0.100 ± 0.007 | 0.219 ± 0.002 |

The CSV artifacts contain Recall/FPR at all three nominal operating points. Aggregation is fold mean within seed, followed by mean ± population SD across the three seed-level means. Transformed test rows were never used for tuning.
