# AuthGuard-MSP confirmation implementation

1. Reuse the frozen v3 token cache, splits, clean loaders, calibration, warning policy,
   and fixed-cap F200 rows.
2. Add only the predeclared attention/mean/max aggregation and 192-to-64 fusion layer.
3. Train three seeds on confirmatory folds 1--4.
4. Persist per-row predictions, fold metrics, checkpoints, parameter counts, and history.
5. Join against v3 predictions on `(seed, fold, condition, sid)`.
6. Compute paired family-clustered AUPRC intervals for the three predeclared comparators.
7. Render a confirmation decision report and verify all cap/pairing invariants.

No fold-0 row enters confirmatory aggregates or intervals.

