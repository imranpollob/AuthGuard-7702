# Baseline Evaluation Report — Revision v2

Research question: **does AuthGuard-Seq outperform reasonable traditional and neural
bytecode-learning baselines under the corrected family-disjoint Revision v2
benchmark?**

Answer: **yes, on every primary metric, against every baseline, and on every seed**,
while remaining one of the cheapest models to run.

Benchmark: `revision_v2/data/authguardbench_7702_v2.csv.gz`, PRIMARY_EVALUATION only
(727 source-flagged vs 1,463 source-unflagged EIP-7702 delegates; 2,190 rows; 790
frozen families). Protocol, architectures, and fairness controls are documented in
`BASELINE_IMPLEMENTATION_NOTES.md`. Seeds 7702/7703/7704, all 5 frozen family-disjoint
outer folds, validation-based model selection, temperature calibration on validation,
thresholds from validation negatives, no test-set tuning. Frozen-artifact guard passed
before and after the run (144 files unchanged).

## Primary results (3-seed mean ± SD across seed-level means)

| model | AUPRC | AUROC | Recall@5%FPR | Recall@1%FPR | Recall@10%FPR | Brier (cal.) |
|---|---|---|---|---|---|---|
| **AuthGuard-Seq** | **0.924 ± 0.014** | **0.963** | **0.833 ± 0.016** | **0.569** | **0.917** | **0.072** |
| flat CNN | 0.885 ± 0.010 | 0.937 | 0.712 ± 0.024 | 0.474 | 0.790 | 0.099 |
| hist+4-gram XGBoost | 0.833 ± 0.004 | 0.908 | 0.615 ± 0.015 | 0.320 | 0.709 | 0.127 |
| ngram_only (neural) | 0.810 ± 0.007 | 0.880 | 0.654 ± 0.029 | 0.170 | 0.776 | 0.125 |
| BiGRU | 0.679 ± 0.098 | 0.815 | 0.379 ± 0.113 | 0.160 | 0.521 | 0.163 |
| dense_only (structural) | 0.637 ± 0.018 | 0.780 | 0.331 ± 0.023 | 0.116 | 0.488 | 0.182 |
| Transformer | 0.563 ± 0.031 | 0.730 | 0.239 ± 0.054 | 0.042 | 0.371 | 0.208 |

Full per-model×seed×fold numbers: `baseline_fold_seed_results.csv`
(also `baseline_summary.csv` for the aggregated table). Achieved FPRs sit close to
their validation-derived targets for all models (e.g. AuthGuard-Seq FPR@5% = 0.052,
XGBoost 0.071, CNN 0.059).

## Per-seed consistency (AUPRC, mean over 5 folds)

| model | seed 7702 | seed 7703 | seed 7704 | spread |
|---|---|---|---|---|
| AuthGuard-Seq | 0.916 | 0.913 | 0.944 | 0.031 |
| flat CNN | 0.883 | 0.874 | 0.898 | 0.024 |
| hist+4-gram XGBoost | 0.828 | 0.833 | 0.839 | 0.011 |
| ngram_only | 0.817 | 0.812 | 0.801 | 0.017 |
| BiGRU | 0.744 | **0.541** | 0.753 | **0.212** |
| dense_only | 0.625 | 0.625 | 0.662 | 0.037 |
| Transformer | 0.520 | 0.592 | 0.575 | 0.072 |

AuthGuard-Seq beats the flat CNN on **every** seed (Δ +0.033 / +0.039 / +0.046) and
XGBoost on **every** seed (Δ +0.088 / +0.080 / +0.105). The ordering
Seq > CNN > XGBoost > ngram_only is stable across all three seeds.

## Model complexity and inference cost

CPU, batch size 1, model forward only (featurization excluded), 200 test contracts
of seed 7702 / fold 0 (`baseline_model_complexity.csv`):

| model | trainable params | serialized size | latency mean / median / p95 (ms) |
|---|---|---|---|
| hist+4-gram XGBoost | — (300 trees) | 397 KB | 0.31 / 0.29 / 0.40 |
| dense_only | 181,877 | 720 KB | 0.33 / 0.32 / 0.38 |
| ngram_only | 181,877 | 720 KB | 0.33 / 0.32 / 0.36 |
| **AuthGuard-Seq** | **181,877** | **720 KB** | **1.01 / 0.95 / 1.59** |
| flat CNN | 154,177 | 605 KB | 2.57 / 2.53 / 2.80 |
| Transformer | 425,217 | 1.63 MB | 23.7 / 34.3 / 36.5 |
| BiGRU | 108,225 | 426 KB | 60.5 / 59.5 / 103.0 |

AuthGuard-Seq is **Pareto-optimal**: it has the best accuracy and, at ~1 ms per
contract, is the fastest of the four true sequence models — the sequential GRU
(60 ms) and quadratic Transformer (24 ms) are 1–2 orders of magnitude slower for
worse accuracy. Only the accuracy-inferior XGBoost / dense / ngram models are faster
(sub-millisecond), and all are well under any interactive pre-authorization budget.

## §Debugging (fairness check, per required section 9)

- **BiGRU initial collapse.** A first BiGRU with masked-mean-only pooling over
  2,048-step uniform-sampled sequences trained to near-random (AUPRC ~0.45 on fold 0
  even at 25 epochs). Diagnosed as a readout problem, not a data/masking bug
  (tokenization, padding, packing, and class weighting were all verified correct). The
  standard sequence-classification readout — concatenated final forward/backward hidden
  states plus masked mean — restored it to AUPRC 0.77 on the same fold. This is a
  legitimate architecture fix, applied **before** any full run and **not** tuned
  against test performance.
- **BiGRU residual instability.** Even after the fix, BiGRU is the only unstable model:
  seed 7703 collapses to AUPRC 0.541 while 7702/7704 reach 0.744/0.753 (spread 0.212;
  Recall@5% SD 0.113). Long (2,048-step) sequential recurrence over opcode streams is
  optimization-fragile; we report the instability rather than cherry-picking seeds.
- **Transformer weakness is genuine, not a bug.** Convergence, masking
  (`src_key_padding_mask`), and positional embeddings were verified. A compact
  Transformer trained from scratch on 2,190 examples simply underperforms convolutional
  and hierarchical inductive biases at this data scale; we did not enlarge it or add
  pretraining (out of scope, and a large LM was explicitly excluded).
- No model was tuned to match AuthGuard-Seq; all share the identical protocol and were
  each given a single reasonable architecture.

## Reading of the results

1. **Opcode *sequence* structure matters.** The two models that consume the ordered
   opcode stream with a suitable inductive bias — AuthGuard-Seq (hierarchical
   chunk-attention) and the flat CNN (local convolutions) — are the top two, both
   above the bag-of-features XGBoost. The order-agnostic structural model (dense_only)
   and the hashed-n-gram models trail.
2. **Hierarchy adds a real, consistent increment.** On top of a strong flat CNN,
   AuthGuard-Seq's chunk-attention adds +0.039 AUPRC and +0.121 Recall@5%, consistently
   across seeds — evidence the hierarchical aggregation captures structure a flat
   receptive field misses (relevant for long delegates that exceed a flat window).
3. **Not every neural model beats the traditional baseline.** BiGRU, dense_only, and
   the Transformer all fall *below* hist+4-gram XGBoost, so "AuthGuard-Seq beats
   several neural nets" is not a trivial bar — XGBoost is a genuinely strong,
   low-variance baseline (SD 0.004). The win is specifically an architecture win for
   hierarchical opcode-sequence modeling.
4. **Corrected-benchmark consistency.** AuthGuard-Seq's 3-seed AUPRC here (0.924)
   matches the audit signal-check (0.920 at seed 7702) and the original-benchmark
   3-seed headline (0.931), confirming the model comparison is stable on the corrected
   data.

## Scope / caveats

- These are *primary-task* numbers only (source-flagged vs source-unflagged delegates);
  robustness (transformations, flooding), controls, and paired significance tests are
  out of scope for this stage. Held-out predictions with per-row calibrated scores and
  thresholds are preserved in `baseline_predictions.csv.gz` for the later paired
  family-clustered significance analysis.
- All label-semantics caveats from `revision_v2/audit/LABEL_CLAIM_CONTRACT.md` apply:
  the task is *source-identified risk screening*, and "outperforms" refers to
  reproducing the source analyzer's decision boundary from bytecode, not to
  independently confirmed maliciousness.
