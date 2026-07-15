# Evaluation Number Audit — Task-Aligned v1

Audit date: 2026-07-15. Scope: `sections/evaluation.tex`, its three tables, all three generated figures, and their captions. Displayed values use consistent three-decimal rounding from machine-readable task-aligned artifacts. No value was reconstructed from a plot.

## Reading rules

- **Fold mean** means the arithmetic mean over five preserved outer test folds. Reported G-DET SD is population SD over those folds.
- **Threshold-free** applies to AUPRC and AUROC.
- **Fit threshold** means maximum-$F_1$ threshold chosen from fitting predictions (G-DET/G-MUT/G-VOL).
- **Validation threshold** means maximum-$F_1$ threshold chosen on a different clean-M0 family fold (G-ADV).
- **Pooled family bootstrap** means pooled paired predictions with frozen families resampled; it is not a fold mean.
- **Comparable** means directly comparable within the named protocol only. No G-DET/G-MUT/G-VOL/G-ADV cross-protocol metric comparison is authorized.

## Context, population, and validation counts

| Rendered number | Meaning | Protocol / aggregation | Threshold dependency | Artifact | Key / column | Comparability |
|---:|---|---|---|---|---|---|
| 5 | Evaluation research questions; also preserved outer folds where stated | Paper organization / all experiment groups | N/A | Prompt 4; task-alignment protocol | protocol definitions | Organizational; fold count common but protocols differ |
| 727 | G-DET positives; G-MUT checker population | G-DET observations / G-MUT positive sources | Mixed | `task_aligned_manifest_summary.json`; `task_aligned_mutation_preservation.json` | `retained_class_counts.malicious`; `M1..M3.checked` | Population count only |
| 1,553 | G-DET weak negatives | G-DET observations | N/A | `task_aligned_manifest_summary.json` | `retained_class_counts.benign_cleared` | Directly defines primary population |
| 727/727 | Passed checker, separately at M1, M2, M3 | G-MUT count, not a rate estimate | N/A | `task_aligned_mutation_preservation.json` | each tier: `checked`, `preserved` | Comparable across tiers only as checker coverage |
| 1 | Confirmed truly novel independent positive | Independent feasibility funnel | Frozen independent threshold exists, but no metric inferred | `reports/funnel.json` | `funnel.confirmed_malicious_TRULY_NOVEL` | Not comparable to task-aligned metrics; insufficient data |

## Table 2 — G-DET family-grouped performance

Common provenance for every row below: `paper_build/data_hygiene/task_aligned_detection_results.json`, key prefix `primary_mal_vs_cleared.leave_family_out`. AUPRC/AUROC are threshold-free. Precision, recall, and F1 use the G-DET fit threshold. All are five-fold means; AUPRC SD is population SD. All seven rows are directly comparable within G-DET. The shipped label-reading oracle was excluded.

| Model / artifact key | AUPRC mean | AUPRC SD | AUROC | Precision | Recall | F1 | JSON suffix |
|---|---:|---:|---:|---:|---:|---:|---|
| Sensitive-name approximation / `usenix_name_rule` | .344 | .094 | .520 | .884 | .043 | .079 | `{method}.mean.{metric}`, `{method}.std.AUPRC` |
| External-call over-approximation / `usenix_struct_rule` | .328 | .078 | .518 | .328 | 1.000 | .489 | same pattern |
| Exact-hash blocklist / `blocklist` | .321 | .077 | .500 | .000 | .000 | .000 | same pattern |
| Selector-LR / `selector_model` | .515 | .066 | .666 | .449 | .618 | .512 | same pattern |
| Opcode-histogram RF / `opcode_rf` | .744 | .085 | .878 | .842 | .297 | .426 | same pattern |
| Opcode-histogram XGBoost / `opcode_xgb` | .784 | .081 | .883 | .798 | .544 | .626 | same pattern |
| AuthGuard / `authguard` | .881 | .028 | .943 | .869 | .576 | .673 | same pattern |

Exact unrounded values were extracted in the audit command from each `mean` and `std` object; the table contains only rounded artifact values. Prose repeats AuthGuard `.881 ± .028`, opcode-XGBoost `.784 ± .081`, `.943/.869/.576`, structural `1.000/.328/.328`, blocklist `.000` recall, and name `.884/.043`; these are the same cells, not separate estimates.

## Figure 2 — G-DET random versus family-grouped AUPRC

All values are threshold-free five-fold AUPRC means from the G-DET artifact. Family and random results are directly comparable as a split diagnostic for the same model and corpus, but random values are not headline generalization estimates.

| Model | Family value | Random value | Protocol | Artifact keys | Direct comparability |
|---|---:|---:|---|---|---|
| Exact-hash blocklist | .321 | .551 | G-DET | `...leave_family_out.blocklist.mean.AUPRC`; `...random_split.blocklist.mean.AUPRC` | Within-model diagnostic only |
| Selector-LR | .515 | .559 | G-DET | same prefixes, `selector_model` | Within-model diagnostic only |
| Opcode-histogram RF | .744 | .969 | G-DET | same prefixes, `opcode_rf` | Within-model diagnostic only |
| Opcode-histogram XGBoost | .784 | .965 | G-DET | same prefixes, `opcode_xgb` | Within-model diagnostic only |
| AuthGuard | .881 | .975 | G-DET | same prefixes, `authguard` | Within-model diagnostic only |
| .094 | AuthGuard random-minus-family absolute AUPRC gap | G-DET subtraction of unrounded stored means | N/A | same two AuthGuard keys | Corpus-specific split gap |

The displayed `.094` is `0.9752765467390121 - 0.881366130013053 = 0.0939104167259591`, rounded to three decimals; it is computed from machine-readable means, not estimated from the figure.

## Table 3 and Figure 3(a) — G-MUT retained recall

Common provenance: `paper_build/data_hygiene/task_aligned_mutation_curve.json`. Every value is a five-fold mean of retained recall on held-out positives at the corresponding clean-model fit threshold. JSON key pattern: `{method}.{tier}.mean`. Values are directly comparable within G-MUT across tiers and methods, subject to rule breadth; they are not comparable as before/after values with G-VOL or G-ADV.

| Model / key | M0 | M1 | M2 | M3 |
|---|---:|---:|---:|---:|
| Sensitive-name approximation / `usenix_name_rule` | .043 | .043 | .043 | .000 |
| External-call over-approximation / `usenix_struct_rule` | 1.000 | 1.000 | 1.000 | 1.000 |
| Exact-hash blocklist / `blocklist` | .000 | .000 | .000 | .000 |
| Selector-LR / `selector_model` | .618 | .619 | .614 | .613 |
| Opcode-histogram XGBoost / `opcode_xgb` | .544 | .603 | .463 | .463 |
| AuthGuard / `authguard` | .576 | .608 | .530 | .530 |

The same 24 values appear in Table 3 and Figure 3(a). Prose repeats only selected endpoints. The condition digits in M0--M3 are identifiers defined by the mutation implementation, not measurement values.

## Figure 3(b) — G-VOL compound flooding

Common provenance: `paper_build/data_hygiene/task_aligned_mutation_volume.json`. Every value is a five-fold mean retained recall on held-out positives at a clean-model fit threshold. JSON key pattern: `{method}.{fraction}.mean`, with fraction keys `0.0`, `0.25`, `0.5`, `1.0`, and `2.0`. Comparisons are valid within G-VOL only. The volume labels +0%, +25%, +50%, +100%, and +200% identify the configured fraction of original executable-byte length.

| Model / key | +0% | +25% | +50% | +100% | +200% |
|---|---:|---:|---:|---:|---:|
| AuthGuard / `authguard` | .608 | .527 | .474 | .291 | .130 |
| Opcode-histogram XGBoost / `opcode_xgb` | .603 | .426 | .410 | .342 | .279 |
| Sensitive-name approximation / `usenix_name_rule` | .000 | .000 | .000 | .000 | .000 |
| External-call over-approximation / `usenix_struct_rule` | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

Prose repeats `.608→.130` and `.603→.279`. These are never paired with G-ADV `.484→.727` as one experiment.

## Table 4 — G-ADV fold means

Common provenance: `paper_build/data_hygiene/task_aligned_advtrain_results.json`, key prefix `aggregate`. All values are five-fold arithmetic means. AUPRC is threshold-free; precision, recall, and FPR use the separate clean-M0 validation threshold. Rows are directly comparable within G-ADV for a fixed condition. F200 here is pure-M0 F200, not compound G-VOL.

| Condition | Model | AUPRC | Precision | Recall | FPR | JSON key pattern |
|---|---|---:|---:|---:|---:|---|
| M0 | Opcode-histogram XGBoost | .757 | .677 | .661 | .161 | `aggregate.{model}.M0.mean.{metric}` |
| M0 | Opcode-histogram XGBoost-aug | .752 | .610 | .779 | .284 | same |
| M0 | AuthGuard-M0 | .819 | .720 | .759 | .134 | same |
| M0 | AuthGuard-aug | .863 | .763 | .807 | .108 | same |
| M3 | Opcode-histogram XGBoost | .695 | .640 | .675 | .201 | `aggregate.{model}.M3.mean.{metric}` |
| M3 | Opcode-histogram XGBoost-aug | .723 | .600 | .807 | .304 | same |
| M3 | AuthGuard-M0 | .768 | .663 | .767 | .181 | same |
| M3 | AuthGuard-aug | .825 | .743 | .796 | .120 | same |
| F200 | Opcode-histogram XGBoost | .529 | .489 | .601 | .347 | `aggregate.{model}.F200.mean.{metric}` |
| F200 | Opcode-histogram XGBoost-aug | .696 | .538 | .756 | .386 | same |
| F200 | AuthGuard-M0 | .561 | .512 | .484 | .217 | same |
| F200 | AuthGuard-aug | .758 | .654 | .727 | .174 | same |

Figure 4 duplicates the six AuthGuard AUPRC fold means for M0/M3/F200 and the eight AuthGuard recall/FPR fold means for M3/F200. No uncertainty bar is drawn. Prose repeats the AuthGuard M0, M3, and F200 AUPRC/recall/FPR triplets and the F200 opcode-XGBoost-aug `.696/.756/.386` trade-off; all are cells above.

## G-ADV family-clustered paired inference

Common provenance: `paper_build/statistics/family_clustered_bootstrap.json`, key prefix `results.task_aligned_v1`. Aggregation is pooled paired prediction, not fold mean. There are 10,000 bootstrap replicates; each resamples 819 frozen families containing 2,280 primary observations and retains all family members and model pairing. The family is the resampling unit. Differences are AuthGuard-aug minus AuthGuard-M0 and are directly comparable only within the same condition and metric.

| Condition | Metric | Pooled M0 | Pooled aug | Difference | 95% CI | JSON keys | Threshold dependency |
|---|---|---:|---:|---:|---|---|---|
| F200 | Recall | .448 | .702 | +.253 | [.144, .379] | `F200.point.*.recall`; `recall_diff_aug_minus_M0`; `recall_diff_CI95` | Validation threshold |
| F200 | FPR | .228 | .179 | -.049 | [-.086, -.014] | `F200.point.*.FPR`; `FPR_diff_aug_minus_M0`; `FPR_diff_CI95` | Validation threshold |
| F200 | AUPRC | — | — | +.248 | [.177, .322] | `F200.AUPRC_diff_aug_minus_M0`; `AUPRC_diff_CI95` | Threshold-free |
| M0 | Recall | — | — | +.044 | [-.045, .133] | `M0.recall_diff_aug_minus_M0`; `recall_diff_CI95` | Validation threshold |
| M0 | FPR | — | — | -.024 | [-.048, -.001] | `M0.FPR_diff_aug_minus_M0`; `FPR_diff_CI95` | Validation threshold |
| M3 | Recall | — | — | +.023 | [-.040, .080] | `M3.recall_diff_aug_minus_M0`; `recall_diff_CI95` | Validation threshold |
| M3 | FPR | — | — | -.059 | [-.083, -.037] | `M3.FPR_diff_aug_minus_M0`; `FPR_diff_CI95` | Validation threshold |

The dash means the pooled point values are not printed in Evaluation prose for that cell, not that the JSON lacks them. The F200 AUPRC prose intentionally reports only the paired difference and CI. “95%” denotes percentile intervals from the 10,000 family-resampled replicates; it is not a fold-level interval.

## RQ5 runtime numbers

Common provenance: `paper_build/runtime/runtime_results.json` under the frozen `runtime_protocol.md`. These are local feature-extraction-plus-prediction timings on an Apple M1 with bytecode preloaded. They are not model-performance metrics and are not directly comparable with any network, wallet, parser, or Gigahorse runtime.

| Rendered number | Metric / condition | Aggregation | JSON key | Threshold dependency |
|---:|---|---|---|---|
| 3.411 ms | Single-contract latency mean | 3,000 timed calls | `single_contract.milliseconds.mean` | None; threshold application excluded |
| 9.514 ms | Single-contract latency p95 | Same 3,000 calls | `single_contract.milliseconds.p95` | None |
| 3,000 | Number of single-contract timed calls | 10 passes over 300 samples | `single_contract.timed_calls` | N/A |
| 10 | Timed batch repetitions | 300 contracts per batch | `batched.timed_batches` | N/A |
| 300 | Batch size | Per timed batch | `batched.batch_size` | N/A |
| 3.197 ms/contract | Batched per-contract mean | Mean over 10 batch repetitions | `batched.milliseconds_per_contract.mean` | None |

## Old-cohort values explicitly excluded

The following original-cohort values were audited but not used as Evaluation evidence:

- Population: 3,258 total; 793 malicious; 1,657 `benign_cleared`; 800 `benign_general`; 8 `benign_AA`; 214 malicious-bearing families.
- G-DET family/random AUPRC pairs: name `.344/.352`, external-call `.341/.341`, blocklist `.324/.558`, selector-LR `.519/.558`, opcode-RF `.775/.941`, opcode-XGB `.789/.948`, AuthGuard `.856/.961`; old AuthGuard gap `.104`.
- G-MUT old AuthGuard M0--M3 `.641/.668/.588/.588`, opcode-XGB `.656/.659/.518/.518`, selector-LR `.617/.621/.623/.621`, and name `.038/.038/.038/.000`; the complete original grid in `original_vs_task_aligned.md` was rejected.
- G-VOL old AuthGuard `.668/.567/.500/.310/.139` and opcode-XGB `.659/.523/.498/.473/.485`.
- G-ADV old AuthGuard-M0 M0/M3/F200 AUPRC-recall-FPR `.830/.797/.192`, `.754/.787/.276`, `.596/.624/.314`; old AuthGuard-aug `.849/.761/.164`, `.814/.801/.196`, `.750/.790/.275`; all original opcode rows were likewise rejected.
- Original family-bootstrap F200 recall difference `+.161 [.068,.285]`, FPR difference `-.046 [-.079,-.014]`, and AUPRC difference `+.220 [.151,.290]`; the superseded contract-resampled intervals were also rejected.

Some invariant or rounded values (for example rule recall `1.000` or zero blocklist recall) numerically coincide across cohorts. Their inclusion is sourced exclusively from the task-aligned JSON, not copied from the original report.

## Incompatible comparisons rejected

- Rejected G-VOL compound `.130` versus G-ADV pure-M0 `.484→.727` as a before/after comparison.
- Rejected G-DET `.881` versus G-ADV clean `.819/.863` as a same-protocol model comparison.
- Rejected fold means as inputs to, or substitutes for, pooled family-bootstrap point estimates.
- Rejected the random diagnostic as a headline family-generalization estimate.
- Rejected sensitive-name/external-call approximations as measurements of the full USENIX Gigahorse/Datalog pipeline.
- Rejected the one-positive independent set as a quantitative accuracy estimate.
- Rejected local scorer timing as end-to-end wallet or network latency.

## Unavailable values

- G-DET benign FPR: **[NOT MEASURED]** by the saved G-DET metric function.
- G-MUT and G-VOL AUPRC, AUROC, precision, F1, and benign FPR: **[NOT MEASURED]** because these protocols score held-out positives and report retained recall.
- M0 and M3 family-bootstrap AUPRC difference intervals: **[NOT MEASURED]** in the saved bootstrap JSON.
- Confidence intervals around the displayed five-fold means: **[NOT MEASURED]**; G-DET stores population SD, while G-ADV paired inference is separate and family-clustered.
- Full USENIX pipeline performance under task-aligned G-DET/G-MUT: **[NOT MEASURED]**; the pipeline was not run.
- Quantitative independent-set accuracy: **[NOT MEASURED]** because the frozen funnel produced $N=1$.
- End-to-end authorization, RPC/network/cache, wallet, and warning-rendering latency: **[NOT MEASURED]**.
