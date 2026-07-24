# AuthGuard-7702 Long-Context Contribution Strengthening Plan

## Objective

Strengthen the paper's central technical contribution by replacing the confounded
"hierarchical model versus short flat baseline" comparison with a controlled study of:

1. long-stream coverage;
2. hierarchical chunking; and
3. learned cross-chunk attention.

The study must also repair the transformed-input capacity mismatch in the current
robustness run. Every clean and transformed sequence will obey its declared token
budget, and every result will be written to new Revision-v3 paths.

## Paper contribution enabled

If the evidence passes the gates below, the paper may claim that AuthGuard-Seq is a
compact long-context bytecode model whose advantage over a flat sequence encoder is
measured under controlled input budgets. The paper may further quantify whether the
gain comes from coverage, chunking, attention, or their combination.

This is stronger and more defensible than attributing the current aggregate gain to
hierarchical attention without component controls.

## Immutable inputs

- `revision_v2/data/authguardbench_7702_v2.csv.gz`
- frozen family assignments and outer folds
- existing feature/token cache from `baseline_v2`
- existing partition-isolated Flood-200% transformation protocol
- existing three seeds: 7702, 7703, and 7704

The frozen guard must pass before and after every run.

## Controlled configurations

All neural configurations use the same observations, family-disjoint folds, validation
rotation, class weighting, optimizer, early stopping, calibration, and validation-derived
operating points.

| Configuration | Maximum detailed-token budget | Purpose |
|---|---:|---|
| `flat_control_2048` | 2,048 | Parameter-matched short flat control |
| `flat_control_16384` | 16,384 | Parameter-matched flat full-budget control |
| `chunk_attention_control_2048` | 2,048 (8 x 256) | Isolates long-stream coverage |
| `chunk_mean_control_16384` | 16,384 (64 x 256) | Isolates learned attention |
| `chunk_attention_control_16384` | 16,384 (64 x 256) | Controlled full hierarchy |
| `authguard_reference_16384` | 16,384 (64 x 256) | Retrained current paper architecture |

The first five models use the same embedding, two convolution layers, dropout, and risk
head. The flat and mean variants have identical trainable parameter counts; attention
adds only a 65-parameter scoring layer. The two flat models and all capped hierarchical
models use deterministic evenly spaced selection when the input exceeds their budget.
Flooded inputs are never allowed to bypass the declared cap.

## Evaluation

Primary clean metrics:

- AUPRC;
- AUROC;
- Brier score;
- Recall and realized FPR at validation-derived 1%, 5%, and 10% FPR thresholds.

Robustness metrics:

- the same metrics under Flood-200%;
- clean-to-flood paired deltas;
- per-row retained original-stream fraction;
- number of transformed inputs exceeding each configured budget.

Inference outputs are stored per row so paired family-clustered bootstrap confidence
intervals can be computed without retraining.

## Gates

### Gate A: coverage

Compare `chunk_attention_control_16384` with `chunk_attention_control_2048`.

- If the full-budget model is materially stronger, the contribution is long-context
  coverage.
- If not, the paper must not claim that full-stream coverage explains the gain.

### Gate B: attention

Compare `chunk_attention_control_16384` with `chunk_mean_control_16384`.

- If learned attention is materially stronger, attention remains part of the technical
  contribution.
- If not, attention is an implementation choice rather than a novelty claim.

### Gate C: hierarchy

Compare `chunk_attention_control_16384` with `flat_control_16384`.

- If the hierarchical model remains stronger at the same token budget, the architecture
  contribution survives the principal reviewer objection.
- If not, the paper will frame hierarchy as an efficient engineering strategy and report
  the result honestly.

### Gate D: robustness

Compare models under identical declared budgets and report both absolute transformed
performance and clean-to-transformed degradation.

- No transformed-input superiority headline is retained unless the advantage survives
  fixed-cap evaluation with family-clustered uncertainty.

### Gate E: transfer to the reported model

Evaluate `authguard_reference_16384` under the corrected cap. This connects the controlled
mechanism study back to the current paper architecture but is not treated as a
parameter-matched causal contrast.

## Reproducibility and isolation

- Code: `revision_v2/experiments/long_context_ablation_v3/`
- Results: `revision_v2/results/long_context_ablation_v3/`
- Logs: `revision_v2/logs/long_context_ablation_v3/`
- No existing result, checkpoint, paper, or frozen artifact is overwritten.
- A resumable checkpoint records completed model/seed/fold units.
- Smoke mode uses a separate `smoke/` output directory.

## Execution sequence

1. Implement models, fixed-budget encoders, persistence, and verification.
2. Run unit/import checks and frozen guard.
3. Run a detached smoke experiment.
4. Verify smoke outputs and protocol invariants.
5. Launch the full run as a detached background job.
6. Launch a separate background waiter that records completion status.
7. Generate aggregate tables, paired family-bootstrap intervals, and a contribution
   decision report.
8. Rewrite the paper only after the gates resolve.
