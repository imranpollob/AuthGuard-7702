# Parameter-Matched Flat vs. Hierarchical Comparison Report — Phase 2, Part 2

## The parameter-matched architecture

`flat_cnn_matched_*` (`revision_v3/experiments/parameter_matched/model_specs.py`): identical
architecture family to the original `flat_cnn_*` (embedding → Conv1d k=7 → Conv1d k=5 →
masked max pool → linear head), with `embedding_dim=32, channels=60` instead of
`embedding_dim=64, channels=128`. This gives **38,885 active parameters** — 0.84% above
`authguard_reference_v3`'s 38,562 active parameters, well inside the required ±10% band
(34,706–42,418). FlatCNN has no dead branches (confirmed in Phase 1's
`PARAMETER_ACCOUNTING_REPORT.md`), so total = active for both models being compared.

Trained at all 3 budgets (2,048 / 8,192 / 16,384 tokens) under the identical canonical
protocol (5 folds × 3 seeds, deterministic). Results:
`revision_v3/results/parameter_matched/parameter_matched_summary.csv`.

| Model | AUPRC | Recall@5% FPR |
|---|---:|---:|
| flat_cnn_matched_2048 | 0.878 ± 0.008 | 0.714 ± 0.007 |
| flat_cnn_matched_8192 | 0.945 ± 0.016 | 0.858 ± 0.011 |
| flat_cnn_matched_16384 | 0.942 ± 0.019 | 0.856 ± 0.011 |
| authguard_reference_v3 (chunk_attention_16384, Phase 1 reference) | 0.929 ± 0.015 | 0.843 ± 0.014 |

## Clean-data comparison (corrected seed-aware bootstrap)

| Budget | ΔAUPRC (chunk_attention − matched_flat) [95% CI] | Excludes 0? | ΔRecall@5% [95% CI] | Excludes 0? |
|---:|---:|:---:|---:|:---:|
| 2,048 | **+0.033 [+0.004, +0.066]** | **Yes** | **+0.112 [+0.045, +0.190]** | **Yes** |
| 8,192 | **−0.030 [−0.064, −0.001]** | **Yes** | −0.006 [−0.034, +0.024] | No |
| 16,384 | −0.022 [−0.055, +0.008] | No | −0.007 [−0.042, +0.022] | No |

**Budget-dependent, not a uniform winner.** At the smallest budget (2,048), the hierarchical
model significantly beats the parameter-matched flat CNN on both metrics. At 8,192, the
parameter-matched flat CNN significantly beats the hierarchical model on AUPRC (Recall@5% not
significant). At 16,384, neither model has a significant clean-data advantage.

**This directly clarifies the Part 1 finding that the *original, 4×-larger* flat CNN
significantly beat `authguard_reference_v3` at 16,384 tokens** (`CORRECTED_BOOTSTRAP_REPORT.md`
§"Which conclusions changed", item 1). With parameters matched, that 16,384-budget advantage
for the flat architecture **disappears** (CI now crosses zero). This is evidence — not proof,
but directly relevant evidence — that the original large flat CNN's edge at 16,384 tokens was
substantially a parameter-capacity effect rather than a "flat beats hierarchical" architecture
effect. The 8,192-budget picture is murkier: even at matched parameters, flat still
significantly wins on AUPRC there, so capacity is not the *whole* explanation.

## Matched-budget Flood-200% comparison

Reusing Phase 1's flooding implementation (`revision_v3/src/robustness/flooding.py`) for
direct comparability with the existing `chunk_attention_*` vs. `flat_cnn_*` Flood-200% numbers
(Part 3 builds a more elaborate, independent flooding protocol separately). Full data:
`revision_v3/results/parameter_matched/parameter_matched_flood_bootstrap.csv`,
`parameter_matched_flood_predictions.csv.gz`.

| Budget | ΔAUPRC (chunk_attention − matched_flat), Flood-200% [95% CI] | Excludes 0? |
|---:|---:|:---:|
| 2,048 | **+0.361 [+0.264, +0.459]** | **Yes** |
| 8,192 | +0.021 [−0.018, +0.063] | No |
| 16,384 | +0.010 [−0.021, +0.041] | No |

## The central finding of Part 2: the robustness advantage was also partly a parameter-count effect

**Compare this to Phase 1's `MATCHED_ROBUSTNESS_REPORT.md`**, where `chunk_attention`
significantly beat the *original, 4×-larger* `flat_cnn_*` on Flood-200% AUPRC at **every**
budget (2,048: +0.365; 8,192: +0.062; 16,384: +0.049, all CIs excluding zero). Against the
**parameter-matched** flat CNN, that advantage **only survives at the smallest budget
(2,048)** — at 8,192 and 16,384 the corrected CIs cross zero.

**This is the single most important scientific finding of Phase 2 so far.** Phase 1's
headline claim ("the hierarchical reference model is significantly more robust to flooding
than a flat CNN of identical token budget, at every budget tested") requires a caveat that was
not previously known: it holds unambiguously only when the flat CNN also has many more
parameters. Once *both* budget and parameter count are controlled, the robustness advantage of
hierarchy over flat processing is real but narrower — clearly present only at the smallest
(2,048-token) budget, where flooding also causes the most severe budget exceedance (81.9% of
flooded sequences exceed 2,048 tokens per Phase 1's `transformed_length_distribution.csv`).

## Answering the Part 2 question directly

> "Does hierarchy provide any benefit once both token budget and parameter capacity are
> controlled?"

**Partially, and budget-dependently.** At the smallest tested budget (2,048 tokens), yes —
hierarchy provides a clear, statistically significant benefit on both clean data and under
flooding, even at matched parameters. At larger budgets (8,192, 16,384), no significant
clean-data or flood-robustness benefit of hierarchy survives parameter-matching — the
differences that looked like an architecture effect in Phase 1 were at least partly a capacity
effect. This nuances but does not eliminate the case for `authguard_reference_v3`: it remains
statistically undefeated at 16,384 (its native budget) once parameters are matched, and it
still has a real, large, and unambiguous advantage at 2,048. See `FINAL_MODEL_SELECTION.md`
(Part 4) for how this is weighed against Part 3's results.
