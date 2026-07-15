# Original versus Task-Aligned v1 Results

The task-alignment policy and manifest were frozen and hashed before any rerun outcome was read. Original artifacts remain unchanged. Values below are fold means unless marked as pooled.

## Cohort change

| item | original | task-aligned v1 | change |
|---|---:|---:|---:|
| all samples | 3,258 | 3,082 | -176 |
| malicious | 793 | 727 | -66 |
| benign_cleared | 1,657 | 1,553 | -104 |
| benign_general | 800 | 797 | -3 |
| benign_AA | 8 | 5 | -3 |
| malicious-bearing families | 214 | 209 | -5 |

Designators: 32/76 runtimes recovered; 3 safely retained, 29 excluded as cross-family exact duplicates, and 44 excluded unresolved. Exact conflicts: all 23 hashes / 103 rows quarantined. The retained manifest has zero cross-class exact hashes.

## G-DET

| method | family AUPRC original | family AUPRC v1 | Δ | random AUPRC original | random AUPRC v1 | Δ |
|---|---:|---:|---:|---:|---:|---:|
| sensitive-name approximation | 0.344 | 0.344 | -0.000 | 0.352 | 0.349 | -0.003 |
| external-call over-approximation | 0.341 | 0.328 | -0.013 | 0.341 | 0.327 | -0.014 |
| blocklist | 0.324 | 0.321 | -0.003 | 0.558 | 0.551 | -0.007 |
| selector-LR | 0.519 | 0.515 | -0.004 | 0.558 | 0.559 | +0.001 |
| opcode-RF | 0.775 | 0.744 | -0.032 | 0.941 | 0.969 | +0.028 |
| opcode-XGB | 0.789 | 0.784 | -0.005 | 0.948 | 0.965 | +0.017 |
| AuthGuard | 0.856 | 0.881 | +0.025 | 0.961 | 0.975 | +0.015 |

AuthGuard random-minus-family gap: 0.104 → 0.094 (change -0.010).

## G-MUT

| method | tier | original recall | v1 recall | Δ |
|---|---|---:|---:|---:|
| sensitive-name approximation | M0 | 0.038 | 0.043 | +0.005 |
| sensitive-name approximation | M1 | 0.038 | 0.043 | +0.005 |
| sensitive-name approximation | M2 | 0.038 | 0.043 | +0.005 |
| sensitive-name approximation | M3 | 0.000 | 0.000 | +0.000 |
| external-call over-approximation | M0 | 1.000 | 1.000 | +0.000 |
| external-call over-approximation | M1 | 1.000 | 1.000 | +0.000 |
| external-call over-approximation | M2 | 1.000 | 1.000 | +0.000 |
| external-call over-approximation | M3 | 1.000 | 1.000 | +0.000 |
| blocklist | M0 | 0.000 | 0.000 | +0.000 |
| blocklist | M1 | 0.000 | 0.000 | +0.000 |
| blocklist | M2 | 0.000 | 0.000 | +0.000 |
| blocklist | M3 | 0.000 | 0.000 | +0.000 |
| selector-LR | M0 | 0.617 | 0.618 | +0.001 |
| selector-LR | M1 | 0.621 | 0.619 | -0.002 |
| selector-LR | M2 | 0.623 | 0.614 | -0.009 |
| selector-LR | M3 | 0.621 | 0.613 | -0.008 |
| opcode-XGB | M0 | 0.656 | 0.544 | -0.113 |
| opcode-XGB | M1 | 0.659 | 0.603 | -0.056 |
| opcode-XGB | M2 | 0.518 | 0.463 | -0.055 |
| opcode-XGB | M3 | 0.518 | 0.463 | -0.055 |
| AuthGuard | M0 | 0.641 | 0.576 | -0.065 |
| AuthGuard | M1 | 0.668 | 0.608 | -0.060 |
| AuthGuard | M2 | 0.588 | 0.530 | -0.058 |
| AuthGuard | M3 | 0.588 | 0.530 | -0.058 |

## G-VOL compound M3-style flooding

| method | flood | original recall | v1 recall | Δ |
|---|---:|---:|---:|---:|
| opcode-XGB | +0% | 0.659 | 0.603 | -0.056 |
| opcode-XGB | +25% | 0.523 | 0.426 | -0.096 |
| opcode-XGB | +50% | 0.498 | 0.410 | -0.088 |
| opcode-XGB | +100% | 0.473 | 0.342 | -0.132 |
| opcode-XGB | +200% | 0.485 | 0.279 | -0.207 |
| AuthGuard | +0% | 0.668 | 0.608 | -0.060 |
| AuthGuard | +25% | 0.567 | 0.527 | -0.040 |
| AuthGuard | +50% | 0.500 | 0.474 | -0.027 |
| AuthGuard | +100% | 0.310 | 0.291 | -0.019 |
| AuthGuard | +200% | 0.139 | 0.130 | -0.009 |

## G-ADV stricter validation protocol

| model | condition | metric | original | v1 | Δ |
|---|---|---|---:|---:|---:|
| AuthGuard-M0 | M0 | AUPRC | 0.830 | 0.819 | -0.011 |
| AuthGuard-M0 | M0 | recall | 0.797 | 0.759 | -0.038 |
| AuthGuard-M0 | M0 | FPR | 0.192 | 0.134 | -0.059 |
| AuthGuard-M0 | M3 | AUPRC | 0.754 | 0.768 | +0.014 |
| AuthGuard-M0 | M3 | recall | 0.787 | 0.767 | -0.020 |
| AuthGuard-M0 | M3 | FPR | 0.276 | 0.181 | -0.095 |
| AuthGuard-M0 | F200 | AUPRC | 0.596 | 0.561 | -0.034 |
| AuthGuard-M0 | F200 | recall | 0.624 | 0.484 | -0.139 |
| AuthGuard-M0 | F200 | FPR | 0.314 | 0.217 | -0.097 |
| AuthGuard-aug | M0 | AUPRC | 0.849 | 0.863 | +0.013 |
| AuthGuard-aug | M0 | recall | 0.761 | 0.807 | +0.046 |
| AuthGuard-aug | M0 | FPR | 0.164 | 0.108 | -0.056 |
| AuthGuard-aug | M3 | AUPRC | 0.814 | 0.825 | +0.012 |
| AuthGuard-aug | M3 | recall | 0.801 | 0.796 | -0.005 |
| AuthGuard-aug | M3 | FPR | 0.196 | 0.120 | -0.075 |
| AuthGuard-aug | F200 | AUPRC | 0.750 | 0.758 | +0.008 |
| AuthGuard-aug | F200 | recall | 0.790 | 0.727 | -0.063 |
| AuthGuard-aug | F200 | FPR | 0.275 | 0.174 | -0.101 |
| opcode-histogram XGBoost | M0 | AUPRC | 0.772 | 0.757 | -0.015 |
| opcode-histogram XGBoost | M0 | recall | 0.660 | 0.661 | +0.001 |
| opcode-histogram XGBoost | M0 | FPR | 0.176 | 0.161 | -0.015 |
| opcode-histogram XGBoost | M3 | AUPRC | 0.710 | 0.695 | -0.015 |
| opcode-histogram XGBoost | M3 | recall | 0.696 | 0.675 | -0.022 |
| opcode-histogram XGBoost | M3 | FPR | 0.230 | 0.201 | -0.029 |
| opcode-histogram XGBoost | F200 | AUPRC | 0.562 | 0.529 | -0.033 |
| opcode-histogram XGBoost | F200 | recall | 0.606 | 0.601 | -0.006 |
| opcode-histogram XGBoost | F200 | FPR | 0.352 | 0.347 | -0.004 |
| opcode-histogram XGBoost-aug | M0 | AUPRC | 0.758 | 0.752 | -0.006 |
| opcode-histogram XGBoost-aug | M0 | recall | 0.725 | 0.779 | +0.054 |
| opcode-histogram XGBoost-aug | M0 | FPR | 0.209 | 0.284 | +0.074 |
| opcode-histogram XGBoost-aug | M3 | AUPRC | 0.727 | 0.723 | -0.003 |
| opcode-histogram XGBoost-aug | M3 | recall | 0.772 | 0.807 | +0.035 |
| opcode-histogram XGBoost-aug | M3 | FPR | 0.233 | 0.304 | +0.071 |
| opcode-histogram XGBoost-aug | F200 | AUPRC | 0.688 | 0.696 | +0.008 |
| opcode-histogram XGBoost-aug | F200 | recall | 0.701 | 0.756 | +0.055 |
| opcode-histogram XGBoost-aug | F200 | FPR | 0.324 | 0.386 | +0.062 |

## Task-aligned pooled family-shape results

| condition | model | pooled recall | singleton recall | family-macro recall |
|---|---|---:|---:|---:|
| M0 | AuthGuard-M0 | 0.754 | 0.777 | 0.804 |
| M0 | AuthGuard-aug | 0.798 | 0.786 | 0.828 |
| M3 | AuthGuard-M0 | 0.762 | 0.839 | 0.826 |
| M3 | AuthGuard-aug | 0.785 | 0.857 | 0.850 |
| F200 | AuthGuard-M0 | 0.448 | 0.554 | 0.556 |
| F200 | AuthGuard-aug | 0.702 | 0.830 | 0.800 |

## Review conclusion

The revised cohort changes several operating-point results materially. G-DET AuthGuard AUPRC increases, but G-MUT retained recall falls and the unaugmented G-ADV F200 recall falls sharply. Augmentation remains beneficial at F200 under fold-mean, pooled, singleton, family-macro, and family-clustered-bootstrap analyses. The old numerical headlines should therefore be replaced rather than combined with v1 values.
