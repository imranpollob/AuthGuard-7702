# Paper Outline: ICTAI 2026, Eight-Page Anonymous Submission

Proposed title: **AuthGuard-7702: Family-Grouped, Evasion-Aware Bytecode Risk Screening Before EIP-7702 Authorization**

Paper identity: an AI-tools paper about an evaluation-grade bytecode-scoring prototype. The estimator is standard; the tool setting, leakage-resistant evaluation, evasion benchmark, and adversarial-training procedure are the center of the paper.

## 1. Abstract — 0.25 page

Plan only:

- EIP-7702 pre-signing risk decision and bytecode-only input.
- Implemented scorer and family-grouped protocol.
- Three headline numbers, each labeled by protocol: G-DET 0.856 AUPRC; random 0.961; G-ADV +200% recall/AUPRC 0.624/0.596 → 0.790/0.750.
- One qualification: clean-recall tradeoff and rule-derived labels.
- No “first,” full-USENIX comparison, semantic-equivalence statement, or complete-wallet latency claim.
- Index Terms immediately after the abstract.

## 2. Introduction — 0.75 page

Plan:

- Signing-time security gap created by EIP-7702 delegation.
- Practical requirement: score available runtime bytecode quickly before authorization.
- AI difficulty: near-duplicate families inflate random evaluation; redeployment transformations stress learned features.
- Gap: existing artifact supports retrospective/rule-derived labels, while this work studies a bytecode-only screening setting. Avoid claiming that the full prior pipeline was reproduced.
- Three contribution sentences from `claim_plan.md`.
- State the scoped task: distinguish USENIX-artifact positives from rule-silent delegates under unseen-family testing.

## 3. Background and Related Work — 0.78 page

Planned subsections:

### 3.1 EIP-7702 execution and signing-time input

- Delegation designator and runtime delegate code.
- Why delegate bytecode is the prototype’s input.
- Keep protocol mechanics short; do not overstate account authority beyond cited EVM/EIP semantics.

### 3.2 Closest EIP-7702 malicious-delegation work

- Describe the USENIX artifact and label provenance.
- Distinguish the full Gigahorse/Datalog pipeline from the two local approximations.
- Explicit sentence: the full pipeline was not executed.

### 3.3 Smart-contract ML and leakage/robustness literature

- Bytecode/opcode malware and vulnerability classifiers.
- Grouped/temporal evaluation and clone leakage.
- Adversarial malware transformations and robust training.
- A current literature audit is required before finalizing this section; do not make priority claims.

## 4. Problem Definition and Threat Model — 0.45 page

Plan:

- Input: normalized runtime bytecode supplied to the scorer.
- Output: scalar risk score and thresholded warning for an external caller.
- Target label: rule-labeled malicious versus rule-silent weak negatives.
- Defender: wallet or screening service integrating the scorer; external integration is not claimed as implemented.
- Adversary: can redeploy and apply metadata, address-immediate, selector, and dead-code transformations while retaining attack capability.
- Security boundary: no source code, on-chain history, signer portfolio, decompiler, or network latency in the evaluated core.
- Mutation terminology: structure-preserving; EVM execution equivalence not verified.

## 5. AuthGuard-7702 Design — 1.05 pages

Planned subsections:

### 5.1 Prototype architecture

- Implemented boundary: bytecode input → deterministic linear disassembly → features → XGBoost score → threshold.
- Offline family assignment/training path.
- External dashed context: authorization parser, code fetch/cache, wallet warning; label as integration context, not implemented modules.
- Figure 1: new vector architecture.

### 5.2 Bytecode representation

- 225 normalized opcode histogram features.
- 512 hashed opcode 4-grams.
- 36 structural and selector features.
- One shared feature implementation for bulk and mutation-time scoring.
- Banned label-derived and provenance features.

### 5.3 Estimator and decision rule

- Standard XGBoost configuration and risk score.
- Distinguish G-DET in-sample training threshold from G-ADV validation threshold.
- Frame estimator as an engineering choice, not a novelty claim.

### 5.4 Evasion-aware training

- Source-balanced variant weighting.
- Split families before mutation.
- Seen and held-out augmentation conditions.
- Keep implementation detail sufficient for reproduction, not a long algorithm listing.

## 6. Dataset and Experimental Methodology — 0.85 page

Planned subsections:

### 6.1 Corpus and label limitations

- Table 1 with all four subsets, counts, family-bearing counts, label source, and role.
- Positive labels are USENIX-artifact-derived.
- `benign_cleared` is weak; 8.1% is a heuristic upper bound.
- Mention 76 bare designators as a data-quality limitation if space allows.

### 6.2 Frozen global families

- Deterministic MinHash-estimated similarity and union-find at 0.85.
- Global rather than per-class grouping because of conflicting exact bytecodes.
- Counts: 1,329 global / 214 positive-bearing / 52.8% positive-member singletons.
- Threshold-sensitivity counts go in artifact/supplement, not the main paper.

### 6.3 Four protocol groups and metrics

- Compact protocol box or paragraph defining G-DET, G-MUT, G-VOL, and G-ADV.
- AUPRC primary; AUROC and operating-point metrics secondary.
- Five outer family folds; G-ADV validation separation.
- Random split is diagnostic context only.
- State leakage assertions.

## 7. Evaluation — 1.95 pages

The evaluation section should answer five research questions without mixing protocols.

### RQ1: How well does the scorer generalize to held-out families? — G-DET

- Table 2: family-grouped performance.
- AuthGuard 0.856 ± 0.043 AUPRC; compare only with G-DET baselines.
- Explain why the external-call over-approximation’s recall is not useful at base-rate precision.
- Do not include the tautological shipped-oracle row in the main table.

### RQ2: How much does a random split inflate performance? — G-DET

- Figure 2: regenerated family-versus-random AUPRC plot.
- AuthGuard gap 0.105; blocklist 0.324 → 0.558 as the memorization diagnostic.
- Avoid universal claims about prior work.

### RQ3: What survives structure-preserving redeployment transformations? — G-MUT

- Table 3: M0--M3 retained recall.
- Sensitive-name rule approximation 0.038 → 0.000; AuthGuard 0.641 → 0.588.
- External-call structural over-approximation remains at 1.000 while non-discriminative under G-DET.
- State 793/793 checker passes and its limited meaning.

### RQ4: Does leakage-safe augmentation improve held-out robustness? — G-ADV

- Table 4: AuthGuard-M0 versus AuthGuard-aug at clean M0, held-out M3, and held-out pure-M0 +200%.
- Figure 3: paired heavy-flood recovery and benign FPR, clearly labeled G-ADV.
- Heavy flood: recall 0.624 → 0.790; AUPRC 0.596 → 0.750; FPR 0.314 → 0.275.
- Clean tradeoff: AUPRC 0.830 → 0.849 and FPR 0.192 → 0.164, but recall 0.797 → 0.761.
- Mention singleton/family-macro results in one sentence.
- Do not print a 95% interval until family-clustered resampling is available.

### RQ5: Is the implemented scorer fast enough for integration? — local core runtime

- One sentence or compact inline values: 3.37 ms mean, 10.67 ms p95.
- Explicitly exclude network and wallet latency.
- State hardware once provenance is recorded.

## 8. Discussion and Limitations — 0.48 page

Prioritized limitations:

1. Circular positive-label provenance; no missed-family discovery claim.
2. Weak negatives and heuristic contamination upper bound.
3. Independent set is INSUFFICIENT DATA with one truly novel confirmed positive.
4. Structure preservation is not execution equivalence.
5. Full USENIX Gigahorse/Datalog pipeline was not executed.
6. Residual +200% FPR of 0.275 and clean-recall reduction.
7. Compound M3 + 200% G-ADV condition was not tested; G-VOL’s 0.139 remains unrecovered.
8. Research scorer lacks evaluated wallet/network integration.

One forward-work sentence: reachability-aware features, family-aware uncertainty, larger independent labels, and wallet-level evaluation.

## 9. Conclusion — 0.22 page

Plan:

- Restate the tool and the evaluation lesson, not a new result.
- One sentence each for family generalization, random inflation, and scoped robustness recovery.
- End on pre-signing screening as a practical direction with residual-risk disclosure.
- No priority, completeness, or state-of-the-art claim.

## 10. References — 1.00 page

Plan:

- Replace the embedded hand-written list with a verified bibliography workflow.
- Target roughly 18--24 tightly relevant references, subject to final IEEE layout.
- Required coverage: EIP-7702 specification; closest EIP-7702 security work; EVM static analysis; smart-contract bytecode ML; malware leakage/grouping; adversarial malware; adversarial training/evaluation.
- Cite the true authors of related work; double-blind review anonymizes this submission, not unrelated references.

## Narrative order and exclusions

Keep the paper’s causal chain:

`pre-signing need → implemented scorer → family leakage problem → mutation benchmark → leakage-safe augmentation → limitations`.

Exclude from the eight-page main paper:

- explanation/nearest-neighbor audit;
- synthetic signer-loss examples;
- independent-set funnel figure;
- full family-threshold table;
- full G-VOL sweep table/figure;
- seen-condition augmentation plots;
- score-distribution grid;
- detailed per-fold tables.

These may live in an anonymous supplement or artifact, but none should be needed to understand the main claims.
