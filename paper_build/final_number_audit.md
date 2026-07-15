# Final Number Audit — Task-Aligned v1

Audit date: 2026-07-15. Scope: every scientific or methodological number rendered by `overleaf/main.tex`, including section prose, tables, captions, and plot labels. Bibliographic years, volumes, issues, and pages are verified separately in `final_citation_audit.md`. TikZ coordinates, table spacing, font sizes, section numbers, citation numbers, and protocol digits used only as names are typesetting or notation rather than empirical claims.

## Reading and comparison rules

- Task-aligned machine-readable artifacts are authoritative. No value was read from a plot or reconstructed from old prose.
- A **fold mean** is the arithmetic mean over five preserved test folds. G-DET AUPRC additionally reports population SD over those folds.
- A **pooled family estimate** pools paired predictions and resamples frozen families; it is not a fold mean.
- AUPRC and AUROC are threshold-free. G-DET/G-MUT/G-VOL thresholded metrics use fitting-prediction maximum-$F_1$ thresholds. G-ADV thresholded metrics use a separate clean-M0 validation-family maximum-$F_1$ threshold.
- Direct comparisons are valid only within the named protocol and compatible condition. G-DET, G-MUT, G-VOL, and G-ADV are not merged.

## Definitions, implementation, and corpus numbers

| Value(s) | Section / location | Meaning | Protocol / aggregation | Threshold | Artifact source | Direct-comparison validity |
|---|---|---|---|---|---|---|
| `7702`; `0xef0100`; 23 bytes | Title and Sections I--V | EIP identifier, delegation prefix, and designator size | Standards/mechanism identifiers | N/A | EIP-7702 specification; `task_alignment_protocol.md` | Not a performance result |
| score range `[0,1]`; threshold `τ` | Problem definition | Model-output range and warning rule | Deterministic scorer definition | Protocol-specific `τ` | `pipeline/03_detection.py`; `problem_threat.tex` | Definition only; score is not calibrated theft probability |
| `773 = 261 + 512`; `261 = 225 + 36`; opcode `4`-grams; `7` interface flags | Design | Feature dimensions and composition | Implemented representation | N/A | `task_aligned_feature_meta.json`; `pipeline/ag_features.py` | Implementation facts |
| 300 trees; depth 6; learning rate .1; row/column subsampling .9/.8; 4 threads; seed 7702 | Design | AuthGuard XGBoost configuration | AuthGuard-M0 and AuthGuard-aug share hyperparameters | N/A | `pipeline/03_detection.py`; `pipeline/adv_run.py` | Estimator is not a contribution |
| 727; 1,553; 797; 5; 3,082 | Table I / Methodology | Positive, weak-negative, general-negative, AA-control, and global observation counts | Task-aligned dataset | N/A | `task_aligned_manifest_summary.json`; `task_aligned_dataset_v1.csv` | Population counts |
| 209/112; 635/399; 437/361; 5/5; 1,258/856 | Table I / Methodology | Families bearing each subset / subset-member singletons; global families / global singletons | Frozen family assignment | N/A | Task-aligned CSV and manifest | Subset family counts overlap and are not summed |
| 76, 32, 3, 29, 44, 73 | Methodology | Designators audited, runtimes recovered, retained, duplicate recovered exclusions, unresolved exclusions, and total designator-source exclusions | Outcome-blind alignment | N/A | `task_alignment_protocol.md`; `designator_audit.csv` | Policy frozen before rerun outcomes |
| 23 hashes / 103 rows; zero retained cross-class hashes | Methodology | Conflicting exact-bytecode groups quarantined | Outcome-blind alignment | N/A | `conflicting_bytecodes.csv`; manifest | No favorable relabeling |
| 233 exact groups / 787 observations | Methodology | Retained same-class exact duplicates | Dataset audit | N/A | Manifest and alignment protocol | Chain/address remains the observation unit |
| opcode 4-grams; 128 MinHash permutations; .85 threshold | Methodology | Similarity-family construction | Frozen pre-existing assignment | N/A | `pipeline/01_freeze_families.py`; task-aligned CSV | Families are similarity groups, not attacker identities |
| five folds; four fit / one test; `(f+1) mod 5`; three fitting folds | Methodology | G-DET/G-MUT and G-ADV split structure | Family-grouped protocols | Fit or validation threshold as stated | `task_aligned_rerun.py`; protocol | Comparisons remain protocol-specific |
| M0--M3; PUSH20; PUSH4; about 20%; 727/727 at M1--M3 | Methodology, Table III, Discussion | Cumulative mutation recipe and checker coverage | G-MUT | Clean-model fit threshold for recall | `pipeline/04_mutations.py`; `task_aligned_mutation_preservation.json` | Checker result is syntactic, not execution equivalence |
| F25/F50/F100/F200; 25/50/100/200% | Methodology and Fig. 3(b) | Post-STOP flooding volumes | G-VOL or G-ADV as explicitly labeled | Protocol-specific | `pipeline/04_mutations.py`; `pipeline/adv_run.py` | G-VOL compound F200 is not G-ADV pure-M0 F200 |
| six conditions; weight `1/n_i` | Methodology | Source-balanced symmetric augmentation | G-ADV fitting data | Validation threshold used only at evaluation | `pipeline/adv_run.py`; rerun artifact | Reduces shortcut opportunity; does not prove shortcut absence |

## G-DET family-grouped performance

All cells are five-fold means from `data_hygiene/task_aligned_detection_results.json`, prefix `primary_mal_vs_cleared.leave_family_out`. AUPRC SD is population SD. AUPRC/AUROC are threshold-free; precision, recall, and $F_1$ use fitting-prediction thresholds. Rows are directly comparable only within G-DET.

| Model / key | AUPRC ± SD | AUROC | Precision | Recall | F1 | Manuscript locations |
|---|---:|---:|---:|---:|---:|---|
| Sensitive-name rule approximation / `usenix_name_rule` | .344 ± .094 | .520 | .884 | .043 | .079 | Table II; selected values in Evaluation |
| External-call structural over-approximation / `usenix_struct_rule` | .328 ± .078 | .518 | .328 | 1.000 | .489 | Table II; selected values in Evaluation |
| Exact-hash blocklist / `blocklist` | .321 ± .077 | .500 | .000 | .000 | .000 | Table II |
| Selector-LR / `selector_model` | .515 ± .066 | .666 | .449 | .618 | .512 | Table II |
| Opcode-histogram RF / `opcode_rf` | .744 ± .085 | .878 | .842 | .297 | .426 | Table II |
| Opcode-histogram XGBoost / `opcode_xgb` | .784 ± .081 | .883 | .798 | .544 | .626 | Table II; Evaluation |
| AuthGuard / `authguard` | .881 ± .028 | .943 | .869 | .576 | .673 | Abstract, Introduction, Evaluation, Table II, Fig. 2, Discussion, Conclusion |

The primary population count `727 + 1,553` is stated in Evaluation and Table II's caption. The label target is artifact-derived positives versus rule-silent weak negatives, not verified malicious/benign truth.

## G-DET random-split diagnostic

These are threshold-free five-fold AUPRC means from the same G-DET JSON under `leave_family_out` and `random_split`. The random values are a corpus-specific split diagnostic, not a production estimate.

| Model | Family mean | Random mean | Difference used | Locations | Valid comparison |
|---|---:|---:|---:|---|---|
| Exact-hash blocklist | .321 | .551 | — | Fig. 2; Evaluation; Discussion | Within model and corpus |
| Selector-LR | .515 | .559 | — | Fig. 2; Evaluation | Within model and corpus |
| Opcode-histogram RF | .744 | .969 | — | Fig. 2; Evaluation | Within model and corpus |
| Opcode-histogram XGBoost | .784 | .965 | — | Fig. 2; Evaluation | Within model and corpus |
| AuthGuard | .881 | .975 | approximately .094 | Abstract, Introduction, Fig. 2, Evaluation, Discussion | Within model and corpus |

The Abstract and Introduction additionally print AuthGuard population SD `.028` for the family mean and `.012` for the random mean, sourced from the same artifact's `leave_family_out.authguard.std.AUPRC` and `random_split.authguard.std.AUPRC`. The `.094` gap is `0.9752765467390121 - 0.881366130013053`, rounded to three decimals from stored means. It is the only manuscript value computed by subtraction rather than stored directly; it is not reconstructed from prose or a figure.

## G-MUT retained recall

Every cell is a five-fold mean retained recall from `data_hygiene/task_aligned_mutation_curve.json`, key `{method}.{tier}.mean`, using clean-model fitting thresholds. The 24 cells are displayed in Table III and Fig. 3(a); selected endpoints recur in Evaluation and Discussion. Direct comparison is valid only inside G-MUT.

| Model | M0 | M1 | M2 | M3 |
|---|---:|---:|---:|---:|
| Sensitive-name rule approximation | .043 | .043 | .043 | .000 |
| External-call structural over-approximation | 1.000 | 1.000 | 1.000 | 1.000 |
| Exact-hash blocklist | .000 | .000 | .000 | .000 |
| Selector-LR | .618 | .619 | .614 | .613 |
| Opcode-histogram XGBoost | .544 | .603 | .463 | .463 |
| AuthGuard | .576 | .608 | .530 | .530 |

## G-VOL compound flooding

Every cell is a five-fold mean retained recall from `data_hygiene/task_aligned_mutation_volume.json`, key `{method}.{fraction}.mean`, using clean-model fitting thresholds. The 20 values are displayed in Fig. 3(b); selected endpoints recur in Evaluation and Discussion. G-VOL includes the compound metadata/address/selector condition and is not recovered by the G-ADV experiment.

| Model | +0% | +25% | +50% | +100% | +200% (F200) |
|---|---:|---:|---:|---:|---:|
| AuthGuard | .608 | .527 | .474 | .291 | .130 |
| Opcode-histogram XGBoost | .603 | .426 | .410 | .342 | .279 |
| Sensitive-name rule approximation | .000 | .000 | .000 | .000 | .000 |
| External-call structural over-approximation | 1.000 | 1.000 | 1.000 | 1.000 |

## G-ADV fold means

All cells are five-fold arithmetic means from `data_hygiene/task_aligned_advtrain_results.json`, prefix `aggregate`. AUPRC is threshold-free; precision, recall, and benign FPR use separate clean-M0 validation-family thresholds. Comparisons are valid for a fixed G-ADV condition. Table IV contains every cell; Fig. 4 repeats AuthGuard AUPRC and held-out recall/FPR cells without uncertainty bars.

| Condition | Model | AUPRC | Precision | Recall | FPR |
|---|---|---:|---:|---:|---:|
| Clean M0 | Opcode-histogram XGBoost | .757 | .677 | .661 | .161 |
| Clean M0 | Opcode-histogram XGBoost-aug | .752 | .610 | .779 | .284 |
| Clean M0 | AuthGuard-M0 | .819 | .720 | .759 | .134 |
| Clean M0 | AuthGuard-aug | .863 | .763 | .807 | .108 |
| Held-out M3 | Opcode-histogram XGBoost | .695 | .640 | .675 | .201 |
| Held-out M3 | Opcode-histogram XGBoost-aug | .723 | .600 | .807 | .304 |
| Held-out M3 | AuthGuard-M0 | .768 | .663 | .767 | .181 |
| Held-out M3 | AuthGuard-aug | .825 | .743 | .796 | .120 |
| Held-out pure-M0 F200 | Opcode-histogram XGBoost | .529 | .489 | .601 | .347 |
| Held-out pure-M0 F200 | Opcode-histogram XGBoost-aug | .696 | .538 | .756 | .386 |
| Held-out pure-M0 F200 | AuthGuard-M0 | .561 | .512 | .484 | .217 |
| Held-out pure-M0 F200 | AuthGuard-aug | .758 | .654 | .727 | .174 |

The AuthGuard clean, M3, and F200 triplets recur in Evaluation; the F200 triplets recur in the Abstract, Introduction, and Discussion. The Conclusion describes partial F200 recovery without adding a number. No G-ADV value is presented as directly comparable with G-DET `.881` or G-VOL `.130`.

## G-ADV paired family-clustered evidence

Source: `statistics/family_clustered_bootstrap.json`, prefix `results.task_aligned_v1`. Each result uses 10,000 paired replicates that resample 819 frozen families containing 2,280 observations. Differences are AuthGuard-aug minus AuthGuard-M0.

| Condition / metric | Pooled M0 | Pooled aug | Difference | 95% CI | Aggregation | Threshold | Locations |
|---|---:|---:|---:|---|---|---|---|
| F200 recall | .448 | .702 | +.253 | [.144, .379] | Pooled paired family bootstrap | Validation | Abstract (difference/CI); Evaluation; Discussion |
| F200 FPR | .228 | .179 | -.049 | [-.086, -.014] | Pooled paired family bootstrap | Validation | Evaluation; Discussion |
| F200 AUPRC | not printed | not printed | +.248 | [.177, .322] | Pooled paired family bootstrap | Threshold-free | Evaluation; Discussion |
| Clean M0 recall | not printed | not printed | +.044 | [-.045, .133] | Pooled paired family bootstrap | Validation | Evaluation |
| Clean M0 FPR | not printed | not printed | -.024 | [-.048, -.001] | Pooled paired family bootstrap | Validation | Evaluation |
| M3 recall | not printed | not printed | +.023 | [-.040, .080] | Pooled paired family bootstrap | Validation | Evaluation |
| M3 FPR | not printed | not printed | -.059 | [-.083, -.037] | Pooled paired family bootstrap | Validation | Evaluation |

Clean and M3 recall intervals include zero and are explicitly described as not statistically resolved. F200 fold means remain separately labeled from these pooled estimates.

## Runtime and independent-validation numbers

| Value | Section / location | Metric / condition | Aggregation | Threshold | Artifact | Direct-comparison validity |
|---|---|---|---|---|---|---|
| 3.411 ms mean; 9.514 ms p95; 3,000 calls | Evaluation and Discussion | Preloaded-bytecode normalization, feature extraction, prediction | Single-contract timing | Threshold presentation excluded | `runtime/runtime_results.json`; `runtime_protocol.md` | Not end-to-end wallet/network latency |
| 3.197 ms/contract; 10 timed 300-contract batches | Evaluation | Same local scorer core, batched | Mean over 10 batches | None | Same runtime artifacts | Not compared with Gigahorse or wallet latency |
| one truly novel confirmed positive (`N=1`) | Evaluation and Discussion | Independent feasibility funnel | Count only | Frozen independent threshold; no metric inferred | `reports/funnel.json`; independent report | Verdict `INSUFFICIENT DATA`; no `1/1` accuracy |

## Repetition, rounding, and exclusion findings

- Repeated headline values are intentional and consistent: G-DET `.881 ± .028` and random `.975 ± .012`; G-ADV F200 `.561/.484/.217 → .758/.727/.174`; family-pooled recall difference `+.253 [.144,.379]`; G-VOL `.130`; and local timing `3.411/9.514 ms` all match their single authoritative artifacts at every occurrence.
- Tables and plot labels use three-decimal rounding. Prose uses the same rounding. No conflicting rounding was found.
- Plot scripts load task-aligned JSON values; no result array is hard-coded and no plotted value was transcribed back into prose.
- No original-cohort headline value remains. A targeted scan found none of the superseded values `.856`, `.961`, `.104`, old AuthGuard mutation `.641/.668/.588`, old G-VOL `.139`, old G-ADV F200 `.596/.624/.314` or `.750/.790/.275`, or old bootstrap `+.161`/`+.220` in the integrated manuscript.
- No unsupported value, old contract-resampled confidence interval, or value reconstructed solely from prose remains.
- Non-rendered typesetting constants (TikZ coordinates, node dimensions, `tabcolsep`, and `vspace`) carry no scientific meaning and were checked for readability/formatting rather than evidence provenance.
