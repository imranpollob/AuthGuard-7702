# Robustness and Operational Final Summary

## Direct answers

**A. F200 ranking.** AuthGuard-Seq remains the highest-performing model on F200: AUPRC 0.920 ± 0.007 and Recall@5% 0.747 ± 0.024.

**B. M3+F200 ranking.** AuthGuard-Seq remains the highest-performing model on M3+F200: AUPRC 0.912 ± 0.005 and Recall@5% 0.745 ± 0.023.

**C. Clean to F200.** AuthGuard-Seq changes by -0.013 ± 0.005 AUPRC and -0.104 ± 0.027 Recall@5% (paired across seed-level fold means).

**D. Clean to M3+F200.** AuthGuard-Seq changes by -0.020 ± 0.001 AUPRC and -0.105 ± 0.024 Recall@5% (paired across seed-level fold means).

**E. Relative robustness.** AuthGuard-Seq remains ahead under every condition. Versus Flat CNN, the AUPRC margin is +0.043 on M0, +0.385 on F200 (increases), and +0.387 on M3+F200 (increases). Versus XGBoost, the AUPRC margin is +0.099 on M0, +0.344 on F200 (increases), and +0.355 on M3+F200 (increases). The detailed delta CSV also reports paired Recall@5% margins.

**F. External benign control.** On 797 external benign-labeled general Ethereum contracts, FPR is 0.015 ± 0.004, 0.065 ± 0.012, and 0.169 ± 0.021 at the nominal 1%, 5%, and 10% primary-validation thresholds, respectively. This is a separate external control, not part of primary classification.

**G. Curated legitimate controls.** The five n=5 qualitative controls are shown below. Score is the mean across 15 CV models; decision columns are fractions of the 15 models that flagged the sample. The warning tier in parentheses is from the named runtime timing artifact.

| Sample | Mean score | Runtime-artifact score (tier) | 1% flag rate | 5% flag rate | 10% flag rate |
|---|---:|---:|---:|---:|---:|
| ethereum:0x0000000020fe2F30453074aD916eDeB653eC7E9D | 0.138 | 0.381 (caution) | 0.00 | 0.07 | 0.27 |
| ethereum:0x000000005c84F8Fd50b21CAC312528A64437030e | 0.077 | 0.154 (low_observed_risk) | 0.00 | 0.00 | 0.00 |
| ethereum:0x69007702764179f14F51cdce752f4f775d74E139 | 0.122 | 0.304 (caution) | 0.00 | 0.00 | 0.07 |
| ethereum:0xd6CEDDe84be40893d153Be9d467CD6aD37875b28 | 0.270 | 0.491 (caution) | 0.07 | 0.07 | 0.53 |
| ethereum:0xe40ccB2D94975c51bff0C004eFDfd9B3a5796fA4 | 0.160 | 0.494 (caution) | 0.07 | 0.07 | 0.27 |

**H. Model-forward latency.** The completed baseline measured median batch-1 CPU forward latency of 0.950 ms (mean 1.009 ms; p95 1.585 ms).

**I. Full local screening latency.** Across 1,500 calls, mean was 5.183 ms, median 4.121 ms, p95 14.547 ms, and p99 21.429 ms. Model load (7.690 ms median) is reported separately.

**J. Runtime artifact.** `revision_v2/experiments/robustness_operational_v2/models/model_authguard_seq_s7702_f0.pt` is the seed-7702/fold-0 cross-validation artifact used only for runtime and illustrative qualitative scoring. It is not presented as a final retrained deployment model. Cross-validation metrics use all 15 independently trained fold/seed models.

**K. Strongest paper-safe claims.** AuthGuard-Seq remains the best of the three frozen models under clean, 200% flooding, and combined representation stress; it maintains strong transformed-input ranking performance without transformed-test tuning; and complete local CPU screening remains practical for interactive pre-authorization use. F200 has bounded execution-fingerprint support. M3+F200 must be described as representation stress because its rewriting is not guaranteed to preserve behavior.

**L. Critical issues.** No critical implementation issue invalidated the completed dataset or baseline results. XGBoost reproduced bit-for-bit. The neural clean reruns showed modest fold-level GPU variance because the frozen baseline code explicitly disables deterministic algorithms; aggregate AUPRC changed by +0.008 for AuthGuard-Seq and +0.005 for Flat CNN, while the model ranking and conclusions were preserved. Donor isolation and frozen-ledger verification passed.

## Interpretation boundary

The benchmark measures screening of source-analyzer-flagged risk, not independently confirmed malicious attacks. The primary source-flagged and source-unflagged samples come from the same observed EIP-7702 population. External and curated legitimate controls remain separate.
