# Exact Table and Figure Plan — Task-Aligned v1

Main-paper budget: four tables and three figures. All result floats use task-aligned artifacts. Original-cohort values stay in the artifact sensitivity report.

## Main tables

### Table 1 — Task-aligned dataset and frozen-family composition

Protocol: dataset audit, not an evaluation group. Placement: methodology, one column. Source: `data_hygiene/task_aligned_dataset_v1.csv` and audit CSVs.

Columns: `subset | observations | families bearing subset | subset-member singletons | source/role`.

Rows:

- malicious | 727 | 209 | 112 (53.6%) | USENIX-artifact positives
- `benign_cleared` | 1,553 | 635 | 399 | rule-silent weak primary negatives
- `benign_general` | 797 | 437 | 361 | secondary negatives
- `benign_AA` | 5 | 5 | 5 | small verified control

Table note: 3,082 observations in 1,258 retained frozen families, including 856 global singletons. Families can bear more than one subset, so family counts must not be summed. Audit removed 73 designator-source rows and quarantined 23 conflicting hashes/103 rows; three verified unique delegate runtimes were retained. The exclusions total 176 and do not overlap.

Caption: “Task-aligned chain/address observations and preserved global similarity-family structure; no retained cross-class exact bytecode and no exact bytecode spans frozen families.”

### Table 2 — G-DET family-grouped performance

Protocol: **G-DET only**. Placement: RQ1, one column. Source: `data_hygiene/task_aligned_detection_results.json`.

Columns: `method | AUPRC ± SD | AUROC | precision | recall | F1`.

Rows:

- sensitive-name rule approximation | .344 ± .094 | .520 | .884 | .043 | .079
- external-call structural over-approximation | .328 ± .078 | .518 | .328 | 1.000 | .489
- blocklist | .321 ± .077 | .500 | .000 | .000 | .000
- selector-LR | .515 ± .066 | .666 | .449 | .618 | .512
- opcode-RF | .744 ± .085 | .878 | .842 | .297 | .426
- opcode-XGB | .784 ± .081 | .883 | .798 | .544 | .626
- **AuthGuard** | **.881 ± .028** | **.943** | **.869** | **.576** | **.673**

Omit the tautological class-reading oracle. Caption must state five preserved outer family folds, artifact-derived positives versus weak negatives, fold-mean aggregation, and training-prediction thresholds.

### Table 3 — G-MUT retained recall under M0–M3

Protocol: **G-MUT only**. Placement: RQ3, one column. Source: task-aligned mutation curve and preservation JSON.

Columns: `method | M0 | M1 | M2 | M3`.

Rows:

- sensitive-name rule approximation | .043 | .043 | .043 | .000
- external-call structural over-approximation | 1.000 | 1.000 | 1.000 | 1.000
- blocklist | .000 | .000 | .000 | .000
- selector-LR | .618 | .619 | .614 | .613
- opcode-XGB | .544 | .603 | .463 | .463
- **AuthGuard** | **.576** | **.608** | **.530** | **.530**

Caption: “G-MUT fold-mean retained recall on held-out positive families under cumulative structure-preserving transformations; all 727 retained positive variants passed the opcode-skeleton checker at M1–M3.” The caption must state that this is not an execution-equivalence test.

### Table 4 — G-ADV clean and held-out AuthGuard outcomes

Protocol: **G-ADV only**. Placement: RQ4, compact one-column table. Source: `data_hygiene/task_aligned_advtrain_results.json`.

Columns: `condition | model | AUPRC | precision | recall | FPR`.

Rows:

- clean M0 | AuthGuard-M0 | .819 | .720 | .759 | .134
- clean M0 | AuthGuard-aug | .863 | .763 | .807 | .108
- held-out M3 | AuthGuard-M0 | .768 | .663 | .767 | .181
- held-out M3 | AuthGuard-aug | .825 | .743 | .796 | .120
- held-out pure-M0 F200 | AuthGuard-M0 | .561 | .512 | .484 | .217
- held-out pure-M0 F200 | AuthGuard-aug | .758 | .654 | .727 | .174

Table note: values are five-fold means. F200 is a held-out severity generated from M0, not compound G-VOL. Family-clustered pooled differences belong in the caption/prose, not as additional table rows: recall +.253 [.144,.379], FPR -.049 [-.086,-.014], AUPRC +.248 [.177,.322].

## Main figures

### Figure 1 — Implemented scorer and integration boundary

Status: new vector figure required. Placement: design section, one column.

Exact content:

- solid online scorer: `verified runtime bytecode → deterministic disassembly/features → AuthGuard XGBoost → score/threshold`;
- solid offline path: `task-aligned manifest → preserved family folds → optional source-balanced variants → trained model/threshold`;
- dashed external context: `authorization parser / RPC or cache / wallet warning`;
- timing brace over only feature extraction plus prediction: `3.411 ms mean; p95 9.514 ms, Apple M1`;
- no claim that a standalone CLI, wallet integration, UI, or network path was evaluated.

### Figure 2 — Random versus family-grouped AUPRC

Status: regenerate from task-aligned G-DET. Placement: RQ2, one column.

Pairs:

- blocklist: .321 family / .551 random;
- selector-LR: .515 / .559;
- opcode-RF: .744 / .969;
- opcode-XGB: .784 / .965;
- AuthGuard: .881 / .975.

Title: “Random versus family-grouped AUPRC (G-DET, task-aligned v1).” Legend: “family-grouped” and “seeded random diagnostic.” Caption must include: “family-grouped testing controls related-bytecode leakage and provides a more demanding generalization estimate.” Do not use “honest,” “leaks,” or “removes memorization.”

### Figure 3 — G-ADV held-out robustness and FPR

Status: regenerate from task-aligned G-ADV. Placement: RQ4, one column.

Panels:

- (a) fold-mean recall for AuthGuard-M0 versus AuthGuard-aug at M3 (.767→.796) and pure-M0 F200 (.484→.727);
- (b) fold-mean benign FPR at M3 (.181→.120) and F200 (.217→.174);
- annotate the family-clustered **pooled differences**, separately labeled from fold means: M3 recall +.023 [-.040,.080], M3 FPR -.059 [-.083,-.037], F200 recall +.253 [.144,.379], F200 FPR -.049 [-.086,-.014].

Do not draw family-bootstrap CIs as though they were confidence intervals around fold means. Do not mix G-MUT or G-VOL values into this figure. Caption must state 10,000 family-resampled paired replicates and fixed seed 7702.

## Results retained in prose

- G-VOL compound F200 recall: AuthGuard .130, opcode-XGB .279; explicitly not the G-ADV condition.
- F200 singleton recall .554→.830 and family-macro recall .556→.800.
- Opcode-XGB-aug F200 fold-mean recall .756 with FPR .386, versus AuthGuard-aug .727/.174.
- Local scorer-core mean 3.411 ms, p95 9.514 ms over 3,000 single calls; 300-contract batches 3.197 ms/contract.
- Independent verdict: “INSUFFICIENT DATA (N=1).”
- Task-alignment sensitivity: original values only in a clearly labeled artifact/supplement table, never as current headlines.

## Supplement/artifact-only material

- complete 76-row designator audit and 23-group conflict audit;
- original-versus-task-aligned comparison;
- family threshold sensitivity;
- family-size and redundant AUPRC plots;
- full G-VOL sweep;
- G-ADV clean/seen score distributions and per-fold tables;
- independent-set funnel.

## Visual and protocol hygiene

- Every result caption names G-DET, G-MUT, G-VOL, or G-ADV and states fold mean, pooled value, SD, or family-clustered CI.
- Never present G-VOL .130 beside G-ADV .484/.727 as a before/after pair.
- Never put G-DET .881 beside G-ADV .819/.863 in an unlabeled model-comparison column.
- Use required approximation names and checker-scoped “structure-preserving” wording.
- Use colorblind-safe colors plus redundant markers/hatching; prefer vector PDF/TikZ.
- Inspect all regenerated image/PDF metadata for anonymity and ensure legibility at IEEE one-column width.
