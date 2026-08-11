# AuthGuard-7702 Long-Context Ablation Protocol v3

Status: frozen before the first reported run.

## Research question

Does AuthGuard-Seq improve because it covers more opcode context, because it processes
that context hierarchically, or because it learns to weight chunks?

The experiment changes only the sequence representation and token budget. It retains the
corrected primary benchmark, stored family-disjoint folds, optimizer, loss, calibration,
and validation-derived warning policy used by the current paper.

## Model configurations

| ID | Representation | Token budget | Chunk aggregation |
|---|---|---:|---|
| `flat_control_2048` | controlled non-hierarchical CNN | 2,048 | global max pool |
| `flat_control_16384` | controlled non-hierarchical CNN | 16,384 | global max pool |
| `chunk_attention_control_2048` | controlled 8 x 256 chunks | 2,048 | learned attention |
| `chunk_mean_control_16384` | controlled 64 x 256 chunks | 16,384 | uniform mean |
| `chunk_attention_control_16384` | controlled 64 x 256 chunks | 16,384 | learned attention |
| `authguard_reference_16384` | current AuthGuard-Seq | 16,384 | learned attention |

Streams longer than a budget are sampled deterministically across the complete linear
opcode stream. No model receives an uncapped transformed input.

The first five configurations share the same 32-dimensional embedding, two convolution
layers, dropout, and risk head. The flat and mean variants have identical parameter
counts; learned attention adds only a 65-parameter scoring layer. The sixth configuration
reproduces the current paper architecture and is reported as a transfer check, not as a
parameter-matched contrast.

## Data and evaluation

- Dataset: `revision_v2/data/authguardbench_7702_v2.csv.gz`
- Population: `PRIMARY_EVALUATION` only
- Outer test fold: stored `fold_id`
- Validation fold for test fold `f`: `(f + 1) mod 5`
- Training folds: the remaining three
- Seeds: 7702, 7703, 7704
- Calibration: validation-only temperature scaling
- Warning thresholds: validation negatives at 1%, 5%, and 10% empirical FPR
- Primary metric: held-out-family AUPRC
- Operational metrics: recall at the three validation-derived warning thresholds
- Robustness condition: donor-isolated `F200`, generated independently per outer fold

Each model is trained on clean data only. `F200` is a test-time stress condition using
the same fitted temperature and warning thresholds as clean evaluation.

## Predeclared comparisons

1. Coverage effect: `chunk_attention_control_16384` minus
   `chunk_attention_control_2048`.
2. Learned aggregation effect: `chunk_attention_control_16384` minus
   `chunk_mean_control_16384`.
3. Hierarchical effect at matched budget: `chunk_attention_control_16384` minus
   `flat_control_16384`.
4. Robustness under matched caps: compare the same three contrasts on `F200`.

These contrasts are interpreted as controlled evidence. A positive contrast in one run
is not described as universal superiority.

## Predeclared secondary diagnostics

- Report held-out AUPRC separately for source programs with at most 2,048 opcodes and
  source programs above 2,048 opcodes. This diagnostic localizes a context-length effect
  but is not treated as a randomized or causal comparison.
- Report, for every model and condition, how many inputs exceed the declared budget and
  verify that retained tokens never exceed that budget.

## Reporting and integrity gates

- Report fold results, seed means, and the mean/standard deviation across seeds.
- Persist per-row clean and `F200` predictions.
- Persist the original opcode count, transformed opcode count, retained-token count, and
  configured budget with each prediction.
- Persist donor provenance for every `F200` segment.
- Do not merge smoke-test output with reported output.
- Do not overwrite earlier experiment families.
- A failed or negative ablation remains part of the result rather than being discarded.
