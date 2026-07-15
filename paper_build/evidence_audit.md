# AuthGuard-7702 Evidence Audit

Audit date: 2026-07-15  
Purpose: establish what the repository supports before drafting an anonymous, eight-page ICTAI 2026 paper.

## Audit conclusion

The repository supports a defensible AI-tools paper about an implemented bytecode risk scorer, family-grouped evaluation, an evasion benchmark, and leakage-safe adversarial augmentation. The existing paper is not an authoritative source and should not be revised by copying its claims. It predates G-ADV, uses disallowed terminology, overstates several baselines, and does not match the required section order.

The evidence does **not** currently support describing AuthGuard-7702 as a complete wallet-integrated pre-signing product. The implemented core consists of bytecode preprocessing, feature extraction, model training, thresholding inside evaluation pipelines, and prediction. No standalone AuthGuard inference command, serialized deployment model, authorization parser, wallet integration, production code-fetch path, or user-warning interface was found. The paper should call it an implemented **bytecode-scoring research prototype** and depict wallet/RPC integration as external context unless those missing modules are added.

## Evidence hierarchy used

1. Raw datasets and frozen assignments.
2. Machine-readable experiment outputs and paired predictions.
3. Training, inference, mutation, and analysis code.
4. Assertion logs and generated reports.
5. Narrative reports.
6. The current LaTeX paper, which is treated only as a list of claims to audit.

When sources disagreed, levels 1--3 controlled the finding.

## Artifacts inspected

| Evidence area | Primary artifacts inspected |
|---|---|
| Current paper and references | `paper/authguard7702.tex`; no `.bib` file found |
| Requested reports | all named files under `reports/`, including reconciliation, narrative, evaluation, claim, table, figure, discussion, gap, synthesis, and adversarial-training reports |
| Dataset and labels | `capability_dataset.csv`; `USENIX EIP-7702 artifact/eoa_detect/detect_result.jsonl`; supporting Phase 0/reconciliation reports |
| Family assignment | `family_assignment_frozen.csv`; `results/family_structure.json`; `pipeline/01_freeze_families.py`; `pipeline/ag_common.py` |
| Features | `results/feature_meta.json`; both feature `.npz` files; `pipeline/02_features.py`; `pipeline/ag_features.py` |
| G-DET | `results/detection_results.json`; `pipeline/03_detection.py` |
| G-MUT and G-VOL | `results/mutation_curve.json`; `results/mutation_preservation.json`; `results/mutation_volume.json`; `pipeline/04_mutations.py` |
| G-ADV | `advtrain_results.json`; `paired_results.csv`; `reports/advtrain_*`; `pipeline/adv_run.py`; `pipeline/adv_analysis.py` |
| Runtime and contamination | `results/supporting.json`; `pipeline/05_supporting.py` |
| Independent set | independent-set protocol, funnel, targets, per-contract predictions, detector output, and `pipeline/ind_*.py` |
| Figures | all ten PNG files under `figures/`, including visual inspection of the principal detection, family, mutation, flooding, and G-ADV plots |

## Verified dataset facts

Directly recomputed from `capability_dataset.csv`:

| Subset | Contracts | Distinct frozen families bearing the subset | Subset-member singleton families | Role and label status |
|---|---:|---:|---:|---|
| malicious | 793 | 214 | 113 (52.8% of malicious-bearing families) | positives derived from the USENIX artifact |
| benign_cleared | 1,657 | 711 | 464 | rule-silent, weak primary negatives |
| benign_general | 800 | 440 | 364 | general-contract secondary negatives; single provenance |
| benign_AA | 8 | 8 | 8 | small hand-verified control only |
| **Total** | **3,258** | **1,329 global families** | **912 global singletons** | all rows have a unique `(chain,address)` key |

Additional checks:

- The class totals sum to 3,258.
- The frozen family CSV has 3,258 rows and matches `(address, chain, class)` row-for-row with the dataset.
- There are 2,616 distinct normalized bytecodes and 2,961 distinct addresses; addresses reused across chains are kept as distinct samples.
- There are 23 exact bytecodes with more than one class label, covering 103 rows. Global clustering prevents these identical bytecodes from crossing family splits.
- Twenty `benign_cleared` rows are byte-identical to a malicious row.
- Seventy-six `benign_cleared` rows are bare EIP-7702 designators (`ef0100 || address`), not delegate runtime bytecode.
- The raw USENIX `eoa_detect/detect_result.jsonl` contains 793 address objects (the final physical line contains concatenated JSON objects, so `wc -l` reports 792 and must not be used as the record count).
- Positive labels are derived from the USENIX artifact. The repository does not provide independently adjudicated ground truth at useful scale.

## Verified family facts

The frozen assignment is global and deterministic in code: seeded BLAKE2b-based, 128-permutation MinHash estimates over opcode 4-grams, followed by union-find. The similarity is a **MinHash-estimated** Jaccard value, not an exact all-pairs Jaccard computation.

At the frozen estimated-similarity threshold of 0.85:

- 1,329 global families.
- 912 global singleton families (68.6%).
- largest global family: 58 contracts.
- 184 cross-chain families (13.8%).
- 44 cross-class families (3.3%).
- the 793 positives occupy 214 families.
- 178 families are purely malicious; 36 malicious-bearing families also contain another class.
- 113 malicious-bearing families contain one malicious member (52.8%).
- largest malicious membership in one family: 58.

Threshold sensitivity from the frozen machine-readable artifact:

| Estimated threshold | Global families | Singleton % | Largest | Cross-chain % | Cross-class % |
|---:|---:|---:|---:|---:|---:|
| 0.75 | 1,120 | 66.9 | 89 | 14.3 | 4.4 |
| **0.85** | **1,329** | **68.6** | **58** | **13.8** | **3.3** |
| 0.90 | 1,511 | 71.7 | 48 | 13.0 | 2.4 |

Use “five-fold family-grouped cross-validation” in the paper. The code has five outer test folds; for G-DET/G-MUT, each outer model is trained on the other four folds. Calling this simply “leave-one-family-out” would be misleading because one family is not held out per run.

## Verified feature and implementation facts

- `features_dense.npz` is finite `float32` with shape `(3258, 261)`.
- `features_ngram.npz` is finite `float32` with shape `(3258, 512)`.
- Dense features contain a 225-bin normalized opcode histogram plus 36 structural/selector features.
- Hashed opcode 4-grams add 512 dimensions, for 773 total model inputs in AuthGuard.
- The feature implementation is shared between bulk extraction and mutation-time inference through `pipeline/ag_features.py`.
- Explicitly banned inputs are the two label-derived capability fields, chain, class, and family ID.
- The AuthGuard estimator is standard XGBoost with 300 trees, maximum depth 6, learning rate 0.1, subsampling 0.9, and column sampling 0.8. It is not a modeling novelty.
- Prediction is implemented and exercised inside the evaluation scripts. A deployable pre-signing application interface is not present.

## Protocol ledger

| Group | Population and split | Threshold protocol | Conditions | Permitted comparison scope |
|---|---|---|---|---|
| G-DET | 793 malicious vs 1,657 `benign_cleared`; five outer family folds; four folds train each run | max-F1 on in-sample training predictions | clean M0; separate random KFold context | primary detection and random-split inflation only |
| G-MUT | same outer family folds; train on M0, mutate held-out positives only | same in-sample train threshold as G-DET-style model | cumulative M0--M3 | retained recall within this mutation protocol |
| G-VOL | same family-grouped model style; held-out positives | in-sample train threshold | metadata/address/selector mutation with variable dead-code flood | compound mutation-plus-flood limitation only |
| G-ADV | five outer family tests; one different outer fold used as validation; remaining three folds train-fit | max-F1 on clean-M0 validation families | seen: M0, M1, M2, F25, F50, F100; held out: M3 and pure-M0 F200 | AuthGuard-M0 vs AuthGuard-aug and augmentation baselines only |

Consequences:

- G-DET AUPRC 0.856 and G-ADV clean AUPRC 0.830 are not contradictory; G-ADV trains on fewer families and selects thresholds on a separate validation fold. AUPRC itself is threshold-free.
- G-VOL 0.139 and G-ADV 0.624 are not the same attack. The former is a compound selector/address/metadata mutation plus heavy flooding; G-ADV F200 is pure-M0 plus 200% flooding.
- No table column or plot axis may directly compare values across these groups.

## Result verification summary

### G-DET

The primary artifact verifies:

- AuthGuard family-grouped AUPRC: 0.8565 ± 0.0435.
- AuthGuard random-split AUPRC: 0.9608 ± 0.0175.
- absolute inflation: 0.1043 (round to 0.105 or “about 0.10”).
- family-grouped AUROC 0.9297, precision 0.8706, recall 0.6410, F1 0.7202.
- opcode-XGB family-grouped AUPRC 0.7893; opcode-RF 0.7753; selector-LR 0.5189.
- blocklist AUPRC 0.3237 with zero recall under family grouping, versus 0.5584 AUPRC and 0.3789 recall under random splits.

The “shipped oracle” row reads the label and is tautological. It should be omitted from the main results table or isolated as a label-provenance sanity check, never presented as a detector baseline.

### G-MUT

`results/mutation_preservation.json` records 793/793 opcode-skeleton checks at M1, M2, and M3. This verifies structure preservation under the repository’s checker; it does **not** verify EVM execution equivalence.

Retained recall (mean over the five folds):

- sensitive-name rule approximation: 0.038, 0.038, 0.038, 0.000 for M0--M3.
- external-call structural over-approximation: 1.000 at all tiers, but it is non-discriminative.
- blocklist: 0.000 at all tiers under family holdout.
- opcode-XGB: 0.656, 0.659, 0.518, 0.518.
- AuthGuard: 0.641, 0.668, 0.588, 0.588.

The full Gigahorse/Datalog USENIX pipeline was not executed. These two lightweight approximations must not be called “the USENIX detector,” and AuthGuard must not be claimed to beat the full system.

### G-VOL

The compound M3-style mutation with variable dead-code flooding yields AuthGuard retained recall of 0.668, 0.567, 0.500, 0.310, and 0.139 at +0%, +25%, +50%, +100%, and +200%. Opcode-XGB yields 0.659, 0.523, 0.498, 0.473, and 0.485. This is a limitation/motivation result, not the G-ADV baseline.

### G-ADV

Fold-mean results from `advtrain_results.json`:

- clean M0 AUPRC: AuthGuard-M0 0.830; AuthGuard-aug 0.849.
- clean M0 recall: 0.797 → 0.761; clean FPR: 0.192 → 0.164.
- held-out M3 AUPRC: 0.754 → 0.814; recall: 0.787 → 0.801; FPR: 0.276 → 0.196.
- held-out pure-M0 +200% flooding AUPRC: 0.596 → 0.750; recall: 0.624 → 0.790; FPR: 0.314 → 0.275.
- opcode-XGB-aug reaches 0.701 recall and 0.688 AUPRC at +200%, below AuthGuard-aug under the same G-ADV protocol.
- +200% singleton-family recall: 0.655 → 0.850; family-macro recall: 0.674 → 0.844.

The paired prediction file contains one row for every one of 2,450 samples × 8 conditions × 5 models = 98,000 rows. Contract-level pooled values differ slightly from fold means, as expected.

The existing paired bootstrap gives a +200% pooled recall change of 0.636 → 0.797 and a 95% interval [0.131, 0.193]. However, `pipeline/adv_analysis.py` resamples contracts independently rather than resampling frozen families. Because contracts within a family are dependent, this interval should not be a submission headline until a family-clustered paired bootstrap is produced. The directional result and aggregate metrics remain valid.

“No clean cost” is unsafe. Clean AUPRC improves and clean FPR falls, but pooled clean recall falls from 0.803 to 0.772; the current contract-level paired interval for the recall change is [-0.053, -0.009]. State the tradeoff.

## Supporting evidence

- `benign_cleared` contamination upper bound: 135/1,657 (8.1%) share a malicious-bearing family; 20/1,657 (1.2%) are exact malicious-bytecode duplicates. This is a heuristic upper bound, not an adjudicated contamination rate.
- Local latency: mean 3.367 ms, p50 2.469 ms, p95 10.673 ms, and batched 3.181 ms/contract over 300 timed samples.
- Latency includes feature extraction plus model prediction. It excludes authorization parsing, RPC/network fetch, caching, wallet UI, and warning presentation.
- The artifact does not record sufficient hardware/OS and timing methodology metadata to make the latency fully reproducible.
- Independent malicious-set result: **INSUFFICIENT DATA**. Only one truly novel, independently confirmed malicious delegate survived the preregistered funnel. The 1/1 AuthGuard outcome is an anecdotal case study, not quantitative generalization or superiority evidence.

## Current-paper conflicts requiring removal or rewrite

1. The author/affiliation/contact block should be removed for double-blind submission, not filled with placeholder identities.
2. “Semantics-preserving” appears repeatedly; replace it with “structure-preserving” or narrowly “attack-capability-preserving” only where justified.
3. “First” appears in all three current contribution claims without a complete literature audit; remove it.
4. Baselines named `USENIX name-rule` and `USENIX struct-rule` must become **sensitive-name rule approximation** and **external-call structural over-approximation**.
5. The current paper implies more of the full USENIX detector than was executed. State explicitly that Gigahorse/Datalog was not run.
6. The current paper predates G-ADV and therefore omits the stricter protocol, augmentation gains, clean-recall reduction, and residual high FPR.
7. The current paper uses G-DET precision beside G-MUT recall in prose. Keep protocols and operating points self-contained.
8. The claim that AuthGuard is “the only method simultaneously robust and discriminative” is too broad; scope any comparison to the evaluated baselines and transformations.
9. The online architecture report includes unimplemented authorization parsing, RPC fetch, and warning modules. Draw those outside the implemented-prototype boundary.
10. The embedded reference list has only ten items, lacks a `.bib` source, anonymizes a cited work’s authors, and is insufficient for a defensible novelty/related-work claim.
11. The current EIP-7702 designator LaTeX renders incorrectly (`\textbackslash,\textbar{}`); use a properly typeset concatenation expression later.

## Figure audit

- `fig_random_vs_family.png` contains the unsupported title phrase “the leakage every prior split hides” and old baseline naming. Regenerate.
- `fig_mutation_curve.png` says “semantics-preserving” and uses old baseline naming. Regenerate.
- `fig_mutation_volume.png` has a clipped title and should be appendix-only or replaced by one limitation sentence.
- `fig_advtrain_heldout.png` is useful but must identify G-ADV in the caption and explain its error bars. It should not be visually paired as if directly comparable to G-MUT/G-VOL.
- `fig_advtrain_scoredist.png` is legible but too large for the eight-page main paper and needs clearer treatment of fold-varying validation thresholds.
- `fig_family_size.png` is accurate but expendable because Table 1 can carry the necessary counts.

## Double-blind audit

The paper itself contains placeholder author/affiliation/contact content that should be removed. The repository also contains a personal email address in the user-agent strings of `pipeline/ind_01_inventory_getcode.py`, `ind_02_retry_failures.py`, `ind_03_targets_overlap.py`, `ind_04_maliciousness.py`, and `ind_06_detectors.py`. This does not affect the manuscript, but any code artifact supplied during anonymous review must be scrubbed and rechecked for paths, metadata, repository URLs, and identities.

## Missing artifacts and readiness gates

### Must resolve before strong paper claims

- A family-clustered paired bootstrap (or another family-aware paired uncertainty analysis) for G-ADV.
- A precise implementation boundary. Either add a standalone scorer/model artifact, or explicitly present the existing implementation as an evaluation-grade bytecode-scoring prototype.
- A verified, current bibliography/related-work matrix. Until then, do not use “first,” “novel,” or “state of the art.”
- A LaTeX build environment and compiled page-count log. No TeX engine is installed in the current environment, so the current manuscript’s page count could not be verified.
- Runtime provenance: hardware/OS, dependency versions, warm-up policy, and timing repetition details if the 3.37 ms value is retained.

### Evidence that is absent but does not block a correctly scoped paper

- Full USENIX Gigahorse/Datalog execution.
- Large rule-independent malicious validation set.
- EVM execution-equivalence testing for mutations.
- G-ADV evaluation of the compound M3 + 200% flooding condition.
- Complete network/wallet latency and a wallet user study.

These absences block the corresponding stronger claims, not the evidence-supported paper outlined in this build plan.
