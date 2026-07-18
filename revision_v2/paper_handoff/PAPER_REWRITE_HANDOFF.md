# AuthGuard-7702 Revision v2 — Paper Rewrite Handoff

## 1. Rewrite objective

Rewrite the paper around one evidence-bounded result: **AuthGuard-Seq is a lightweight, hierarchical opcode-sequence screener that best reproduces source-analyzer risk flags among the compared models under family-disjoint clean and prespecified representation-stress evaluation.** The paper is about pre-authorization triage from runtime bytecode, not ground-truth malicious-contract detection, semantic verification, or a deployed wallet defense.

The rewrite must use the corrected Revision v2 dataset, the official seven-model `baseline_v2` comparison, the three-seed family-clustered paired analysis, and the finalized robustness/operational run. Do not average old and new runs or retain old manuscript numbers for narrative continuity.

## 2. Final research question and framing

### Primary research question

> Can a compact, bytecode-only hierarchical sequence model provide statistically supported screening of source-analyzer-flagged EIP-7702 delegate risk before authorization, while remaining useful under bounded representation stress and practical for local CPU execution?

### Recommended subquestions

1. Does AuthGuard-Seq outperform strong traditional and neural bytecode baselines on family-disjoint clean evaluation?
2. Are its differences from the closest Flat CNN and histogram+n-gram XGBoost baselines supported by paired family-clustered confidence intervals?
3. How do AuthGuard-Seq and the two strongest baselines behave under F200 and M3+F200 representation stress?
4. What degradation does AuthGuard-Seq exhibit relative to its matched clean M0 model outputs?
5. What external-control false-positive and local operational tradeoffs bound deployment interpretation?

### Contribution framing

Use three restrained contributions:

1. A corrected, dependence-aware EIP-7702 bytecode screening benchmark with explicit primary, external, qualitative, and excluded populations.
2. AuthGuard-Seq, a compact hierarchical full-stream opcode encoder, evaluated against six baselines under one frozen family-disjoint protocol.
3. A paired family-clustered and operational evaluation that distinguishes official clean performance, matched degradation, representation stress, external benign controls, and local-only latency.

Avoid “first,” “state of the art,” “production-ready,” and causal architecture claims unless separately substantiated. “Integration-ready” should be replaced by “research prototype with CLI/Python/structured output” unless the paper precisely defines the integration claim.

## 3. Dataset statement to use

AuthGuardBench-7702-v2 contains **3,082 audited rows** partitioned before final evaluation:

- **2,190 primary evaluation rows:** 727 source-analyzer-flagged positives and 1,463 source-unflagged weak negatives, positive fraction 0.332;
- **797 external benign-labeled general-Ethereum controls;**
- **5 curated legitimate qualitative controls;** and
- **90 uncertain/corrupted-source inputs excluded from evaluation.**

The primary population contains **790 frozen bytecode families** and 1,665 unique bytecodes. Five outer folds are family-disjoint. Exact-bytecode label/fold constraints and donor-isolation checks remain part of the protocol. Families approximate related code, not attacker identity.

The label sentence must appear early:

> The primary labels reproduce a source analyzer’s flagged versus unflagged distinction; source silence is a weak negative and does not establish benign semantics, while a source flag does not independently establish malicious intent or exploitation.

Keep the external 797 and curated 5 outside the primary confusion matrix. Never repair the old primary count by silently folding the 90 excluded rows back into the negative class.

## 4. Model and method details that remain valid

AuthGuard-Seq uses deterministic linear-sweep EVM disassembly, stable opcode IDs, a separate padding ID, and PUSH-immediate skipping. It does not truncate at the first linear `STOP`. The opcode stream is partitioned into 256-token chunks, with at most 64 chunks. The audited benchmark maximum (16,081 opcodes) fits the 16,384-token capacity; larger inputs use uniformly spaced chunk selection across the stream.

Each chunk uses a 32-dimensional embedding followed by 1-D convolutions (kernel 5, then kernel 3 with dilation 2), GELU activations, and masked maximum pooling into a 64-dimensional chunk vector. Learned attention aggregates chunk vectors. The contract vector passes through a 128-dimensional GELU/dropout/layer-normalized risk representation and binary head. The final model has **181,877 trainable parameters**.

Training uses class-weighted BCE, AdamW (learning rate 1e-3, weight decay 1e-4), batch size 16, gradient clipping at 5, at most 30 epochs, and patience-5 early stopping on validation AUPRC. Temperature and nominal 1%/5%/10% FPR thresholds are fit on validation data only. For test fold f, fold (f+1) mod 5 is validation and the remaining three folds are training. Seeds are 7702, 7703, and 7704.

Review these implementation facts against the current code during prose integration, but do not change the architecture or retrain.

## 5. Baseline section

Describe all seven frozen clean models, not only XGBoost:

- AuthGuard-Seq;
- Flat CNN, the closest clean competitor and most direct flat-versus-hierarchical sequence comparison;
- normalized opcode-histogram + hashed opcode-4-gram XGBoost;
- neural n-gram-only model;
- BiGRU;
- dense structural/histogram-only neural model; and
- compact Transformer trained from scratch.

All share the same primary rows, family-disjoint folds, validation rotation, seed set, selection rules, calibration, and operating-point construction. The clean table must report `baseline_v2` only.

Official clean headline:

| Model | AUPRC | Recall@5% | AUROC | Brier |
|---|---:|---:|---:|---:|
| **AuthGuard-Seq** | **0.924 ± 0.014** | **0.833 ± 0.016** | **0.963 ± 0.011** | **0.072 ± 0.012** |
| Flat CNN | 0.885 ± 0.010 | 0.712 ± 0.024 | 0.937 ± 0.007 | 0.099 ± 0.004 |
| XGBoost | 0.833 ± 0.004 | 0.615 ± 0.015 | 0.907 ± 0.002 | 0.127 ± 0.003 |

The complete seven-model table is in `FINAL_TABLES.md`. AuthGuard-Seq ranked first on every seed, but describe this as consistency within the completed protocol, not universal model superiority.

## 6. Statistical analysis section

Replace the manuscript’s seed-7702 pooled bootstrap description. The final procedure is:

- statistical unit: frozen bytecode family;
- families sampled with replacement separately within each outer test fold;
- same family multiplicities preserve pairing across models, seeds, and matched conditions;
- compute the metric per fold and seed, average over five folds, then average over seeds 7702/7703/7704;
- 10,000 percentile-bootstrap replicates, seed 77022026; and
- 95% paired-difference CIs are the inferential output. P-values and Holm corrections are not reported.

Primary clean comparisons:

| Comparison | ΔAUPRC [95% CI] | ΔRecall@5% [95% CI] |
|---|---:|---:|
| AuthGuard-Seq − Flat CNN | +0.039 [+0.009,+0.073] | +0.121 [+0.050,+0.190] |
| AuthGuard-Seq − XGBoost | +0.091 [+0.045,+0.140] | +0.217 [+0.124,+0.314] |

All four intervals exclude zero. Do not claim clean Recall@1% superiority to Flat CNN; its secondary interval crosses zero. Keep descriptive means and paired estimands conceptually separate even when their observed deltas match the mean differences.

## 7. Robustness section

Define M0 as normalized original bytecode. Define F200 as deterministic donor-isolated 200% flooding. Define M3+F200 as metadata/address/selector rewriting combined with F200. Transform positives and negatives symmetrically; transformed copies retain the source label and family and are not independent samples.

Use the following transformed descriptive results:

| Model | F200 AUPRC / Recall@5% | M3+F200 AUPRC / Recall@5% |
|---|---:|---:|
| **AuthGuard-Seq** | **0.920 ± 0.007 / 0.747 ± 0.024** | **0.912 ± 0.005 / 0.745 ± 0.023** |
| Flat CNN | 0.535 ± 0.013 / 0.191 ± 0.010 | 0.525 ± 0.011 / 0.185 ± 0.013 |
| XGBoost | 0.576 ± 0.003 / 0.226 ± 0.014 | 0.557 ± 0.007 / 0.202 ± 0.014 |

The eight paired transformed differences versus Flat CNN/XGBoost all exclude zero; use Table III in `FINAL_TABLES.md` for exact CIs.

### Mandatory clean/M0 distinction

The robustness models were produced by a separate neural training execution. The frozen GPU path is not bitwise deterministic, so robustness M0 differs modestly from `baseline_v2`. Therefore:

- use **0.924 AUPRC / 0.833 Recall@5%** for official clean reporting;
- use robustness M0 **0.932 / 0.851** only inside the paired degradation calculation; and
- never place M0 beside the official clean table as if it were a second estimate to choose from.

Matched AuthGuard-Seq degradation:

| Change | ΔAUPRC [95% CI] | ΔRecall@5% [95% CI] |
|---|---:|---:|
| F200 − M0 | −0.013 [−0.030,−0.002] | −0.104 [−0.155,−0.067] |
| M3+F200 − M0 | −0.020 [−0.037,−0.009] | −0.105 [−0.158,−0.067] |

Interpretation: ranking quality decreases modestly, low-FPR recall decreases materially, and AuthGuard-Seq’s relative advantage over the two baselines remains supported. F200 has bounded execution-fingerprint evidence. M3+F200 is representation stress and is not guaranteed behavior-preserving. Do not use “semantic robustness” as an unqualified result label.

## 8. External and qualitative controls

At thresholds selected on primary validation negatives, the 797 external benign-labeled controls yield FPR **0.015 ± 0.004**, **0.065 ± 0.012**, and **0.169 ± 0.021** at the nominal 1%, 5%, and 10% operating points. Present these as threshold transfer to a different benign population. They do not prove a population-wide FPR, and the nominal budgets need not transfer exactly.

The five curated legitimate EIP-7702 controls are qualitative. Across 15 CV models, their mean scores range from 0.077 to 0.270; their 5% flag fractions range from 0 to 0.067. Report examples only if space permits, and state n=5 prominently. A runtime-artifact score/tier is a single illustrative checkpoint output, not a cross-validated estimate.

## 9. Operational section

Use the finalized operational protocol:

- 300 contracts stratified by fold and label across code-size order;
- five repeats, **1,500 full-pipeline calls**;
- AMD Ryzen 5 3600, one CPU thread, Python 3.12.12, PyTorch 2.9.0+cu128;
- full local screening: **5.183 ms mean, 4.121 ms median, 14.547 ms p95, 21.429 ms p99**;
- model load: **7.958 ms mean, 7.690 ms median, 9.716 ms p95, 10.574 ms p99** over 10 loads; and
- forward-only reference: **1.009 ms mean, 0.950 ms median, 1.585 ms p95**.

The full local scope includes runtime-bytecode validation, normalization, disassembly/tokenization, PUSH-immediate skipping, chunk construction/capping, inference, temperature calibration, warning assignment, bytecode-local evidence extraction, and response construction. It excludes RPC/network, blockchain node, wallet UI, and external services.

The timed checkpoint is seed 7702/fold 0 and is used only for timing and illustration. It is not a final retrained deployment model. Report its checkpoint size as **742,625 bytes (725.2 KiB)**. The **737,548-byte** baseline value is raw model-state serialization and must not replace the checkpoint size.

## 10. Terminology contract

Use:

- “source-analyzer-flagged risk,” “source-flagged,” and “source-unflagged weak negative”;
- “pre-authorization screening” or “triage”;
- “family-disjoint held-out evaluation”;
- “nominal 5% validation-negative FPR operating point” and separately “achieved test FPR”;
- “bounded representation stress” and “donor-isolated F200”;
- “M3+F200 representation stress without guaranteed behavior preservation”;
- “local bytecode-only screening latency”; and
- “research prototype” or precisely scoped implementation language.

Avoid:

- “malware detector,” “malicious contract detection,” or “benign ground truth” without the source-label qualifier;
- “adversarially robust,” “semantics-preserving transformations,” or “universal robustness”;
- “safe,” “authorization guarantee,” or “attack prevention”;
- “wallet latency,” “production deployment,” or “final deployment model”; and
- “significant” without naming the paired CI and comparison.

## 11. Obsolete numbers in the current paper

The following values belong to earlier experiment families and must be removed from the abstract, introduction, evaluation, tables, figures, discussion, conclusion, and appendix wherever they appear:

| Obsolete manuscript value | Replacement |
|---|---|
| Primary n=2,280; 1,553 negatives; 819 families | n=2,190; 1,463 negatives; 790 families |
| Positive prevalence 31.9% | 33.2% |
| Clean AuthGuard AUPRC 0.9309/0.931 | 0.924 ± 0.014 |
| Clean AuthGuard Recall@5% 0.8282 | 0.833 ± 0.016 |
| Clean XGBoost AUPRC 0.8276/0.828 | 0.833 ± 0.004 |
| Clean XGBoost Recall@5% 0.5822 | 0.615 ± 0.015 |
| F200 AuthGuard AUPRC 0.9104 | 0.920 ± 0.007 |
| M3+F200 AuthGuard AUPRC 0.9102 | 0.912 ± 0.005 |
| F200/M3+F200 XGBoost AUPRC 0.5765/0.5633 | 0.576 ± 0.003 / 0.557 ± 0.007 |
| Old clean paired AUPRC +0.0571 [0.0023,0.1179] | vs CNN +0.039 [0.009,0.073]; vs XGB +0.091 [0.045,0.140] |
| Old clean paired Recall@5% +0.2118 [0.0952,0.3390] | vs CNN +0.121 [0.050,0.190]; vs XGB +0.217 [0.124,0.314] |
| Old F200 AUPRC Δ +0.3314 | +0.385 vs CNN; +0.344 vs XGB |
| Old M3+F200 AUPRC Δ +0.3254 | +0.387 vs CNN; +0.355 vs XGB |
| External FPR 0.0051/0.0616/0.1000 | 0.015/0.065/0.169 |
| Artifact 742,561 bytes / 0.743 MB | 742,625 bytes / 725.2 KiB |
| Full latency 4.334 mean, 3.172 median, 14.073 p95, 16.906 p99; 3,000 calls | 5.183 mean, 4.121 median, 14.547 p95, 21.429 p99; 1,500 calls |
| Model load 10.047 ms | 7.958 mean / 7.690 median ms |
| Primary-seed-only paired bootstrap | Three-seed fold-preserving family bootstrap |

Also remove old pooled scores (for example 0.8910/0.8339) when explaining final paired results. The final analysis uses the completed fold→seed estimator and its observed deltas.

## 12. Sections and assets requiring revision

1. **Abstract:** replace all dataset, clean, robustness, paired-CI, model-size, call-count, and latency values; remove “malicious delegate” as the unqualified label description.
2. **Introduction:** correct the primary counts and seven-model result; frame Flat CNN as the closest comparator and XGBoost as the strong traditional comparator.
3. **Contributions:** replace “significantly improves … detection” with the scoped paired-CI claim; soften “integration-ready.”
4. **Benchmark:** change 1,553/819 to 1,463/790, positive prevalence to 33.2%, and state that 90 uncertain inputs are excluded.
5. **Methodology:** replace seed-7702 pooled bootstrap with the final three-seed, per-fold family bootstrap. Update baseline coverage from one strongest baseline to seven clean models and three robustness models.
6. **RQ organization:** use the five subquestions in Section 2 of this handoff. The current causal “which architectural choice accounts for performance?” wording is too strong; retain old selection/ablation findings only as supporting development evidence, not a final causal contribution.
7. **Clean results:** replace `tables/three_seed_results.tex` from `baseline_v2`; include Flat CNN and preferably all seven models.
8. **Paired results:** replace `tables/paired_bootstrap.tex` with final clean, F200, M3+F200, and matched-degradation CIs.
9. **Robustness figure:** regenerate `figures/clean_and_transformed_performance.pdf` from the supplied figure CSVs. Keep official clean and robustness M0 visually distinct; the simplest main figure should plot F200 and M3+F200 only, with official clean in the model-comparison figure/table.
10. **External/operational table:** replace `tables/benign_runtime.tex`; state separate-control and local-only scopes.
11. **Operational-artifact paragraph:** update checkpoint bytes and fold-specific role.
12. **Discussion/limitations:** retain source-label, external-population, static-information, transformation-validity, and wallet-boundary limitations; update quantitative values.
13. **Conclusion:** use 0.924 clean, 0.920 F200, 0.912 M3+F200, final paired claims, and finalized latency. End with triage—not safety-certificate—language.
14. **Appendix/reproducibility:** update statistical unit/estimator/seeds and runtime repeat count; keep hyperparameters only if code-verified.

## 13. Recommended results narrative

Begin with the corrected seven-model clean comparison: AuthGuard-Seq ranks first at 0.924 AUPRC and 0.833 Recall@5%, followed by Flat CNN at 0.885/0.712 and XGBoost at 0.833/0.615. Then present the final clean paired CIs, emphasizing that the smaller but most demanding comparison is versus Flat CNN. Next report transformed-input performance and paired relative advantages. Immediately follow with the matched degradation result so the robustness claim acknowledges that Recall@5% falls by about 0.10 even while relative performance remains strong. Close the results with external threshold-transfer FPR and measured local latency.

This ordering yields a defensible message: **best clean performance, supported closest-baseline differences, retained relative advantage under stress, measurable absolute degradation, and explicit operational/external limits.**

## 14. Suggested replacement abstract result core

> We evaluate AuthGuard-Seq on a corrected primary corpus of 2,190 EIP-7702 delegates (727 source-analyzer-flagged and 1,463 source-unflagged weak negatives) grouped into 790 bytecode families. Across three seeds and five family-disjoint folds, AuthGuard-Seq achieves 0.924±0.014 AUPRC and 0.833±0.016 Recall at the nominal 5% validation-negative FPR operating point, compared with 0.885±0.010/0.712±0.024 for Flat CNN and 0.833±0.004/0.615±0.015 for histogram+n-gram XGBoost. Three-seed family-clustered paired intervals support both clean advantages. Under F200 and M3+F200 representation stress, AuthGuard-Seq retains 0.920 and 0.912 AUPRC, while its matched Recall@5% decreases by approximately 0.104–0.105. A 181,877-parameter fold-specific checkpoint completes the measured local screening pipeline in 4.121 ms median and 14.547 ms p95 over 1,500 CPU calls. These results support lightweight bytecode triage of source-analyzer risk flags, not independently verified maliciousness, semantic safety, or end-to-end wallet performance.

## 15. Handoff files

- `FINAL_RESULTS_MANIFEST.md`: authoritative values and boundary notes.
- `FINAL_CLAIMS.md`: allowed, qualified, and unsupported claims.
- `FINAL_TABLES.md`: five compact IEEE-ready table designs and merge guidance.
- `FINAL_FIGURE_DATA/main_model_comparison.csv`: clean seven-model plotting data.
- `FINAL_FIGURE_DATA/robustness_comparison.csv`: matched robustness plotting data with M0 role labels.
- `FINAL_FIGURE_DATA/operational_latency.csv`: operational plotting data.
- `EXPERIMENT_SOURCE_MAP.md`: exact result-to-source provenance.

No experiment output, frozen artifact, current paper source, architecture, or model was modified to create this handoff.
