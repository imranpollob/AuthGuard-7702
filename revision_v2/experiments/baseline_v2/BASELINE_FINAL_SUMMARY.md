# Baseline Final Summary — Revision v2 Model Comparison

Corrected benchmark, PRIMARY_EVALUATION (727 source-flagged vs 1,463 source-unflagged
EIP-7702 delegates, 790 frozen families). Seeds 7702/7703/7704 × 5 family-disjoint
outer folds, identical protocol, validation-based selection and calibration, no
test-set tuning. Numbers are 3-seed means ± SD across seed-level means.
Source table: `revision_v2/experiments/baseline_v2/baseline_summary.csv`.

| rank | model | AUPRC | Recall@5%FPR | AUROC |
|---|---|---|---|---|
| 1 | **AuthGuard-Seq** | **0.924 ± 0.014** | **0.833 ± 0.016** | 0.963 |
| 2 | flat CNN | 0.885 ± 0.010 | 0.712 ± 0.024 | 0.937 |
| 3 | hist+4-gram XGBoost | 0.833 ± 0.004 | 0.615 ± 0.015 | 0.908 |
| 4 | ngram_only (neural) | 0.810 ± 0.007 | 0.654 ± 0.029 | 0.880 |
| 5 | BiGRU | 0.679 ± 0.098 | 0.379 ± 0.113 | 0.815 |
| 6 | dense_only (structural) | 0.637 ± 0.018 | 0.331 ± 0.023 | 0.780 |
| 7 | Transformer | 0.563 ± 0.031 | 0.239 ± 0.054 | 0.730 |

**A. Best AUPRC:** AuthGuard-Seq, 0.924.

**B. Best Recall@5%FPR:** AuthGuard-Seq, 0.833.

**C. Does AuthGuard-Seq outperform XGBoost?** Yes — +0.091 AUPRC (0.924 vs 0.833) and
+0.218 Recall@5%, on every seed (Δ +0.088/+0.080/+0.105).

**D. Does AuthGuard-Seq outperform the flat CNN?** Yes — +0.039 AUPRC (0.924 vs 0.885)
and +0.121 Recall@5%, on every seed (Δ +0.033/+0.039/+0.046). This is the closest
competitor and the most important comparison: hierarchical chunk-attention adds a real,
consistent increment over strong flat convolutions.

**E. Does AuthGuard-Seq outperform BiGRU?** Yes, by a wide margin — +0.245 AUPRC
(0.924 vs 0.679). BiGRU is also unstable (see H).

**F. Does AuthGuard-Seq outperform the Transformer?** Yes, by the widest margin —
+0.362 AUPRC (0.924 vs 0.563). A compact from-scratch Transformer is the weakest model
at this data scale.

**G. Are the improvements consistent across seeds?** Yes. AuthGuard-Seq ranks #1 on all
three seeds and beats every baseline on every seed; the top-4 ordering
(Seq > CNN > XGBoost > ngram_only) is identical across seeds. AuthGuard-Seq seed spread
is 0.031 AUPRC.

**H. Are any models unstable?** Yes — **BiGRU** (AUPRC SD 0.098; seed 7703 collapses to
0.541 vs 0.744/0.753; Recall@5% SD 0.113) is optimization-fragile over long recurrent
opcode sequences. The **Transformer** is stably weak. All other models are stable
(SD ≤ 0.018). AuthGuard-Seq, CNN, XGBoost, and ngram_only are all stable.

**I. Performance-vs-cost tradeoff:** AuthGuard-Seq is **Pareto-optimal**. CPU batch-1
forward latency: 1.0 ms median (182K params, 720 KB) — the fastest of the four
sequence models and best accuracy. The flat CNN is 2.5× slower for -0.039 AUPRC;
BiGRU (60 ms) and Transformer (24 ms) are 1–2 orders slower for far worse accuracy.
XGBoost/dense/ngram are sub-millisecond but 0.09–0.29 AUPRC behind. AuthGuard-Seq's
~1 ms is negligible for interactive pre-authorization screening.

**J. Does the evidence support retaining AuthGuard-Seq as the proposed model?**
**Yes.** It is the most accurate model on both the ranking metric (AUPRC) and the
operational metric (Recall@5%FPR), wins against every traditional and neural baseline
on every seed, is stable, is well-calibrated (lowest Brier 0.072), and is among the
cheapest to run. The comparison also shows the win is non-trivial — three of the
neural baselines fall below the strong XGBoost baseline — so the advantage is
specifically attributable to hierarchical opcode-sequence modeling, not merely to
using a neural network.

*Terminology note:* per `revision_v2/audit/LABEL_CLAIM_CONTRACT.md`, "outperform" here
means reproducing the source analyzer's flag decision from bytecode alone
(source-identified risk screening), not detecting independently confirmed malicious
contracts.

Outputs: `baseline_summary.csv`, `baseline_fold_seed_results.csv`,
`baseline_predictions.csv.gz`, `baseline_model_complexity.csv`,
`BASELINE_EVALUATION_REPORT.md`, `BASELINE_IMPLEMENTATION_NOTES.md`
(mirrored under `revision_v2/results/baseline_v2/`).
