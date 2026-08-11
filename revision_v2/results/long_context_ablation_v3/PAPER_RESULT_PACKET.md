# AuthGuard-7702 v3 paper result packet

All transformed results below use the declared per-model cap before scoring.

| Model | Budget | Parameters | Clean AUPRC | F200 AUPRC | F200 Recall@5% |
|---|---:|---:|---:|---:|---:|
| Flat control (2K) | 2,048 | 29,985 | 0.879 +/- 0.005 | 0.532 +/- 0.017 | 0.148 +/- 0.013 |
| Flat control (16K) | 16,384 | 29,985 | 0.936 +/- 0.003 | 0.810 +/- 0.014 | 0.506 +/- 0.038 |
| Chunk attention (2K) | 2,048 | 30,050 | 0.902 +/- 0.003 | 0.897 +/- 0.009 | 0.817 +/- 0.022 |
| Chunk mean (16K) | 16,384 | 29,985 | 0.879 +/- 0.005 | 0.728 +/- 0.020 | 0.274 +/- 0.031 |
| Chunk attention (16K) | 16,384 | 30,050 | 0.918 +/- 0.007 | 0.908 +/- 0.001 | 0.815 +/- 0.039 |
| Legacy AuthGuard reference (16K) | 16,384 | 181,877 | 0.914 +/- 0.013 | 0.894 +/- 0.006 | 0.786 +/- 0.021 |

## Predeclared mechanism contrasts

| Mechanism | Condition | Delta AUPRC | Family-bootstrap 95% CI | Decision |
|---|---|---:|---:|---|
| coverage | M0 | +0.0152 | [-0.0028, +0.0300] | INCONCLUSIVE |
| attention | M0 | +0.0386 | [+0.0072, +0.0643] | SUPPORTED |
| hierarchy | M0 | -0.0181 | [-0.0400, +0.0182] | INCONCLUSIVE |
| coverage | F200 | +0.0112 | [-0.0051, +0.0252] | INCONCLUSIVE |
| attention | F200 | +0.1800 | [+0.1348, +0.2316] | SUPPORTED |
| hierarchy | F200 | +0.0980 | [+0.0590, +0.1544] | SUPPORTED |

## Predeclared clean length diagnostic

| Model | Source <=2,048 AUPRC | Source >2,048 AUPRC |
|---|---:|---:|
| Flat control (16K) | 0.946 +/- 0.009 | 0.918 +/- 0.017 |
| Chunk mean (16K) | 0.892 +/- 0.003 | 0.885 +/- 0.005 |
| Chunk attention (16K) | 0.921 +/- 0.006 | 0.936 +/- 0.012 |
| Legacy AuthGuard reference (16K) | 0.928 +/- 0.008 | 0.922 +/- 0.023 |

The fold-stratified controlled contrasts, not the standalone legacy AuthGuard
reference row, determine the mechanism claims. Fold results and per-row
predictions remain in the source CSV artifacts.
