# AuthGuard-7702 Revision v2 — Final Claim Set

Use the following language boundaries in the rewrite. “AuthGuard-Seq” is the proposed hierarchical bytecode sequence model; “risk” means correspondence to source-analyzer flags within the audited EIP-7702 benchmark.

## Claims directly supported by completed evidence

1. **Clean ranking:** On the corrected 2,190-contract primary evaluation, AuthGuard-Seq ranked first among seven frozen models, with AUPRC 0.924 ± 0.014 and Recall@5% 0.833 ± 0.016 across three seeds.
2. **Clean paired advantage:** Family-clustered paired 95% CIs support higher clean AUPRC and Recall@5% than Flat CNN and histogram+n-gram XGBoost. The smallest supported clean AUPRC difference is +0.039 versus Flat CNN, CI [+0.009, +0.073].
3. **Transformed-input ranking:** AuthGuard-Seq remained first among the three robustness models under F200 and M3+F200, reaching 0.920/0.912 AUPRC and 0.747/0.745 Recall@5%, respectively.
4. **Transformed-input paired advantage:** All prespecified AUPRC and Recall@5% intervals versus Flat CNN and XGBoost under F200 and M3+F200 exclude zero.
5. **Measured degradation:** Relative to its matched robustness-run M0, AuthGuard-Seq showed small AUPRC decreases (−0.013 F200; −0.020 M3+F200) and larger Recall@5% decreases (−0.104 and −0.105); all four degradation intervals exclude zero.
6. **External control:** On a separate set of 797 external benign-labeled general-Ethereum contracts, mean FPR was 0.015, 0.065, and 0.169 at thresholds selected for nominal 1%, 5%, and 10% FPR on primary validation data.
7. **Operational measurement:** The measured local bytecode-only screening pipeline had median latency 4.121 ms and p95 14.547 ms across 1,500 calls on the stated CPU environment. The timed artifact has 181,877 parameters and occupies 742,625 bytes.
8. **Descriptive controls:** Five curated legitimate EIP-7702 contracts were scored across 15 CV models; these examples are qualitative controls, not a rate estimate.

## Claims that require their qualifier

- Say **“source-analyzer-flagged risk screening”**, **“source-flagged/source-unflagged”**, or **“reproduces the source analyzer’s flag decision from bytecode.”** Do not shorten this to malicious-contract detection.
- Say **“family-disjoint cross-validation within the audited benchmark.”** Do not imply future-family, temporal, chain-wide, or ecosystem-wide generalization.
- Say **“F200 has bounded execution-fingerprint support.”** Do not claim complete semantic equivalence.
- Say **“M3+F200 representation stress.”** Its rewriting is not guaranteed to preserve behavior.
- Say **“best among the compared frozen models.”** Do not claim state of the art unless a defensible, task-matched literature comparison is added separately.
- Say **“practical in the measured local CPU setting”** or report the measurements. Do not generalize to wallet end-to-end latency because RPC, node, UI, and external services were excluded.
- Say **“fold-specific checkpoint used for timing.”** Do not call it a final trained deployment artifact.
- Use M0 only in **matched degradation** sentences. Use `baseline_v2` for all clean headline comparisons.

## Claims not supported by this evidence

- Independently confirmed maliciousness, exploitation, loss, intent, or attack success.
- Universal semantic, adversarial, metamorphic, or cross-compiler robustness.
- Production readiness, deployed-wallet effectiveness, user-study benefit, or real-world attack prevention.
- A causal claim that hierarchical attention alone produced the gain. The model comparison supports an architectural association under the frozen protocol, not component-level causality without a dedicated ablation.
- A population-wide benign FPR. The external control is a separate shifted population, and the five curated cases are too small for estimation.
- Statistical superiority at clean Recall@1% versus Flat CNN; that secondary CI crosses zero.
- Bitwise reproducibility of the neural GPU training path. The completed protocol preserves conclusions but separate executions yield modest neural variation.
- P-values or Holm-adjusted p-values. The prespecified inferential output is the family-clustered percentile CI.

## Recommended single-sentence central claim

> On a corrected, family-disjoint benchmark of source-analyzer-flagged EIP-7702 delegate risk, AuthGuard-Seq outperformed six frozen baselines on clean bytecode and retained statistically supported advantages over Flat CNN and XGBoost under two prespecified representation-stress conditions, while local CPU screening remained millisecond-scale in the measured environment.

## Recommended limitations sentence

> These results measure bytecode-level reproduction of source-analyzer risk flags rather than independently verified maliciousness; M3+F200 is not guaranteed behavior-preserving, and the operational benchmark excludes RPC, node, wallet-UI, and deployment effects.
