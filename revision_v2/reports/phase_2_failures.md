# Phase 2 Failures and Deviations

- Independent human adjudication is not complete. The 170-item blinded package is ready, but
  no human judgments were fabricated; agreement remains `pending_human_labels`.
- Execution validation is bounded to ten representative delegates and a fixed calldata suite.
  It does not prove general semantic equivalence.
- M3 intentionally reroutes renamed sensitive selectors, so full trace equality is neither
  expected nor claimed for those calls.
- The benign-AA control has only five cases and supports case observations, not an FPR estimate.
