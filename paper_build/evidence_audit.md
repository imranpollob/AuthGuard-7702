# AuthGuard-7702 Evidence Audit — Task-Aligned v1

Audit updated: 2026-07-15  
Status: task-validity gate completed before paper drafting.

## Audit conclusion

The original 3,258-row cohort was not fully aligned with a bytecode-only delegate-runtime task: it contained 76 EIP-7702 designators and 23 exact-bytecode hashes carrying conflicting class labels. An outcome-blind policy was frozen and hashed before reruns. The resulting v1 manifest contains 3,082 samples, no designator used as runtime input, no cross-class exact hash, and no retained exact hash spanning frozen families.

All four experiment groups were rerun with preserved original outer family-fold identities and unchanged features, hyperparameters, seeds, threshold procedures, mutation recipes, augmentation recipes, and source weights. Several results changed materially. The paper must use the task-aligned numbers in this audit and retain the original numbers only as a sensitivity comparison.

The implementation remains an evaluation-grade bytecode-scoring prototype: bytecode preprocessing, feature extraction, model training, thresholding, mutation, and prediction are implemented. A wallet authorization parser, production RPC/cache adapter, warning UI, and deployable serialized model/CLI are not part of the evaluated artifact and are not required if the paper keeps this boundary explicit.

## Frozen task-alignment policy

- Protocol: `paper_build/data_hygiene/task_alignment_protocol.md`.
- Protocol SHA-256: `6368be0b35c5b4aca6e067b3fb57aabf7db90a18b4bc6d43c9e969abae16083b`.
- Task-aligned dataset SHA-256: `147f86754bd2a01da1a21d78cce21a4710855a5eff3f6788ab6c3e58b4a8ac5f`.
- No original dataset, family, feature, fold, or result artifact was overwritten.
- No row was relabeled from a model prediction.
- No family was reclustered or reassigned.

## Designator resolution

All 76 designator rows represented delegating accounts, not verified delegate runtime inputs.

| Outcome | Rows |
|---|---:|
| verified target runtime recovered | 32 |
| recovered from existing repository target row | 29 |
| recovered through read-only `eth_getCode` | 3 |
| recovered but excluded because exact runtime existed in another frozen family | 29 |
| recovered and safely retained | 3 |
| unresolved and excluded | 44 |
| total designator-source exclusions | 73 |

The 29 cross-family recoveries could not be retained while simultaneously preserving the source row’s original family and preventing exact input leakage. They were excluded rather than reassigned. The three retained recoveries were previously absent target runtimes obtained read-only on BNB Chain and did not duplicate any dataset bytecode.

Direct audit: `paper_build/data_hygiene/designator_audit.csv`.

## Exact-bytecode conflict quarantine

- 23 original normalized-bytecode hashes carried more than one class.
- They covered 103 rows: 66 malicious, 31 `benign_cleared`, 3 `benign_general`, and 3 `benign_AA`.
- Every complete group was quarantined; no favorable-class-only removal or relabeling occurred.
- No additional conflict was induced by the three retained runtime recoveries.
- Task-aligned cross-class exact hashes: 0.

The conflicts are consistent with unresolved label noise and/or contextual dual use. Bytecode alone cannot disambiguate them. Direct audit: `paper_build/data_hygiene/conflicting_bytecodes.csv`.

## Verified task-aligned dataset

| Subset | Samples | Frozen families bearing subset | Subset-member singleton families | Role |
|---|---:|---:|---:|---|
| malicious | 727 | 209 | 112 (53.6%) | USENIX-artifact positives |
| `benign_cleared` | 1,553 | 635 | 399 | rule-silent weak primary negatives |
| `benign_general` | 797 | 437 | 361 | secondary negatives |
| `benign_AA` | 5 | 5 | 5 | small verified control |
| **Total** | **3,082** | **1,258 global retained families** | **856 global singletons** | task-aligned v1 |

Additional checks:

- Primary malicious fraction: 0.31886.
- Largest retained family: 58.
- Malicious-bearing families: 209.
- Malicious-member singleton families: 112.
- Cross-class similarity families: 28; none is an exact-bytecode conflict.
- Same-class exact duplicate groups: 233, covering 787 rows.
- Exact hashes spanning frozen families: 0.
- Families spanning stored primary or secondary outer folds: 0.

Same-class duplicates remain because the observation unit retains chain/address rows; their dependence is controlled by the preserved global family folds.

## Feature and estimator verification

- Dense feature shape: `(3082, 261)`.
- Hashed opcode 4-gram shape: `(3082, 512)`.
- AuthGuard input dimension: 773.
- The same `pipeline/ag_features.py` implementation produced training and mutation-time features.
- Banned inputs remain label-derived capability fields, chain, class, and family ID.
- Estimator remains standard XGBoost: 300 trees, depth 6, learning rate 0.1, subsample 0.9, column sample 0.8, seed 7702.

## Protocol ledger

| Group | Task-aligned population/split | Threshold | Conditions | Comparison scope |
|---|---|---|---|---|
| G-DET | 727 malicious vs 1,553 `benign_cleared`; preserved five outer family folds | max-F1 on training predictions | M0; seeded random diagnostic separately | primary detection and split sensitivity |
| G-MUT | same preserved folds; train M0; mutate 727 held-out positives across folds | G-DET-style training threshold | cumulative M0--M3 | retained recall within G-MUT |
| G-VOL | preserved folds and M0 training | training threshold | M3-style compound transform plus variable flood | compound flooding limitation |
| G-ADV | preserved test fold; next original fold validation; remaining three train-fit | max-F1 on clean validation families | held-out M3 and pure-M0 F200 | M0 vs augmented models within G-ADV |

The seeded random diagnostic necessarily receives new row assignments after exclusions; its KFold implementation and seed are unchanged. Fixed family folds are read from stored original fold IDs and are not rebalanced.

## Revised G-DET results

Task-aligned primary results, five preserved outer folds:

- AuthGuard AUPRC: **0.881 ± 0.028**.
- AUROC: 0.943.
- precision: 0.869.
- recall: 0.576.
- F1: 0.673.
- random-split AUPRC: **0.975 ± 0.012**.
- random-minus-family AUPRC gap: **0.094**.
- opcode-XGB AUPRC: 0.784; opcode-RF: 0.744; selector-LR: 0.515.
- blocklist: 0.321 family-grouped versus 0.551 random.

Original-to-v1 AuthGuard changes: family AUPRC +0.025, random AUPRC +0.015, and gap -0.010. The safe interpretation is: **family-grouped testing controls related-bytecode leakage and provides a more demanding generalization estimate**.

## Revised G-MUT results

Retained recall M0--M3:

- sensitive-name rule approximation: 0.043, 0.043, 0.043, 0.000.
- external-call structural over-approximation: 1.000 at every tier, but non-discriminative under G-DET.
- blocklist: 0.000 at every tier.
- selector-LR: 0.618, 0.619, 0.614, 0.613.
- opcode-XGB: 0.544, 0.603, 0.463, 0.463.
- AuthGuard: **0.576, 0.608, 0.530, 0.530**.

AuthGuard M3 is 0.058 lower than the original result. The structure checker passed 727/727 retained positives at M1, M2, and M3. It verifies the repository’s opcode-skeleton condition, not EVM execution equivalence.

The full USENIX Gigahorse/Datalog pipeline was not executed. Use only “sensitive-name rule approximation” and “external-call structural over-approximation.”

## Revised G-VOL result

AuthGuard compound M3-style retained recall at +0%, +25%, +50%, +100%, and +200% flooding is 0.608, 0.527, 0.474, 0.291, and **0.130**. Opcode-XGB is 0.603, 0.426, 0.410, 0.342, and **0.279**.

G-VOL remains separate from G-ADV. Do not imply augmentation recovered the 0.130 compound condition.

## Revised G-ADV results

Fold means under the stricter preserved test/validation/train-fit protocol:

| Condition | Model | AUPRC | Precision | Recall | FPR |
|---|---|---:|---:|---:|---:|
| clean M0 | AuthGuard-M0 | 0.819 | 0.720 | 0.759 | 0.134 |
| clean M0 | AuthGuard-aug | 0.863 | 0.763 | 0.807 | 0.108 |
| held-out M3 | AuthGuard-M0 | 0.768 | 0.663 | 0.767 | 0.181 |
| held-out M3 | AuthGuard-aug | 0.825 | 0.743 | 0.796 | 0.120 |
| held-out pure-M0 F200 | AuthGuard-M0 | 0.561 | 0.512 | 0.484 | 0.217 |
| held-out pure-M0 F200 | AuthGuard-aug | 0.758 | 0.654 | 0.727 | 0.174 |

F200 singleton recall is 0.554→0.830; family-macro recall is 0.556→0.800. Opcode-XGB-aug reaches 0.756 fold-mean F200 recall but with 0.386 FPR; AuthGuard-aug’s FPR is 0.174.

## Family-clustered paired uncertainty

Ten thousand fixed-seed replicates sample frozen test families with replacement and preserve model pairing.

Task-aligned pooled differences, AuthGuard-aug minus AuthGuard-M0:

- clean recall: +0.044, 95% CI [-0.045, 0.133].
- clean FPR: -0.024, 95% CI [-0.048, -0.001].
- M3 recall: +0.023, 95% CI [-0.040, 0.080].
- M3 FPR: -0.059, 95% CI [-0.083, -0.037].
- F200 recall: **+0.253, 95% CI [0.144, 0.379]**.
- F200 FPR: **-0.049, 95% CI [-0.086, -0.014]**.
- F200 AUPRC: **+0.248, 95% CI [0.177, 0.322]**.

The old contract-resampled interval is superseded and must not appear as a submission headline.

## Runtime provenance

Frozen local benchmark: Apple M1, 8 GiB, macOS 26.5.1 arm64, Python 3.13.9, XGBoost 3.3.0, NumPy 2.3.4, scikit-learn 1.9.0.

- 30 warm-up calls and 3,000 timed batch-size-1 calls.
- mean: **3.411 ms**; p50: 2.499 ms; p95: **9.514 ms**; p99: 16.578 ms.
- ten timed 300-contract batches: **3.197 ms/contract** mean.

Bytecode was already in memory. Model training/loading, RPC, authorization parsing, caching, UI, and wallet integration were excluded. Call this local feature extraction plus model prediction, not end-to-end wallet latency.

## Independent evidence and limitations

- Independent malicious-set verdict remains **INSUFFICIENT DATA** with one truly novel confirmed positive.
- Positive labels remain derived from the USENIX artifact.
- `benign_cleared` remains a weak negative set; 115/1,553 rows (7.4%) share a retained similarity family with a positive and zero are exact positive duplicates. Treat 7.4% as a conservative malicious-like-family heuristic, not a measured contamination rate.
- Mutations are structure-preserving under the checker, not execution-equivalent.
- Compound M3 + F200 was not evaluated under G-ADV.
- Full USENIX pipeline and wallet-level evaluation were not run.
- F200 AuthGuard-aug residual FPR is 0.174; robustness is improved, not complete.
- Fold-level G-ADV effects are heterogeneous even though the family-clustered F200 intervals exclude zero.

## Anonymity and remaining drafting gates

Personal HTTP user-agent email strings and first-party local absolute paths were removed; path-bearing Python bytecode caches were deleted. See `paper_build/anonymity_precheck.md`.

Before submission, still required:

- verified current bibliography/related-work matrix;
- removal of the entire placeholder author block from the LaTeX paper;
- regenerated figures with task-aligned values and safe terminology;
- an IEEE LaTeX build and page-count check.

These items do not require another data-validity rerun unless the frozen dataset or protocol changes.
