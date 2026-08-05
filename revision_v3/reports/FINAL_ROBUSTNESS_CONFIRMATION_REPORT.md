# Final Robustness Confirmation Report — Phase 2, Part 3

## Protocol

Independent, paper-grade Flood-200% reimplementation (`revision_v3/src/robustness/flooding_v2.py`),
differing from Phase 1's simplified version in three ways: (1) "200%" is computed against the
**executable region only** (CBOR metadata trailer detected and excluded — verified against a
sample of the primary population: detected trailers average 53 bytes for
`has_cbor_metadata=True` rows, consistent with a standard Solidity IPFS+solc-version CBOR
map); (2) donors are also stripped to their own executable region before being appended;
(3) **3 independent transformation seeds per recipient** (seeds 1/2/3, orthogonal to the 3
model-training seeds) so donor-selection variance is directly measurable, not just
model-training variance. Family exclusion and deterministic seeding are preserved from Phase
1. All 5 models are scored at their native 16,384-token budget from already-trained
checkpoints — no retraining. Full data:
`revision_v3/results/final_robustness/final_robustness_predictions.csv.gz` (5 models × 15
fold-seeds × ~446 test rows × [1 clean + 3 flood variants] ≈ 133,800 scored inferences),
`final_robustness_summary.csv`, `final_robustness_ABC_bootstrap.json`,
`donor_selection_variance.csv`, `donor_provenance_sample.json`.

## Descriptive results (flood score = mean across the 3 transformation seeds)

| Model | Clean AUPRC | Flood AUPRC | Absolute degradation | Mean donor-variance (SD across 3 transform seeds) |
|---|---:|---:|---:|---:|
| authguard_reference_v3 | 0.929 ± 0.015 | 0.853 ± 0.023 | 0.077 | 0.066 |
| chunk_max_16384 | 0.914 ± 0.011 | 0.842 ± 0.018 | 0.072 | 0.091 |
| **authguard_sequence_dense** | 0.920 ± 0.004 | **0.898 ± 0.010** | **0.022** | **0.055** |
| flat_cnn_matched_16384 | 0.942 ± 0.019 | 0.861 ± 0.057 | 0.081 | 0.097 |
| flat_cnn_16384 (original, 4× params) | 0.951 ± 0.006 | 0.859 ± 0.024 | 0.092 | 0.109 |

`authguard_sequence_dense` has both the smallest absolute degradation under flooding **and**
the lowest sensitivity to which specific donor bytes get appended (lowest donor-variance) of
all 5 models.

## Question A — Does chunk attention significantly outperform chunk max under flooding?

| ΔAUPRC (reference − chunk_max), Flood [95% CI] | Excludes 0? |
|---:|:---:|
| +0.018 [−0.031, +0.067] | **No** |

**No.** Under the final protocol, attention pooling is *not* significantly more robust to
flooding than max pooling. (Recall from `CONTROLLED_ABLATION_REPORT.md` that attention *does*
significantly beat mean pooling — but max pooling, a zero-parameter aggregator, remains
statistically indistinguishable from attention on both clean data and now confirmed under
flooding too.)

## Question B — Does authguard_sequence_dense significantly outperform authguard_reference_v3 under flooding?

| ΔAUPRC (sequence_dense − reference), Flood [95% CI] | Excludes 0? |
|---:|:---:|
| **+0.052 [+0.030, +0.077]** | **Yes** |

**Yes — confirmed, not just a lead.** Phase 1's `MATCHED_ROBUSTNESS_REPORT.md` §7 explicitly
flagged this as "an interesting, unconfirmed lead... a single point estimate from one retrain,
with no paired family-clustered bootstrap CI." Under the final protocol, with a proper
seed-aware paired bootstrap, **the advantage is confirmed statistically significant**, and its
magnitude (+0.052 AUPRC, ~6% relative improvement over the reference's 0.853 flood AUPRC) is
practically meaningful, not a marginal effect. This is the single most decision-relevant
finding of Phase 2 for the final model choice (see `FINAL_MODEL_SELECTION.md`).

## Question C — Does the hierarchical reference remain more robust than a parameter-matched Flat CNN?

| Comparison | ΔAUPRC, Flood [95% CI] | Excludes 0? |
|---|---:|:---:|
| reference − flat_cnn_matched_16384 | −0.015 [−0.047, +0.016] | No |
| reference − flat_cnn_16384 (original) | +0.012 [−0.020, +0.044] | No |

**No longer significant either way**, against *either* flat CNN variant. This is a materially
different picture from Phase 1's `MATCHED_ROBUSTNESS_REPORT.md` (chunk_attention beat the
original flat CNN significantly at every budget) and even from Part 2's simplified-flooding
parameter-matched comparison (where the 16,384-budget difference was already not significant,
consistent with this). With the more careful, executable-region-aware, multi-donor-seed
protocol, **the hierarchical reference model's robustness advantage over flat processing does
not survive** at the 16,384 budget against either flat CNN variant. Combined with Question A,
none of {attention vs. max pooling, hierarchy vs. flat} is a confirmed robustness advantage
under the final protocol — the ONLY confirmed robustness advantage found anywhere in Phase 2
is the dense-feature hybrid (Question B).

## Question D — How much variance is introduced by donor selection?

`donor_selection_variance.csv`: for each (model, recipient, model-seed, fold), the standard
deviation of the flood score across the 3 independent transformation seeds.

| Model | Mean SD across transform seeds | Median | Max (worst case) |
|---|---:|---:|---:|
| authguard_sequence_dense | **0.055** | 0.012 | 0.557 |
| authguard_reference_v3 | 0.066 | 0.023 | 0.573 |
| chunk_max_16384 | 0.091 | 0.029 | 0.571 |
| flat_cnn_matched_16384 | 0.097 | 0.028 | 0.577 |
| flat_cnn_16384 | 0.109 | 0.028 | 0.576 |

Donor-selection variance is **substantial for every model** — median SD 0.012–0.029 is modest,
but the mean is pulled up by a heavy tail (max SD approaches 0.57–0.58 for all five models,
meaning for a minority of individual recipients, which specific donor bytes get appended can
swing the flood score by more than half the 0–1 range). This means **any single-transform-seed
robustness number (including all of Phase 1's and Part 2's results) carries real, previously
unquantified uncertainty from donor selection alone**, independent of family-clustered sampling
uncertainty or model-training-seed variance. Flat CNN variants are consistently the most
donor-sensitive; `authguard_sequence_dense` is the least.

## Overall interpretation

The final, most careful robustness protocol **narrows** most of Phase 1's headline robustness
claims (hierarchy-vs-flat, attention-vs-max no longer significant) while **confirming and
strengthening** the one candidate that actually matters for the final model decision:
`authguard_sequence_dense`'s robustness advantage is real, statistically supported, and larger
in magnitude than any of the architecture-pooling effects that motivated the original
hierarchical design. See `FINAL_MODEL_SELECTION.md` for how this changes the recommended final
model.
