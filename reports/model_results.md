# Model Results

Run `v2`. Every value below is read from
`data/gold_dataset/experiments/v2_experiment_results.json` and the per-model prediction files
`v2_test_predictions_{A,B,C}.csv` in the same directory.

**Headline: all three experiments perform at chance on the human-reviewed temporal test set.**
This is a genuine null result, not a pipeline failure — the diagnosis is below.

## Label mapping

| Gold label | Treatment |
|---|---|
| R1, R2 | warning-positive (1) |
| B | negative (0) |
| U | defer / abstain — never trained on, never scored as a binary case |
| NOTSCREENABLE | defer — no bytecode exists, so no feature vector can be built |

## Examples and families per experiment

| Experiment | training examples | positives | families | notes |
|---|---:|---:|---:|---|
| A — Huang weak labels only | 2,367 | 784 | n/a | 83 Huang rows excluded for address- or bytecode-overlap with the gold population |
| B — human-reviewed only | 113 | 40 | 96 | train split, decidable rows only |
| C — Huang pretrain → human fine-tune | 2,367 → 113 | 784 → 40 | 96 | continued boosting from A |

Split sizes (all rows / decidable rows): train 193/113, val 62/50, **test 51/44**.
Families per split: train 120, val 52, test 51.

## Test-set results

Test set: **44 decidable contracts, 9 positive, prevalence 0.205**. The test split was used once,
for these numbers only; thresholds and calibration come from validation.

| Experiment | AUPRC | AUPRC 95% CI | AUROC | AUROC 95% CI | Brier (cal.) | R@5%FPR |
|---|---:|---:|---:|---:|---:|---:|
| A — Huang only | 0.201 | [0.106, 0.377] | 0.486 | [0.311, 0.658] | 0.250 | 0.000 |
| B — human only | 0.227 | [0.127, 0.430] | 0.533 | [0.324, 0.743] | 0.173 | 0.000 |
| C — pretrain+fine-tune | 0.226 | [0.127, 0.422] | 0.549 | [0.364, 0.727] | 0.172 | 0.000 |
| *prevalence baseline* | *0.205* | — | *0.500* | — | — | — |

Confidence intervals are 2,000 bootstrap resamples **clustered on `split_group`** (the
family/proxy closure), since contracts inside a group are not independent.

Every AUPRC interval contains the prevalence baseline (0.205) and every AUROC interval contains
0.5. No experiment is distinguishable from chance, and the ordering A < B < C is well inside
noise.

### Operating points (thresholds from validation only), model C

| Nominal FPR | threshold | recall | precision | F1 |
|---|---:|---:|---:|---:|
| 1% | 0.907 | 0.000 | 0.000 | 0.000 |
| 5% | 0.789 | 0.000 | 0.000 | 0.000 |
| 10% | 0.696 | 0.111 | 0.125 | 0.118 |

Brier score 0.308 raw, 0.172 after isotonic calibration fitted on validation.

### Breakdown by label, coverage, and code size (model C)

| Final label | n | mean score | median score |
|---|---:|---:|---:|
| R1 | 8 | 0.248 | 0.167 |
| R2 | 1 | 0.156 | 0.156 |
| B | 35 | 0.308 | 0.081 |
| U | 7 | 0.442 | 0.510 |

The warning-positive classes score *lower on average* than the negatives. `score_distribution_by_label.pdf`
shows this directly: at the 5%-FPR threshold every above-threshold contract is a B or a U, and
every R1 sits below it.

| Coverage | n | mean score |
|---|---:|---:|
| COMPLETE | 44 | 0.294 |
| PARTIAL | 7 | 0.442 |

| Code-size quartile | n | decidable | positives | AUPRC |
|---|---:|---:|---:|---:|
| Q1 | 13 | 12 | 2 | 0.268 |
| Q2 | 13 | 13 | 1 | 0.091 |
| Q3 | 12 | 11 | 2 | 0.750 |
| Q4 | 13 | 8 | 4 | 0.378 |

Each quartile has 1–4 positives; these values are essentially noise and are reported only for
completeness.

### Decidable-only metrics and defer rate over the full population

Binary metrics above are computed **only** on the 44 decidable (R1/R2/B) test contracts.
Over the full test population of 51 rows, 7 (13.7%) are U and deferred. Population-wide, a
further 8 NOTSCREENABLE delegates are always deferred and never enter the gold set.

## Why the result is null — diagnosis

The models fit their training data perfectly and do not generalise:

| | train | val | test |
|---|---:|---:|---:|
| AUPRC (model B) | 1.000 | 0.227 | 0.216 |
| AUROC (model B) | 1.000 | 0.607 | 0.514 |

113 training examples across 96 families with 36 features is far too little to learn a
generalisable rule, and the labels are a **semantic** property — is a reachable dangerous
capability dominated by an authorization guard? — while the features are **structural** opcode
and selector counts. Guard dominance is a control-flow-dominance relation that opcode histograms
do not encode, so there is little reason to expect the feature set to carry the signal even with
more data. Top-gain features (`has_owner`, `n_jump`, `has_transfer`, `n_revert`) are proxies for
"this is an account-like contract", not for "this capability is unprotected".

**The obvious way to make these numbers look good would be circular and was deliberately not
taken.** The reachability/guard-dominance features that *define* the v3 labels are available in
every evidence package. Feeding them to the classifier would reproduce the labels almost
perfectly and would measure nothing except the labelling function. This is the same circularity
the project previously documented for the Huang rule labels
(`revision_v2/audit/DATASET_AUDIT_REPORT.md`), where a bytecode model reached AUPRC ≈ 0.92 against
labels that were themselves a bytecode rule. The comparison worth noting: on the *previous*,
rule-derived labels this feature class scored ~0.92; on semantically grounded labels it scores at
chance. That contrast is the most defensible finding in this report.

## Traceability

| Artifact | Path |
|---|---|
| Experiment metrics | `data/gold_dataset/experiments/v2_experiment_results.json` |
| Per-contract test scores | `data/gold_dataset/experiments/v2_test_predictions_{A,B,C}.csv` |
| Decision scores | `data/gold_dataset/experiments/v2_decision_scores.csv` |
| Gold dataset | `data/gold_dataset/v2_gold_reviewed.csv` |
| Split manifest (SHA-256 `f87cf8f4…`) | `data/split_manifests/v2_split_manifest.csv` |
| Frozen review (SHA-256 `8a8ad256…`) | `data/human_reviews/frozen/v2_gold_review_FROZEN.csv` |
