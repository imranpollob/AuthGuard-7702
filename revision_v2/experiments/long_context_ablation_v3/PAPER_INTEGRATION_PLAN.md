# Paper integration plan after the v3 gates resolve

This file maps experimental outcomes to manuscript changes. It deliberately does not
pre-write a favorable result.

## Contribution hierarchy

The revised paper should make one central technical claim:

> AuthGuard-7702 studies whether a compact hierarchical bytecode encoder can preserve
> useful evidence across long deployed-runtime streams under strict inference budgets.

The supporting contributions should be:

1. a family-disjoint, provenance-audited EIP-7702 delegation benchmark;
2. a parameter-matched mechanism study separating context coverage, chunking, and learned
   aggregation;
3. cap-correct donor-isolated flooding evaluation with validation-derived operating
   points; and
4. deployable warning policies with explicit limits, not exploit-proof claims.

This ordering prevents the model novelty from resting on the existing confounded
AuthGuard-versus-short-flat comparison.

## Required factual repairs independent of outcome

1. State the actual non-hierarchical budgets: Flat CNN and BiGRU use 2,048 opcodes, while
   the compact Transformer uses 1,024.
2. Replace the old uncapped transformed AuthGuard scores with the v3 fixed-cap scores.
3. Describe uniform full-stream sampling precisely. Do not call a capped input a complete
   opcode stream.
4. Treat first-linear-STOP evidence as a tokenizer/linear-disassembly limitation, not as
   an executable evasion result.
5. Keep the five legitimate contracts as qualitative cases; do not infer a general benign
   false-positive rate from them.

## Result-dependent claim rules

### Coverage gate

- `SUPPORTED`: claim that increased full-stream coverage materially improves the
  controlled hierarchical encoder on held-out families.
- `INCONCLUSIVE`: report a scale trend without causal language.
- `NOT SUPPORTED`: remove long-context coverage as an explanatory claim.

### Attention gate

- `SUPPORTED`: retain learned cross-chunk attention as an empirically supported component.
- `INCONCLUSIVE`: describe attention as the chosen aggregator.
- `NOT SUPPORTED`: rename the method around hierarchical long-context encoding rather than
  attention and prefer the simpler mean variant when its operational results are also
  competitive.

### Hierarchy gate

- `SUPPORTED`: claim an advantage over a parameter-matched flat encoder at the same
  16,384-token budget.
- `INCONCLUSIVE`: frame hierarchy as a memory/processing decomposition and report parity.
- `NOT SUPPORTED`: do not claim predictive superiority from hierarchy; center the paper on
  the benchmark, evaluation protocol, and operational robustness findings.

### Fixed-cap F200 gate

- Retain a robustness claim only when the clean-to-F200 degradation and paired contrast
  remain favorable under the same declared cap.
- If the reference model fails while a controlled variant succeeds, report the mechanism
  result but do not transfer it to AuthGuard-Seq.

## Manuscript edits

### Abstract

- Add at most one controlled-ablation sentence with the observed AUPRC deltas and
  family-bootstrap interval.
- Use the fixed-cap F200 result, not the earlier uncapped number.
- Keep the deployment claim as prioritization/warning support.

### Introduction

- Make the long deployed-runtime problem concrete with the observed fraction of contracts
  above 2,048 opcodes and the predeclared budget comparison.
- Replace a generic architecture contribution bullet with the controlled mechanism study.

### Method

- Add a compact diagram or paragraph distinguishing uniform flat sampling from
  uniformly selected 256-opcode chunks.
- Report controlled trainable parameter counts beside the current AuthGuard reference.
- State that all clean and transformed views are capped before scoring.

### Evaluation

Add one main-paper table:

| Model | Budget | Aggregation | Parameters | Clean AUPRC | F200 AUPRC | F200 R@5% |
|---|---:|---|---:|---:|---:|---:|

Add one compact contrast table:

| Mechanism | Condition | Delta AUPRC | Family-bootstrap 95% CI | Decision |
|---|---|---:|---:|---|

Put fold/seed detail, Brier, AUROC, and the other operating points in the appendix.

### Limitations

- Linear opcode streams are not control-flow recovery.
- Uniform selection under a 16,384-token cap is broad coverage, not lossless coverage.
- Flooding is a representation stress test, not by itself an executable adversarial
  exploit.
- The benchmark and external controls do not establish temporal generalization.

## Files to consume

- `summary.csv`
- `metrics.csv`
- `fold_clustered_contrasts.csv`
- `FOLD_CLUSTERED_CONTRIBUTION_DECISION.md`
- `complexity.csv`
- `predictions.csv.gz`
- `data/f200_donor_ledger_fold*.csv.gz`

Only after the full verifier passes should these values be copied into
`revision_v2/paper_final/main_final.tex`.
