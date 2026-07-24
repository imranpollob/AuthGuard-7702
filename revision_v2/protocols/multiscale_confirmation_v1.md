# AuthGuard-MSP confirmatory protocol v1

Status: frozen after inspecting long-context v3 outer fold 0 and before inspecting any
outer-fold 1--4 result.

## Development observation

On development fold 0, increasing the flat-control budget was valuable, learned chunk
attention was stronger than mean aggregation in some seeds, but attention-only chunk
aggregation did not consistently retain the strongest local evidence. Fold 0 is therefore
excluded from every confirmatory result below.

## Model fixed before confirmation

AuthGuard-MSP uses the controlled local encoder:

- 32-dimensional opcode embeddings;
- kernel-5 64-channel convolution;
- kernel-3 64-channel dilated convolution with dilation 2;
- masked maximum pooling within each 256-opcode chunk.

It computes three contract-level summaries over valid chunks:

1. learned attention-weighted pooling;
2. uniform mean pooling; and
3. element-wise maximum pooling.

The summaries are concatenated, normalized, projected from 192 to 64 dimensions with
GELU and 0.15 dropout, and passed to a linear risk head. Inputs use at most 64 chunks
(16,384 opcode-token budget) with deterministic full-stream chunk selection above the
cap. No architecture or hyperparameter is changed after fold-1--4 results are viewed.

## Confirmation data and training

- Confirmatory test folds: 1, 2, 3, and 4 only.
- Development test fold 0 is not reported as confirmation.
- For test fold `f`, validation remains `(f + 1) mod 5`; the other three folds train.
- Seeds: 7702, 7703, 7704.
- Optimizer, class weighting, early stopping, temperature calibration, warning policy,
  and clean/F200 scoring match long-context ablation v3.
- F200 reuses the exact cached donor-isolated transformed rows from v3 and applies the
  same 16,384-token cap before scoring.

## Predeclared comparisons

Using only test folds 1--4 and paired family-clustered bootstrap intervals:

1. AuthGuard-MSP versus `chunk_attention_control_16384`;
2. AuthGuard-MSP versus `flat_control_16384`; and
3. AuthGuard-MSP versus `authguard_reference_16384`.

Clean AUPRC is primary. Fixed-cap F200 AUPRC and Recall@5% are operational secondary
outcomes.

## Decision

- A positive 95% interval versus the attention control supports multi-statistic
  aggregation as a model contribution.
- A positive interval versus the matched flat control supports the hierarchical model
  over the strongest budget control.
- The current AuthGuard reference remains the deployment-transfer comparator.
- Negative or inconclusive confirmation is retained and reported; it does not trigger
  another architecture search on these test folds.

