# Result Provenance Ledger — Task-Aligned v1

This ledger is the authoritative numeric source for drafting. Original-cohort results may appear only as explicitly labeled sensitivity comparisons in `data_hygiene/original_vs_task_aligned.md`. Values from different protocol groups or aggregations must not share unlabeled comparison columns.

## Frozen identities

| Artifact | SHA-256 | Role |
|---|---|---|
| `data_hygiene/task_alignment_protocol.md` | `6368be0b35c5b4aca6e067b3fb57aabf7db90a18b4bc6d43c9e969abae16083b` | outcome-blind cleaning policy frozen before reruns |
| `data_hygiene/task_aligned_dataset_v1.csv` | `147f86754bd2a01da1a21d78cce21a4710855a5eff3f6788ab6c3e58b4a8ac5f` | authoritative task-aligned manifest |
| `data_hygiene/task_aligned_detection_results.json` | `38a812ce13b81516811d43607edff2d291516193e2410966f403f9a60ef77520` | G-DET |
| `data_hygiene/task_aligned_mutation_curve.json` | `45a76cf8babc74a3b3554446daefcf4c3f5c957a3f0cc614201f1c77dfc1da47` | G-MUT |
| `data_hygiene/task_aligned_mutation_volume.json` | `ae7984fbab0d4462978c298cd80b64ab852a929c4ab55f24d52ebe215d8cb0fd` | G-VOL |
| `data_hygiene/task_aligned_advtrain_results.json` | `3e030136dedca890558698939d06f47e8d0f5fa8026b9641bc85bdf101fe7106` | G-ADV fold metrics |
| `data_hygiene/task_aligned_paired_results.csv` | `f4c22e370503244e3907c4c0c0950ee9e1f07b1b21289775059c89d3389f7e84` | paired outer-test predictions |
| `data_hygiene/task_aligned_advtrain_leakage_assertions.txt` | `a49c50cda7cd61663b3fc2a01df890f9bcb7c3715a50402ce441bd0c8f4b105b` | G-ADV integrity assertions |

Complete fingerprints and protocol notes are in `data_hygiene/task_aligned_result_provenance.md`. Original dataset, feature, fold, and result artifacts were not overwritten.

## Cleaning and dataset provenance

The audit inspected all 76 EIP-7702 designators. Thirty-two verified target runtimes were recovered: 29 from existing repository target rows and three through read-only RPC. The 29 repository recoveries were excluded because the exact runtime already belonged to another frozen family; retaining them would leak exact inputs and family reassignment was forbidden. Three unique RPC recoveries were retained. Forty-four unresolved designators were excluded. Thus, 73 designator-source rows were excluded.

All 23 cross-class exact-bytecode groups, covering 103 rows, were quarantined without relabeling. The exclusions do not overlap: 73 + 103 = 176 rows.

| Subset | Samples | Families bearing subset | Subset-member singletons | Role |
|---|---:|---:|---:|---|
| malicious | 727 | 209 | 112 (53.6%) | USENIX-artifact positives |
| `benign_cleared` | 1,553 | 635 | 399 | rule-silent weak primary negatives |
| `benign_general` | 797 | 437 | 361 | secondary negatives |
| `benign_AA` | 5 | 5 | 5 | small verified control |
| **total** | **3,082** | **1,258 global retained families** | **856 global singletons** | task-aligned v1 |

The manifest contains zero designators used as runtime inputs, zero cross-class exact hashes, zero exact hashes spanning frozen families, and zero families spanning the stored primary or secondary outer folds. It retains 233 same-class exact-duplicate groups covering 787 chain/address observations; the preserved family folds keep every such group within one fold. Twenty-eight similarity families contain multiple classes without exact-bytecode conflicts.

For the 1,553 retained `benign_cleared` rows, 115 (7.4%) share a similarity family with a retained positive and zero are exact positive duplicates. The 7.4% value is a conservative malicious-like-family heuristic, not a measured contamination rate.

## Protocol invariants

- Original family IDs and original family-to-outer-fold identities are preserved; no reclustering, reassignment, or fold rebalancing occurred.
- Features, banned fields, estimator hyperparameters, seeds, threshold methods, mutations, augmentation conditions, and source weights are unchanged.
- Main tables report arithmetic means over five preserved outer folds and population SD where shown.
- Pooled paired analyses use each contract's single outer-test prediction.
- Family-clustered intervals sample frozen test families with replacement and retain all observations and model pairing.
- The seeded random diagnostic mechanically reruns the original KFold procedure on the reduced row order; it is not a fixed-family result.

## G-DET: primary family-grouped detection

Population: 727 positives versus 1,553 `benign_cleared` weak negatives. Threshold: max-F1 on in-sample training predictions. Primary metric: AUPRC.

| Method | Family AUPRC ± SD | AUROC | Precision | Recall | F1 | Random AUPRC ± SD |
|---|---:|---:|---:|---:|---:|---:|
| sensitive-name rule approximation | .344 ± .094 | .520 | .884 | .043 | .079 | .349 ± .016 |
| external-call structural over-approximation | .328 ± .078 | .518 | .328 | 1.000 | .489 | .327 ± .012 |
| blocklist | .321 ± .077 | .500 | .000 | .000 | .000 | .551 ± .044 |
| selector-LR | .515 ± .066 | .666 | .449 | .618 | .512 | .559 ± .027 |
| opcode-RF | .744 ± .085 | .878 | .842 | .297 | .426 | .969 ± .014 |
| opcode-XGB | .784 ± .081 | .883 | .798 | .544 | .626 | .965 ± .016 |
| **AuthGuard** | **.881 ± .028** | **.943** | **.869** | **.576** | **.673** | **.975 ± .012** |

AuthGuard's random-minus-family AUPRC gap is 0.094. The safe interpretation is: **family-grouped testing controls related-bytecode leakage and provides a more demanding generalization estimate**. The class-reading shipped oracle is a tautological sanity check and is excluded from paper tables.

## G-MUT: cumulative M0–M3 mutation evaluation

Models train on retained clean M0 training families; only retained held-out positives are mutated. Metric: retained recall using G-DET-style training thresholds.

| Method | M0 | M1 | M2 | M3 |
|---|---:|---:|---:|---:|
| sensitive-name rule approximation | .043 | .043 | .043 | .000 |
| external-call structural over-approximation | 1.000 | 1.000 | 1.000 | 1.000 |
| blocklist | .000 | .000 | .000 | .000 |
| selector-LR | .618 | .619 | .614 | .613 |
| opcode-XGB | .544 | .603 | .463 | .463 |
| **AuthGuard** | **.576** | **.608** | **.530** | **.530** |

All 727 retained positives passed the repository's opcode-skeleton preservation checker at M1, M2, and M3. This supports “structure-preserving under our checker,” not execution or semantic equivalence. The full USENIX Gigahorse/Datalog pipeline was not executed.

## G-VOL: compound M3-style flooding

| Method | +0% | +25% | +50% | +100% | +200% |
|---|---:|---:|---:|---:|---:|
| AuthGuard | .608 | .527 | .474 | .291 | **.130** |
| opcode-XGB | .603 | .426 | .410 | .342 | .279 |

G-VOL combines metadata, address, selector, and flooding transformations. It is not the G-ADV pure-M0 F200 condition and is retained as a limitation rather than an augmentation-recovery claim.

## G-ADV: separated test/validation/train-fit protocol

For test fold `f`, validation is the next preserved original fold and the remaining three folds are train-fit. Thresholds use clean-M0 validation families. Augmented training uses M0, M1, M2, F25, F50, and F100 with source-normalized weights. M3 and pure-M0 F200 are held out.

| Condition | Model | AUPRC | Precision | Recall | FPR |
|---|---|---:|---:|---:|---:|
| clean M0 | AuthGuard-M0 | .819 | .720 | .759 | .134 |
| clean M0 | AuthGuard-aug | .863 | .763 | .807 | .108 |
| held-out M3 | AuthGuard-M0 | .768 | .663 | .767 | .181 |
| held-out M3 | AuthGuard-aug | .825 | .743 | .796 | .120 |
| held-out pure-M0 F200 | AuthGuard-M0 | .561 | .512 | .484 | .217 |
| held-out pure-M0 F200 | AuthGuard-aug | .758 | .654 | .727 | .174 |

At F200, pooled recall is .448→.702, singleton recall .554→.830, and family-macro recall .556→.800. Opcode-XGB-aug has .756 fold-mean recall but .386 FPR, versus AuthGuard-aug's .727 recall and .174 FPR. Fold-level effects are heterogeneous; the aggregate family-clustered results below are the statistical basis for the paper claim.

## Family-clustered paired uncertainty

Ten thousand fixed-seed replicates sample the 819 retained outer-test families with replacement and preserve model pairing. Differences are AuthGuard-aug minus AuthGuard-M0.

| Condition/metric | Pooled difference | 95% percentile CI |
|---|---:|---:|
| clean recall | +.044 | [-.045, .133] |
| clean FPR | -.024 | [-.048, -.001] |
| M3 recall | +.023 | [-.040, .080] |
| M3 FPR | -.059 | [-.083, -.037] |
| F200 recall | **+.253** | **[.144, .379]** |
| F200 FPR | **-.049** | **[-.086, -.014]** |
| F200 AUPRC | **+.248** | **[.177, .322]** |

The prior contract-resampled interval is superseded and must not be quoted as the task-aligned confidence interval.

## Runtime provenance

On an Apple M1 with 8 GiB RAM, macOS 26.5.1 arm64, Python 3.13.9, and XGBoost 3.3.0, 30 warm-ups preceded 3,000 batch-size-1 timed calls. Local feature extraction plus prediction averaged **3.411 ms/contract** (p50 2.499, p95 **9.514**, p99 16.578). Ten timed 300-contract batches averaged **3.197 ms/contract**.

Bytecode was preloaded. Training/loading, RPC, authorization parsing, caching, UI, and wallet integration were excluded. Never describe this as end-to-end wallet latency.

## Independent evidence and drafting rules

The independent-set verdict remains **INSUFFICIENT DATA (N=1)**; no quantitative out-of-corpus generalization claim is permitted.

1. Use task-aligned values above as current results.
2. Label protocol and aggregation in every result caption.
3. Use fold means for main performance tables and family-clustered intervals for inferential claims.
4. Use exactly “sensitive-name rule approximation,” “external-call structural over-approximation,” and “full USENIX Gigahorse/Datalog pipeline.”
5. Disclose rule-derived positives, weak negatives, quarantined rows, same-class dependence, and the scorer-core runtime boundary.
6. Do not claim novelty, execution equivalence, complete robustness, a deployed wallet product, or superiority to the unexecuted full pipeline.
