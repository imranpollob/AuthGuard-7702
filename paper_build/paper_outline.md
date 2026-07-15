# Paper Outline — Task-Aligned v1

Proposed title: **AuthGuard-7702: Task-Aligned, Family-Grouped Bytecode Risk Screening for EIP-7702 Delegation**

Paper identity: an AI-tools paper about an evaluation-grade bytecode scorer. The standard estimator is not the novelty. The central contribution is the task-aligned dataset audit, family-controlled evaluation, checker-scoped evasion benchmark, and family-disjoint augmentation study.

This file is a drafting plan only; no Abstract or Introduction prose is authorized by this gate.

## 1. Abstract — 0.25 page

Plan only:

- EIP-7702 pre-authorization screening need and runtime-bytecode input.
- Outcome-blind data-hygiene freeze and preserved family-fold evaluation.
- At most three result clauses from `claim_plan.md`: .881/.975 G-DET AUPRC, F200 .484/.561/.217→.727/.758/.174, and family-clustered recall difference +.253 [.144,.379].
- Required qualifications: USENIX-artifact positives, weak negatives, checker-scoped transformations, and scorer-core boundary.
- No priority, full-pipeline superiority, semantic-equivalence, or complete-wallet claim.

## 2. Introduction — 0.75 page

Plan only:

- Signing-time security gap created by delegated runtime code.
- Practical question: can bytecode already available to an integration be screened before authorization?
- Evaluation risk: designators are not delegate runtimes, exact cross-class conflicts make a bytecode-only target ill-posed, and related bytecode inflates random evaluation.
- Scoped objective: distinguish artifact-derived positives from rule-silent weak negatives on held-out frozen families.
- Three contribution sentences from the revised claim plan.

## 3. Background and Related Work — 0.75 page

### 3.1 EIP-7702 execution and input identity

- Distinguish a delegating account's designator from target runtime code.
- Explain why verified target runtime—not the designator—is the model input.

### 3.2 Closest malicious-delegation work

- Describe USENIX artifact label provenance.
- Separate the full USENIX Gigahorse/Datalog pipeline from the two local approximations.
- State that the full pipeline was not executed.

### 3.3 Smart-contract ML leakage and robustness

- Bytecode/opcode classification, clone leakage, grouped evaluation, adversarial program transformations, and robust training.
- Complete a current verified literature matrix before prose drafting; make no priority claim.

## 4. Problem Definition and Threat Model — 0.45 page

- Input: verified normalized delegate runtime bytecode supplied to the scorer.
- Output: risk score and optional thresholded warning for an external integration.
- Target: artifact-derived malicious versus rule-silent weak negative.
- Defender boundary: scorer is implemented; wallet parser, RPC/cache, UI, and deployment are integration context.
- Adversary: can redeploy with metadata, address-immediate, selector, and dead-code changes while attempting to retain attack capability.
- Mutation boundary: structure preservation under the opcode-skeleton checker; execution equivalence not established.

## 5. AuthGuard-7702 Design — 1.00 page

### 5.1 Implemented scorer and external boundary

- Solid implemented path: bytecode → deterministic disassembly/features → XGBoost → score/threshold.
- Offline training path: task-aligned manifest → preserved families/folds → optional weighted variants → model/threshold.
- Dashed context only: authorization parsing, code retrieval/cache, wallet warning.

### 5.2 Representation and estimator

- 225 opcode-histogram features, 512 hashed opcode 4-grams, and 36 structural/selector features; total 773.
- Shared feature implementation for bulk and mutation-time scoring.
- Banned label, capability, chain, class, and family inputs.
- Standard XGBoost configuration; frame as an engineering choice.

### 5.3 Evasion-aware training

- Split families before mutation.
- Source-normalized M0/M1/M2/F25/F50/F100 training variants.
- M3 and pure-M0 F200 held out in G-ADV.

## 6. Dataset and Experimental Methodology — 1.00 page

### 6.1 Outcome-blind task alignment

- Protocol frozen and hashed before reruns.
- Audit all 76 designators: 32 recovered, 3 retained, 29 cross-family duplicates excluded, 44 unresolved excluded.
- Quarantine all 23 conflicting hashes/103 rows; no relabeling.
- Revised Table 1: 3,082 observations; 727/1,553/797/5 subsets; 1,258 retained frozen families.

### 6.2 Dependence and weak labels

- Unit is chain/address; 233 same-class exact groups/787 observations remain within family folds.
- Zero cross-class exact hashes and zero hashes spanning families.
- 115/1,553 weak negatives share a positive-bearing similarity family; 7.4% is a heuristic, not a contamination estimate.
- Positive labels remain artifact-derived; independent evidence is N=1.

### 6.3 Frozen families and protocols

- Deterministic global similarity families at the original threshold; no reclustering or fold rebalancing.
- Define G-DET, G-MUT, G-VOL, and G-ADV in a compact protocol box.
- AUPRC primary; operating-point metrics secondary.
- Distinguish training thresholds in G-DET/G-MUT from validation thresholds in G-ADV.
- State leakage assertions and family-clustered paired bootstrap procedure.

## 7. Evaluation — 1.85 pages

### RQ1: Family-held-out detection — G-DET

- Table 2 with task-aligned fold means.
- AuthGuard .881 ± .028 AUPRC, .943 AUROC, .869 precision, .576 recall, .673 F1.
- Baselines only from the same G-DET protocol; omit the tautological class-reading oracle.

### RQ2: Random-versus-family sensitivity — G-DET

- Figure 2 with family/random pairs: blocklist .321/.551, selector-LR .515/.559, opcode-RF .744/.969, opcode-XGB .784/.965, AuthGuard .881/.975.
- Use the exact safe interpretation: family-grouped testing controls related-bytecode leakage and provides a more demanding generalization estimate.

### RQ3: Checker-scoped redeployment transformations — G-MUT/G-VOL

- Table 3: sensitive-name approximation .043→0; AuthGuard M0–M3 .576/.608/.530/.530.
- State 727/727 checker passes and explicitly deny execution-equivalence evidence.
- One limitation sentence for compound G-VOL F200 AuthGuard recall .130.

### RQ4: Family-disjoint augmentation — G-ADV

- Table 4: clean M0, held-out M3, and held-out pure-M0 F200 fold means.
- F200 AuthGuard-M0→aug: AUPRC .561→.758, recall .484→.727, FPR .217→.174.
- Figure 3 combines fold-mean operating points with separately labeled family-clustered pooled differences.
- Inferential headline: pooled recall +.253 [.144,.379], FPR -.049 [-.086,-.014], AUPRC +.248 [.177,.322].
- State that clean and M3 recall intervals include zero and fold effects are heterogeneous.
- Mention singleton .554→.830 and family-macro .556→.800.

### RQ5: Local scorer-core runtime

- Apple M1, 3,000 single calls: mean 3.411 ms, p95 9.514 ms.
- Batched 300-contract mean: 3.197 ms/contract.
- Bytecode preloaded; exclude model loading, RPC, wallet/UI, and network.

## 8. Discussion and Limitations — 0.55 page

Prioritize:

1. Artifact-derived positives and weak negatives; no discovery or calibrated prevalence claim.
2. Outcome-blind exclusions change the cohort by 176 observations; the paper's target is runtime-bytecode screening, not delegating-account designators.
3. Contextual or label-noise conflicts cannot be resolved from bytecode alone.
4. Chain/address observations retain same-class duplicates; family folds control but do not erase dependence.
5. Independent generalization remains insufficient at N=1.
6. Structure preservation is checker-defined, not execution equivalence.
7. Full USENIX pipeline and compound M3+F200 augmentation were not evaluated.
8. F200 fold effects are heterogeneous and AuthGuard-aug retains .174 FPR.
9. Runtime covers a local scorer core on one consumer machine, not wallet/network integration.

Forward work: larger independent labels, contextual ground truth, reachability-aware features, family-aware uncertainty, compound transformations, and wallet-level evaluation.

## 9. Conclusion — 0.20 page

Plan only:

- Restate the implemented scorer and the data-validity lesson.
- Separate family-held-out detection, random sensitivity, and scoped F200 robustness.
- End with residual-risk and integration-boundary disclosure.

## 10. References — 1.00 page

- Use a verified bibliography workflow and current literature matrix.
- Cover EIP-7702, closest malicious-delegation work, EVM/static analysis, bytecode ML, clone/group leakage, adversarial program transformations, and robust evaluation.
- Preserve true related-work authorship under double-blind review.

## Narrative and exclusions

Narrative order:

`input identity and hygiene → implemented scorer → family-controlled evaluation → checker-scoped evasion → family-disjoint augmentation → limitations`.

Exclude from the eight-page main paper: explanation audit, synthetic signer-loss examples, independent funnel figure, threshold-sensitivity grid, full G-VOL sweep, seen-condition augmentation plots, score-distribution grids, and detailed per-fold tables. Original-cohort results belong only in an explicitly labeled artifact sensitivity report.
