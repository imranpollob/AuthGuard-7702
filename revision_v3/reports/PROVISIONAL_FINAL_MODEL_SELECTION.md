# PROVISIONAL FINAL MODEL Selection

**LABEL_SOURCE=LLM_PROVISIONAL. STATUS=PROVISIONAL_NOT_FOR_FINAL_CLAIMS.**

This selects a **PROVISIONAL FINAL MODEL** — explicitly not a replacement for the Phase 2
frozen model (`configs/final_model.json`, `authguard_sequence_dense`), which is preserved
unchanged. Both configurations exist side by side:

- `phase2_frozen_model`: `revision_v3/configs/final_model.json` (untouched)
- `llm_provisional_selected_model`: `revision_v3/configs/provisional_final_model.json` (new)

## Selection basis: Gold-Dev only

Using Part 7's 10-method retraining comparison (`LLM_PROVISIONAL_RETRAINING_REPORT.md`),
`confidence_weighted` fine-tuning was selected on **multiple criteria, not point-estimate
AUPRC alone**:

| Criterion | confidence_weighted | Runner-up | Basis |
|---|---|---|---|
| Mean val AUPRC | 0.969 | 0.962 (source_plus_provisional_weighting) | highest |
| Stability (std across 6 CV runs) | 0.017 | 0.020 | lowest / most stable |
| Complexity | identical architecture to frozen baseline | — | no added parameters |
| Uncertainty-coverage behavior | unchanged from frozen model (UNCERTAIN excluded from training entirely) | — | no regression |

No architecture change (`sequence_dense_weight_adjustment`, the one method that altered which
weights train, actually performed *worse* than the frozen baseline — see the retraining
report) — so the provisional final model is architecturally identical to
`authguard_sequence_dense`, differing only in fine-tuned weights.

## What was actually frozen

3 seeds (7702/7703/7704), each fine-tuned on **all 47** Gold-Dev binary-labeled items (not
just a CV fold) using `confidence_weighted` loss, 20 epochs, calibrated + thresholded on an
80/20 held-out split of the same 47 items (no Gold-Test involvement whatsoever). Checkpoints:
`results/llm_provisional/provisional_final_model_checkpoints/provisional_final_model_seed{7702,7703,7704}.pt`.

## A concrete, honest caution surfaced by freezing this model

The calibration/threshold step, run on a ~9-item random split of an already-tiny 47-item set,
produced degenerate thresholds for 2 of the 3 seeds (`threshold_5pct≈0.000`) — i.e. almost any
score clears the bar. This was NOT caught until Part 9's Gold-Test evaluation, where the
provisional final model showed recall=1.000 but FPR=0.857 (predicting nearly everything
UNSAFE). This is reported transparently as a first-order finding of this exercise: **naive
threshold selection on a 47-item calibration split does not reliably generalize**, and is
exactly the kind of failure mode independent human labels (with a larger, better-balanced
Gold-Dev set) should help avoid. See `LLM_PROVISIONAL_GOLD_TEST_REPORT.md`.

## Term usage

Every artifact from this selection is labeled **PROVISIONAL FINAL MODEL** in its own
metadata (`configs/provisional_final_model.json`'s `_comment` and `STATUS` fields;
`results/llm_provisional/provisional_final_model_manifest.json`). It is not referred to as
"the final model" anywhere in this pipeline's outputs.
