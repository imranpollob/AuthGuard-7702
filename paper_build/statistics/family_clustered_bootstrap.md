# Family-Clustered Paired Bootstrap

Fixed base seed: 7702. Replicates per cohort/condition: 10,000.

Each replicate samples frozen test families with replacement, retains every contract in each sampled family, and preserves the AuthGuard-M0/AuthGuard-aug pairing. Intervals are percentile 95% intervals. Positive recall differences favor augmentation; negative FPR differences favor augmentation.

## original

| condition | pooled recall M0→aug | Δ recall [95% CI] | pooled FPR M0→aug | Δ FPR [95% CI] | Δ AUPRC [95% CI] | families |
|---|---:|---:|---:|---:|---:|---:|
| M0 | 0.803→0.772 | -0.032 [-0.121, 0.038] | 0.189→0.158 | -0.031 [-0.055, -0.011] | — | 890 |
| M3 | 0.794→0.808 | 0.014 [-0.018, 0.050] | 0.270→0.189 | -0.081 [-0.107, -0.057] | — | 890 |
| F200 | 0.636→0.797 | 0.161 [0.068, 0.285] | 0.313→0.266 | -0.046 [-0.079, -0.014] | 0.220 [0.151, 0.290] | 890 |

## task_aligned_v1

| condition | pooled recall M0→aug | Δ recall [95% CI] | pooled FPR M0→aug | Δ FPR [95% CI] | Δ AUPRC [95% CI] | families |
|---|---:|---:|---:|---:|---:|---:|
| M0 | 0.754→0.798 | 0.044 [-0.045, 0.133] | 0.135→0.111 | -0.024 [-0.048, -0.001] | — | 819 |
| M3 | 0.762→0.785 | 0.023 [-0.040, 0.080] | 0.185→0.126 | -0.059 [-0.083, -0.037] | — | 819 |
| F200 | 0.448→0.702 | 0.253 [0.144, 0.379] | 0.228→0.179 | -0.049 [-0.086, -0.014] | 0.248 [0.177, 0.322] | 819 |

## Interpretation rule

Use the task-aligned-v1 intervals for the revised paper numbers. The original cohort is retained only to reconcile the earlier contract-level bootstrap. Do not use the old contract-resampled interval as a submission headline.
