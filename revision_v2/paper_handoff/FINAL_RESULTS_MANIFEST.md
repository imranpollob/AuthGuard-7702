# AuthGuard-7702 Revision v2 — Final Results Manifest

Status: **paper handoff authority**. This file synthesizes completed outputs only; it does not define or report a new experiment.

## Authority and aggregation rules

- **Official clean results:** `revision_v2/experiments/baseline_v2/baseline_summary.csv`. These are the only clean headline numbers.
- **Robustness results:** `revision_v2/experiments/robustness_operational_v2/robustness_summary.csv`.
- **Matched clean M0:** the robustness-run M0 is used only as the paired reference for clean-to-transformed degradation. It is not a replacement for the official `baseline_v2` clean result. Separate neural training executions are not bitwise identical on the frozen GPU path.
- **Descriptive aggregation:** three-seed mean ± sample SD across seed-level means; each seed aggregates five family-disjoint outer folds.
- **Inference:** paired, family-clustered percentile bootstrap; 10,000 replicates, fixed seed 77022026, with fold-to-seed aggregation preserved. Report 95% CIs; do not introduce p-values.
- **Task boundary:** labels denote source-analyzer-flagged versus source-unflagged EIP-7702 delegate risk. They are not independently adjudicated malicious/benign ground truth.

## 1. Dataset audit counts

| Population | Rows | Role |
|---|---:|---|
| PRIMARY_EVALUATION | 2,190 | Official model comparison: 727 source-flagged, 1,463 source-unflagged |
| EXTERNAL_BENIGN_CONTROL | 797 | Separate benign-labeled general-Ethereum control |
| QUALITATIVE_CONTROL | 5 | Curated legitimate EIP-7702 controls; descriptive only |
| EXCLUDED_UNCERTAIN_INPUT | 90 | Excluded from evaluation |
| **Total audited rows** | **3,082** | All populations |

Primary evaluation contains 790 frozen families and 1,665 unique bytecodes. The positive fraction is 0.332. Family-disjoint fold sizes are 446/446/427/447/424.

## 2. Official clean model comparison

All entries are mean ± SD across the three seed-level means. Recall columns use validation-selected nominal FPR operating points; achieved test FPR is reported separately.

| Rank | Model | AUPRC | AUROC | Brier | Recall@1% | Recall@5% | Recall@10% |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | **AuthGuard-Seq** | **0.924 ± 0.014** | **0.963 ± 0.011** | **0.072 ± 0.012** | **0.569 ± 0.047** | **0.833 ± 0.016** | **0.917 ± 0.040** |
| 2 | Flat CNN | 0.885 ± 0.010 | 0.937 ± 0.007 | 0.099 ± 0.004 | 0.474 ± 0.029 | 0.712 ± 0.024 | 0.790 ± 0.038 |
| 3 | Histogram+n-gram XGBoost | 0.833 ± 0.004 | 0.907 ± 0.002 | 0.127 ± 0.003 | 0.320 ± 0.019 | 0.615 ± 0.015 | 0.709 ± 0.025 |
| 4 | n-gram only | 0.810 ± 0.007 | 0.880 ± 0.020 | 0.125 ± 0.001 | 0.170 ± 0.031 | 0.654 ± 0.029 | 0.776 ± 0.010 |
| 5 | BiGRU | 0.679 ± 0.098 | 0.815 ± 0.069 | 0.163 ± 0.027 | 0.160 ± 0.063 | 0.379 ± 0.113 | 0.521 ± 0.117 |
| 6 | Dense only | 0.637 ± 0.018 | 0.780 ± 0.022 | 0.182 ± 0.009 | 0.116 ± 0.015 | 0.331 ± 0.023 | 0.488 ± 0.021 |
| 7 | Transformer | 0.563 ± 0.031 | 0.730 ± 0.019 | 0.208 ± 0.013 | 0.042 ± 0.012 | 0.239 ± 0.054 | 0.371 ± 0.074 |

For AuthGuard-Seq, achieved FPRs were 0.016 ± 0.001, 0.052 ± 0.007, and 0.128 ± 0.013 at the nominal 1%, 5%, and 10% operating points.

## 3. Final paired family-clustered confidence intervals

### Official clean comparisons

| Comparison | Metric | Paired Δ | 95% CI |
|---|---|---:|---:|
| AuthGuard-Seq − Flat CNN | AUPRC | +0.039 | [+0.009, +0.073] |
| AuthGuard-Seq − Flat CNN | Recall@5% | +0.121 | [+0.050, +0.190] |
| AuthGuard-Seq − XGBoost | AUPRC | +0.091 | [+0.045, +0.140] |
| AuthGuard-Seq − XGBoost | Recall@5% | +0.217 | [+0.124, +0.314] |

### Transformed-input comparisons

| Condition | Comparator | Metric | Paired Δ | 95% CI |
|---|---|---|---:|---:|
| F200 | Flat CNN | AUPRC | +0.385 | [+0.302, +0.472] |
| F200 | Flat CNN | Recall@5% | +0.556 | [+0.463, +0.655] |
| F200 | XGBoost | AUPRC | +0.344 | [+0.286, +0.397] |
| F200 | XGBoost | Recall@5% | +0.521 | [+0.442, +0.607] |
| M3+F200 | Flat CNN | AUPRC | +0.387 | [+0.309, +0.468] |
| M3+F200 | Flat CNN | Recall@5% | +0.561 | [+0.471, +0.659] |
| M3+F200 | XGBoost | AUPRC | +0.355 | [+0.296, +0.409] |
| M3+F200 | XGBoost | Recall@5% | +0.543 | [+0.467, +0.629] |

All 12 primary/supporting comparison intervals above exclude zero. A secondary clean Recall@1% comparison against Flat CNN crosses zero and must not be presented as supported superiority.

## 4. Robustness and matched degradation

| Model | Condition | AUPRC | Recall@5% | Achieved FPR@5% |
|---|---|---:|---:|---:|
| AuthGuard-Seq | M0 matched clean* | 0.932 ± 0.006 | 0.851 ± 0.015 | 0.049 ± 0.007 |
| AuthGuard-Seq | F200 | **0.920 ± 0.007** | **0.747 ± 0.024** | 0.045 ± 0.012 |
| AuthGuard-Seq | M3+F200 | **0.912 ± 0.005** | **0.745 ± 0.023** | 0.053 ± 0.006 |
| Flat CNN | F200 | 0.535 ± 0.013 | 0.191 ± 0.010 | 0.048 ± 0.006 |
| Flat CNN | M3+F200 | 0.525 ± 0.011 | 0.185 ± 0.013 | 0.043 ± 0.004 |
| XGBoost | F200 | 0.576 ± 0.003 | 0.226 ± 0.014 | 0.052 ± 0.006 |
| XGBoost | M3+F200 | 0.557 ± 0.007 | 0.202 ± 0.014 | 0.057 ± 0.007 |

\* M0 is a paired robustness-run reference only. The official clean AuthGuard-Seq result remains 0.924 AUPRC and 0.833 Recall@5% from `baseline_v2`.

| AuthGuard-Seq change | Metric | Paired Δ | 95% CI |
|---|---|---:|---:|
| F200 − matched M0 | AUPRC | −0.013 | [−0.030, −0.002] |
| F200 − matched M0 | Recall@5% | −0.104 | [−0.155, −0.067] |
| M3+F200 − matched M0 | AUPRC | −0.020 | [−0.037, −0.009] |
| M3+F200 − matched M0 | Recall@5% | −0.105 | [−0.158, −0.067] |

F200 has bounded execution-fingerprint support. M3+F200 is representation stress; its rewriting is not guaranteed to preserve semantics. Neither condition supports a universal semantic-robustness claim.

## 5. External benign control

Across 797 external benign-labeled general-Ethereum contracts, mean FPR across seed means was:

| Nominal primary-validation operating point | External FPR |
|---|---:|
| 1% | 0.015 ± 0.004 |
| 5% | 0.065 ± 0.012 |
| 10% | 0.169 ± 0.021 |

Mean calibrated score was 0.115 ± 0.003 and median calibrated score was 0.061 ± 0.008. This control is population-shift evidence, not an extension of the primary confusion matrix.

## 6. Operational measurements

| Measurement | Calls | Mean | Median | p95 | p99 |
|---|---:|---:|---:|---:|---:|
| Full local screening pipeline | 1,500 | 5.183 ms | 4.121 ms | 14.547 ms | 21.429 ms |
| Model load | 10 | 7.958 ms | 7.690 ms | 9.716 ms | 10.574 ms |
| Model forward reference | 195 | 1.009 ms | 0.950 ms | 1.585 ms | — |

- Trainable parameters: **181,877**.
- Runtime artifact: **742,625 bytes (725.2 KiB)**, including checkpoint metadata.
- Raw baseline model-state serialization: **737,548 bytes (720.3 KiB)**. Do not substitute this for the operational artifact size.
- Timing environment: AMD Ryzen 5 3600, one CPU thread, Python 3.12.12, PyTorch 2.9.0+cu128.
- Full-pipeline scope includes bytecode validation, normalization, disassembly/tokenization, chunking, inference, calibration, warning tier, evidence extraction, and response construction. RPC/network, node, wallet UI, and external services are excluded.
- The timed seed-7702/fold-0 checkpoint is a fold-specific cross-validation artifact used for timing and illustration, not a final deployment model.

## 7. Qualitative legitimate controls

Each aggregate is over 15 CV models. Flag rates are fractions of those models. The single runtime score/tier comes from the timing artifact and is illustrative.

| Control | 15-model mean score | Runtime score (tier) | Flag rate @1% / @5% / @10% |
|---|---:|---:|---:|
| `0x0000000020fe…7E9D` | 0.138 | 0.381 (caution) | 0.00 / 0.07 / 0.27 |
| `0x000000005c84…030e` | 0.077 | 0.154 (low observed risk) | 0.00 / 0.00 / 0.00 |
| `0x690077027641…E139` | 0.122 | 0.304 (caution) | 0.00 / 0.00 / 0.07 |
| `0xd6CEDDe84be4…5b28` | 0.270 | 0.491 (caution) | 0.07 / 0.07 / 0.53 |
| `0xe40ccB2D9497…6fA4` | 0.160 | 0.494 (caution) | 0.07 / 0.07 / 0.27 |

With n=5, these examples are qualitative sanity checks only; they do not establish a benign false-positive rate.
