# Sequence+Dense Architecture and Training Protocol

## Architecture

`authguard_sequence_dense` (`HybridModel`, `revision_v3.src.models.hybrid`): a chunked
opcode-sequence encoder (227-token vocabulary, 256-token chunks, up to 64 chunks —
16,384-token budget, evenly-spaced downsampling rather than prefix truncation when a
contract exceeds the budget) combined via a learned per-sample gate with a 261-dimensional
dense view (225-d opcode histogram + 36-d structural/selector features). 97,645 active
parameters (forward+backward-verified, not merely `requires_grad` count — see Phase 2's
`PARAMETER_ACCOUNTING_REPORT.md`). Selected over the sequence-only reference
(`authguard_reference_v3`) for a statistically supported (+0.052 AUPRC, bootstrap CI excludes
zero) robustness advantage under Flood-200% transformation, with clean-data performance
statistically tied.

## Training protocol

5 stored, family-disjoint outer folds (test = fold $f$, validation = fold $(f{+}1)\bmod 5$,
train = remaining 3); 3 seeds (7702/7703/7704, actual per-fold seed = seed + test_fold);
class-weighted `BCEWithLogitsLoss` (`pos_weight = n_neg/n_pos` on the train fold); AdamW
(lr=1e-3, weight_decay=1e-4, gradient-norm clip 5.0, batch size 16); early stopping on
validation AUPRC (patience 5, max 30 epochs); single-scalar temperature scaling (LBFGS) fit
on validation logits only; nominal 1%/5%/10% FPR thresholds derived from validation negatives
only. Strict determinism (`cudnn.deterministic=True`, `torch.use_deterministic_algorithms(True)`
in strict — not warn-only — mode, `CUBLAS_WORKSPACE_CONFIG=:4096:8`), verified by two
independent runs of the same seed/fold producing bit-identical test predictions
(`revision_v3/tests/test_determinism.py`).

## This pass's fine-tuning extension (provisional)

Part 7 of this pipeline pass extended the training harness (without modifying it) to support
10 retraining/fine-tuning variants for a **provisional final model** exercise on the tiny (47
binary-labeled) Gold-Dev sample: plain fine-tuning, confidence-weighted BCE, source-vs.-
provisional-label agreement weighting, label-smoothing as a noise-robust approximation,
generalized cross-entropy, a simplified non-negative PU-learning loss (treating UNCERTAIN
items as the unlabeled pool), soft-label training from LLM confidence, a sequence-encoder-
frozen variant, and threshold-only recalibration. `confidence_weighted` won on both mean
validation AUPRC (0.969) and stability (std 0.017 across 6 family-grouped CV runs) — see
`LLM_PROVISIONAL_RETRAINING_REPORT.md` for the full comparison and its small-sample caveats.
