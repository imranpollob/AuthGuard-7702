# Family-Disjoint Evaluation, Corrected Bootstrap, Parameter-Matched Analysis, Final Robustness

(This section largely restates Phase 2 methodology, carried unchanged into this pipeline
pass — see the corresponding Phase 2 reports for full detail; only the extensions made in
this pass are new here.)

## Family-disjoint evaluation and checkpoint provenance

The primary benchmark uses five stored, family-disjoint outer folds. For outer test fold
$f$, training uses three folds and validation uses $(f+1)\bmod 5$; every test item is therefore
scored by a checkpoint that saw neither that item nor any member of its bytecode family during
training or validation.

Gold-Dev and Gold-Test are sampled from this primary benchmark. They are family-disjoint from
one another, but they are **not external to model development**, and an all-fold ensemble is
invalid for them because three of five checkpoints trained on each sampled family. The repaired
protocol resolves every sampled `family_id` to its canonical fold and uses only that fold's
held-out-test checkpoint, with the threshold learned by the same checkpoint. Unknown non-empty
family identifiers are rejected. Only a post-cutoff/control runtime for which provenance
matching finds no canonical family may use the all-fold external ensemble. Mixed control sets
apply this rule item by item and report the fraction of eligible checkpoints exceeding each
checkpoint's own validation-derived threshold.

The DCRG-only and DCRG+sequence experiments use the same outer folds and three seeds. DCRG
XGBoost parameters and noisy-OR fusion are fixed before test evaluation; context calibration
and nominal-FPR thresholds use validation data only. Paired differences are evaluated with one
family-multiset bootstrap draw shared across all seeds. Human-reference results remain
provisional until the independent reviews are completed and adjudicated.

## Predeclared human-final evaluation

Gold-Test is accepted for final analysis only when its release contains exactly the 150 frozen
manifest items, every item has a final adjudicated label (including explicit indeterminate or
not-screenable outcomes), and both `NO_CONCRETE_UNSAFE_BEHAVIOR_FOUND` and UNSAFE are present.
`INDETERMINATE` and `NOT_BYTECODE_SCREENABLE` are counted and reported but excluded from
binary metrics. The evaluator refuses duplicate or unknown labels, inconsistent review
metadata, incomplete dual review/adjudication, and any missing seed/item prediction. No model
is retrained, recalibrated, or selected using Gold-Test.

Before any Gold-Test annotation existed, we materialized label-free, score-only prediction
tables for the sequence/DCRG/fusion comparison and all four predeclared DCRG representation
variants. A one-time lock binds those tables, the sample manifest, seed set, and feature groups
by SHA-256. Final evaluation verifies the lock before opening the human-label release. Thus the
independent labels cannot influence training, calibration, thresholds, model selection, or the
choice of representation ablations.

For each eligible item and seed, sequence, DCRG, and fixed noisy-OR fusion use the score and
nominal-5%-FPR threshold belonging to that item's held-out family checkpoint. We report AUPRC,
AUROC, Brier score, calibration error, precision, recall, F1, and observed FPR; selective
results additionally report deferral, warning recall/FPR, and every human-UNSAFE item assigned
`LOW_OBSERVED_RISK`. Fusion-minus-sequence and fusion-minus-DCRG intervals use the same paired,
seed-aware family bootstrap described below. This analysis can establish label-independent
performance on a frozen audit sample, but not post-cutoff external validity.

The same evaluator reports full-DCRG minus capability-only CFG, untyped-guard, and
protocol-actor-removed variants using paired family-clustered intervals for AUPRC, recall, and
observed FPR at the fixed operating points. Typed or authority-relative superiority is claimed
only if a predeclared interval supports its direction; otherwise that part of the proposed
novelty is explicitly rejected.

## Corrected bootstrap

Phase 2 identified and fixed a "combine confidence intervals after the fact" statistical bug
in the original bootstrap methodology; the corrected seed-aware, paired, family-clustered
bootstrap (`revision_v3.src.evaluation.bootstrap_v2.seed_aware_paired_bootstrap_ci`) is the
standard used throughout. This pass's Gold-Test AUPRC confidence intervals
(`run_gold_test_evaluation.py::bootstrap_ci_metric`) use the same family-clustered
resampling principle (resample unique families with replacement, not individual items),
extended to a single-model (non-paired) CI since Part 9 reports absolute AUPRC per model
rather than only paired deltas.

## Parameter-matched analysis

The parameter-matched Flat CNN (`flat_cnn_matched_16384`, Phase 2) is carried through as a
comparison point in this pass's Gold-Dev/Gold-Test/deployment evaluations exactly as
originally matched — no re-matching was performed or needed.

## Final robustness

Phase 2's paper-grade Flood-200% robustness result (the basis for selecting
`authguard_sequence_dense` over the sequence-only reference) is unchanged by this pipeline
pass. **Not yet re-run against provisional or human labels** — see the reviewer-concern
closure matrix, row 10 (PARTIALLY_RESOLVED), for the concrete follow-up.
