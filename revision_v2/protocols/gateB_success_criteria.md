# Gate B Success Criteria — Selective Escalation (frozen BEFORE results)

Mechanism: a deterministic escalation rule routes a bytecode either to the automatic
AuthGuard-v2 decision or to "escalate to deeper analysis". All cutoffs are selected on
training/validation populations only and frozen before test evaluation.

Candidate signals (each computable from bytecode + training-population statistics only):
S1 known conflicting exact-bytecode history (frozen 23-hash list);
S2 trailing-byte ratio (post-terminal bytes / total bytes);
S3 full-view vs restricted-view score disagreement (|Δscore|);
S4 low prediction margin (|score − threshold|);
S5 cross-seed prediction disagreement (5-seed ensemble variance);
S6 feature-space outlier score (distance to k-th nearest training neighbor in the dense
   feature space, k=5, standardized);
S7 transformation indicators (e.g., metadata absent/rewritten pattern, appended-code volume).

Trivial baseline (must be run first): escalate the lowest-|margin| x% of cases
("low-confidence abstention"), x matched to the candidate rule's escalation rate.

## Success requires ALL of the following at an operating point with escalation rate ≤ 15%:

1. Error concentration: the escalated subset's error density (FN+FP per escalated case) is
   ≥ 2× the non-escalated subset's error density under the clean condition, with family-
   clustered 95% CI of the ratio excluding 1.
2. Automatic-coverage quality: recall among non-escalated malicious does not fall below the
   full-population recall, and non-escalated FPR does not exceed full-population FPR.
3. Robust value: under at least one of {G-VOL +200%, compound M3+F200}, escalation captures
   ≥ 33% of the false negatives at ≤ 15% escalation.
4. Beats the trivial baseline: at matched escalation rate, error concentration (1) exceeds
   the low-confidence-abstention baseline's concentration by a margin whose family-clustered
   CI excludes 0.
5. EIP-7702-specific justification: at least one contributing signal must be
   delegation-context-specific (S1 conflict history or S2/S3 terminal/trailing structure),
   not purely generic (margin alone does not qualify).

If ANY criterion fails, Gate B fails: results retained internally
(`revision_v2/results/gateB/`), reported honestly, not added to the manuscript.
