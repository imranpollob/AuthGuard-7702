# Family-Disjoint Evaluation, Corrected Bootstrap, Parameter-Matched Analysis, Final Robustness

(This section largely restates Phase 2 methodology, carried unchanged into this pipeline
pass — see the corresponding Phase 2 reports for full detail; only the extensions made in
this pass are new here.)

## Family-disjoint evaluation

Every evaluation split in this project (training folds, Gold-Dev, Gold-Test, and this pass's
internal Gold-Dev CV splits for retraining) enforces family-level disjointness — no two
near-duplicate bytecode variants of the same underlying contract appear on both sides of any
train/eval boundary. Verified for the new provisional pipeline by
`test_family_isolation_between_gold_dev_and_gold_test` and the retraining script's own
family-grouped K-fold logic (`group_kfold_indices`).

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
