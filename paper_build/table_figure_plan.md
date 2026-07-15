# Exact Table and Figure Plan for the Eight-Page Paper

Main-paper limit: **four tables and three figures**. All other plots/tables move to an anonymous supplement or are reduced to prose.

## Main tables

### Table 1 — Dataset and frozen family composition

Protocol: dataset/family metadata, not an evaluation group.  
Placement: Section 6, one column.  
Source: `capability_dataset.csv`, `family_assignment_frozen.csv`.

Exact columns:

`subset | contracts | families bearing subset | member-singleton families | label source / role`

Exact rows:

- malicious | 793 | 214 | 113 (52.8%) | USENIX-artifact positives
- `benign_cleared` | 1,657 | 711 | 464 | rule-silent weak primary negatives
- `benign_general` | 800 | 440 | 364 | general secondary negatives
- `benign_AA` | 8 | 8 | 8 | hand-verified small control

Table note: global frozen structure is 1,329 families, 912 global singletons (68.6%), largest 58. Families can bear multiple subsets, so the family column must not be summed.

Caption requirement: “Dataset and frozen global MinHash-estimated family structure at threshold 0.85.”

### Table 2 — G-DET family-grouped performance

Protocol: **G-DET only**.  
Placement: Section 7/RQ1, one column using compact abbreviations.  
Source: `results/detection_results.json`.

Exact columns:

`method | AUPRC ± SD | AUROC | precision | recall | F1`

Exact rows:

- sensitive-name rule approximation | .344 ± .093 | .518 | .884 | .038 | .071
- external-call structural over-approximation | .341 ± .084 | .539 | .341 | 1.000 | .503
- blocklist | .324 ± .078 | .500 | .000 | .000 | .000
- selector-LR | .519 ± .068 | .670 | .459 | .617 | .521
- opcode-RF | .775 ± .076 | .895 | .782 | .444 | .557
- opcode-XGB | .789 ± .060 | .907 | .784 | .656 | .704
- **AuthGuard** | **.856 ± .043** | **.930** | **.871** | .641 | **.720**

Omit the tautological shipped-oracle row. Caption must state five outer family folds and that operating-point thresholds use training predictions. If space is tight, drop AUROC before dropping precision/recall.

### Table 3 — G-MUT retained recall under M0--M3

Protocol: **G-MUT only**.  
Placement: Section 7/RQ3, one column.  
Source: `results/mutation_curve.json`, `results/mutation_preservation.json`.

Exact columns:

`method | M0 | M1 | M2 | M3`

Exact rows:

- sensitive-name rule approximation | .038 | .038 | .038 | .000
- external-call structural over-approximation | 1.000 | 1.000 | 1.000 | 1.000
- blocklist | .000 | .000 | .000 | .000
- selector-LR | .617 | .621 | .623 | .621
- opcode-XGB | .656 | .659 | .518 | .518
- **AuthGuard** | **.641** | **.668** | **.588** | **.588**

Caption requirement: “G-MUT retained recall on held-out positive families under cumulative structure-preserving mutations; 793/793 passed the opcode-skeleton checker at M1--M3.” Do not mention semantic equivalence.

### Table 4 — G-ADV clean and held-out AuthGuard outcomes

Protocol: **G-ADV only**.  
Placement: Section 7/RQ4, compact one-column table; use `M0`, `M3`, and `F200` labels defined in the text.  
Source: `advtrain_results.json`.

Exact columns:

`condition | model | AUPRC | precision | recall | FPR`

Exact rows:

- clean M0 | AuthGuard-M0 | .830 | .693 | .797 | .192
- clean M0 | AuthGuard-aug | .849 | .720 | .761 | .164
- held-out M3 | AuthGuard-M0 | .754 | .613 | .787 | .276
- held-out M3 | AuthGuard-aug | .814 | .686 | .801 | .196
- held-out pure-M0 F200 | AuthGuard-M0 | .596 | .525 | .624 | .314
- held-out pure-M0 F200 | AuthGuard-aug | .750 | .615 | .790 | .275

Table note: F200 is a held-out flooding severity generated from M0; it is not the compound G-VOL condition. Mention opcode-XGB-aug’s F200 recall 0.701 in prose rather than adding more rows.

## Main figures

### Figure 1 — AuthGuard prototype and integration boundary

Status: **new vector figure required**; do not reuse the current prose-only architecture.  
Placement: Section 5, one column.

Exact content:

- solid implemented path: `runtime bytecode → deterministic disassembly/features → AuthGuard XGBoost → risk score/threshold`;
- solid offline path: `labeled corpus → frozen global families → family split → optional source-balanced variants → trained model + threshold`;
- dashed external context: `wallet authorization / RPC or cache / user warning`;
- explicit timing brace only over feature extraction + prediction: `3.37 ms mean locally`;
- no explanation/calibration component.

Caption must distinguish implemented scorer modules from unimplemented integration context.

### Figure 2 — Random versus family-grouped AUPRC

Status: **regenerate** `figures/fig_random_vs_family.png`.  
Protocol: **G-DET only**.  
Placement: Section 7/RQ2, one column.  
Source: `results/detection_results.json`.

Exact plotted methods and pairs:

- blocklist: .324 family / .558 random;
- selector-LR: .519 / .558;
- opcode-RF: .775 / .941;
- opcode-XGB: .789 / .948;
- AuthGuard: .856 / .961.

Exclude the sensitive-name approximation from this plot because its gap is negligible and it crowds the figure. Replace the current title with “Random versus family-grouped AUPRC (G-DET).” Legend: “family-grouped” and “random.” Remove “honest,” “leaks,” and any universal claim about prior work.

### Figure 3 — G-ADV held-out robustness and false-positive tradeoff

Status: **regenerate** `figures/fig_advtrain_heldout.png`.  
Protocol: **G-ADV only**.  
Placement: Section 7/RQ4, one column.  
Source: `advtrain_results.json`; family-aware uncertainty should be added if produced.

Exact panels:

- panel (a): AuthGuard-M0 versus AuthGuard-aug recall at held-out M3 and pure-M0 F200;
- panel (b): corresponding benign FPR;
- direct labels: M3 `.787→.801` recall and `.276→.196` FPR; F200 `.624→.790` recall and `.314→.275` FPR.

Do not place G-MUT or G-VOL values on either axis. If uncertainty bars remain, caption exactly what is resampled; remove the current unexplained fold-SD bars if they obscure the paired comparison.

## Results retained in prose, not main floats

- G-VOL compound +200% AuthGuard recall 0.139 versus opcode-XGB 0.485: one limitation sentence.
- G-ADV clean AUPRC/recall/FPR tradeoff: already in Table 4; discuss in one sentence.
- G-ADV F200 singleton recall 0.655 → 0.850 and family-macro recall 0.674 → 0.844: one sentence.
- Local latency 3.37 ms mean / 10.67 ms p95: one sentence after hardware provenance is recorded.
- Independent-set verdict: one limitation sentence, “INSUFFICIENT DATA (N=1).”

## Supplement/artifact-only floats

- family threshold sensitivity table (0.75/0.85/0.90);
- `fig_family_size.png`;
- `fig_auprc.png` (redundant with Table 2);
- `fig_mutation_curve.png` after terminology/baseline-name regeneration (redundant with Table 3 in the main paper);
- `fig_mutation_volume.png` after fixing clipped title and protocol label;
- `fig_advtrain_clean.png` and `fig_advtrain_seen.png`;
- `fig_advtrain_scoredist.png` after clarifying fold-varying thresholds;
- `fig_independent_funnel.png`;
- per-fold and full baseline G-ADV tables.

## Protocol and visual hygiene checklist

- Every results caption begins with or contains `G-DET`, `G-MUT`, `G-VOL`, or `G-ADV`.
- Never put G-VOL 0.139 beside G-ADV 0.624/0.790 as though it were a before/after pair.
- Never put G-DET 0.856 beside G-ADV 0.830/0.849 in one model-comparison column.
- Use “structure-preserving,” not “semantics-preserving.”
- Use the required approximation names; never label the plots “USENIX detector.”
- Avoid red/green-only encodings; use colorblind-safe colors plus markers/hatching.
- Use vector PDF/TikZ for the new architecture and regenerated plots when possible.
- Ensure all text remains legible at IEEE one-column width and all titles fit without clipping.
- Captions must state whether values are fold means, pooled values, SDs, or confidence intervals.
