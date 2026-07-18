# Baseline Implementation Notes — Revision v2 Model Comparison

All models are trained and evaluated by
`revision_v2/experiments/baseline_v2/run_baseline_v2.py` on the corrected benchmark
`revision_v2/data/authguardbench_7702_v2.csv.gz`, PRIMARY_EVALUATION population only
(727 source-flagged vs 1,463 source-unflagged EIP-7702 delegates, 2,190 rows,
790 frozen families). Feature cache: `features_v2.npz` (identical to the audit
signal-check cache; row-hash verified). Frozen originals are read-only.

## Shared protocol (identical for every model)

- **Splits:** frozen family-disjoint outer folds `fold_id`. For outer test fold *f*,
  validation = fold *(f+1) mod 5*, training = the remaining three folds. No random
  splits; no test-set tuning.
- **Seeds:** 7702, 7703, 7704 (torch/numpy/random seeded per fold as `seed + fold`,
  matching the frozen AuthGuard-Fusion harness).
- **Label:** y = 1 for source-flagged delegates.
- **Class weighting:** `BCEWithLogitsLoss(pos_weight = n_neg/n_pos)` computed on the
  training fold (≈2.0). Applied to every neural model. XGBoost uses its default
  logloss (unweighted) exactly as the frozen baseline.
- **Model selection:** early stopping on **validation AUPRC**, patience 5, max 30
  epochs; the best-val-AUPRC checkpoint is restored before scoring.
- **Optimizer (neural):** AdamW, lr 1e-3, weight decay 1e-4, gradient-norm clip 5.0.
- **Calibration:** temperature scaling (single scalar, LBFGS) fit on **validation
  logits only**, applied to test logits. AUPRC/AUROC/recall-at-threshold are invariant
  to this monotone transform; it only affects the Brier score.
- **Thresholds:** derived from **validation-negative** calibrated scores at 1%/5%/10%
  FPR targets (`WarningPolicy`, frozen). Recall and achieved FPR on the test fold use
  these thresholds. Test labels never touch threshold selection.
- **Aggregation:** metrics per fold → mean over the 5 folds per seed → mean and SD
  across the 3 seed-level means.

## Input representations

The corpus opcode-token stream is produced by the frozen featurizer
(`authguard7702.features.encode_bytecode` → `pipeline/ag_features`). Vocabulary size
227 (PAD = 0, UNK = 1, 225 opcode tokens). Two feature families are cached:

- **Dense (261-d):** opcode histogram (225) + structural EVM statistics + sensitive
  selector scalars.
- **Hashed 4-gram (512-d):** hashed opcode 4-gram occurrence vector.
- **Opcode-token sequence:** per-contract linear-sweep opcode IDs (median 1,619
  tokens, p95 5,724, max 10,795).

**Flat-model input budget (fairness).** To avoid giving the hierarchical model a
*data* advantage, the flat sequence models (CNN, BiGRU, Transformer) receive the
**whole** contract via uniform-stride sampling to a fixed length: contracts ≤ max_len
are used at full resolution; longer contracts are evenly downsampled across their
entire opcode stream (the same whole-sequence-sampling idea AuthGuard-Seq applies at
the chunk level). This equalizes *what* each model sees and isolates the architectural
comparison. `max_len` = 2,048 for CNN and BiGRU; 1,024 for the Transformer (its
self-attention is O(L²); the smaller window is a documented memory limitation, not a
data-access advantage for other models). AuthGuard-Seq's effective token budget is up
to 64 × 256 = 16,384 sampled tokens, so it retains higher resolution on the longest
contracts — a property of the hierarchical design, reported honestly.

## Models

### hist_ngram_xgb — strongest traditional baseline
XGBoost (hist tree method) on the 225-d histogram + 512-d hashed 4-gram vector (737-d).
Hyperparameters identical to the frozen baseline: 300 trees, max_depth 6, lr 0.1,
subsample 0.9, colsample_bytree 0.8, logloss. Calibrated via temperature scaling of
the predicted-probability logit for a like-for-like Brier comparison.

### dense_only — dense structural neural baseline (existing)
The frozen `AuthGuardFusion` with only the dense view active: LayerNorm → Linear(261→128)
→ GELU → Dropout → Linear(128→64) → GELU, then the shared risk head. Dense features
standardized with train-fold mean/scale.

### ngram_only — neural hashed n-gram baseline (existing)
Same `AuthGuardFusion` with only the hashed-4-gram view active (MLP over the 512-d
vector).

### flat_cnn — non-hierarchical 1-D opcode CNN (new)
Embedding(227→64, padding_idx 0) → Conv1d(64→128, k7) → GELU → Conv1d(128→128, k5) →
GELU → masked max-pool over time → Dropout → Linear(128→1). Padding positions are
masked before pooling. max_len 2,048.

### bigru — bidirectional GRU (new)
Embedding(227→64) → BiGRU(hidden 96) over packed variable-length sequences → readout
= concat[final forward hidden, final backward hidden, masked-mean of outputs] (4×96 =
384-d) → Dropout → Linear(384→1). Packed sequences give exact lengths so padding never
contributes. (An initial masked-mean-only readout collapsed to near-random on
2,048-step sequences; the standard final-hidden-state readout resolved it — documented
in `BASELINE_EVALUATION_REPORT.md §debugging`.) max_len 2,048.

### transformer — compact Transformer encoder (new)
Embedding(227→128, padding_idx 0) + learned positional embedding → 2× TransformerEncoder
layers (d_model 128, 4 heads, FFN 256, GELU, dropout 0.1, batch_first) with
`src_key_padding_mask` → masked mean pool → Dropout → Linear(128→1). No pretrained LM.
max_len 1,024.

### authguard_seq — proposed hierarchical model (unchanged)
The frozen `AuthGuardFusion` with only the sequence view active: opcodes are split into
256-token chunks (≤ 64 chunks, evenly sampled if more), each chunk encoded by a dilated
Conv1d stack with masked max-pool, then combined by learned chunk attention. Architecture
and hyperparameters are exactly as in
`revision_v2/experiments/authguard_fusion/run_authguard_fusion.py`; **not modified for
this comparison.**

## Batch sizes
Fusion-based models (dense_only, ngram_only, authguard_seq) use batch 16 (their frozen
default); flat neural models use batch 32. Batch size is not a fairness axis in the
required protocol (folds, validation-based selection, seeds, and class weighting are
held identical); it is recorded here for reproducibility.

## Complexity / latency methodology
Trainable-parameter count and serialized `state_dict` size are measured directly.
Inference latency is measured on **CPU, batch size 1** over 200 test contracts of
seed 7702 / fold 0 (5-sample warmup discarded), reporting mean / median / p95
milliseconds for the **model forward pass only** (bytecode featurization/disassembly is
a shared preprocessing cost, excluded). CPU batch-1 reflects realistic local
pre-authorization screening in a wallet client.
