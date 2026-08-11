# Historical pooled-family contribution decision (superseded)

Do not use these intervals in the manuscript. This first-pass diagnostic pooled
held-out families across folds and does not mirror the reported fold-then-seed
aggregation. The authoritative analysis is
`FOLD_CLUSTERED_CONTRIBUTION_DECISION.md`.

Decisions follow the predeclared family-clustered AUPRC contrasts.

| Gate | Condition | Delta AUPRC | 95% CI | Decision |
|---|---|---:|---:|---|
| coverage | M0 | +0.0049 | [-0.0044, +0.0165] | INCONCLUSIVE |
| attention | M0 | +0.0500 | [+0.0190, +0.0797] | SUPPORTED |
| hierarchy | M0 | -0.0161 | [-0.0619, +0.0199] | INCONCLUSIVE |
| coverage | F200 | -0.0041 | [-0.0207, +0.0135] | INCONCLUSIVE |
| attention | F200 | +0.2027 | [+0.1442, +0.2693] | SUPPORTED |
| hierarchy | F200 | +0.1058 | [+0.0362, +0.1775] | SUPPORTED |

The AuthGuard reference is a transfer check and is deliberately excluded from the
causal gate decisions.
