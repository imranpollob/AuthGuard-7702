# Provisional Cascade Report

**LABEL_SOURCE=LLM_PROVISIONAL. STATUS=PROVISIONAL_NOT_FOR_FINAL_CLAIMS.**

Escalation band selected on Gold-Dev only (score tercile: [0.044, 0.581] on
`authguard_sequence_dense`'s calibrated scores), frozen, then evaluated once on Gold-Test —
not revised afterward. Script: `run_cascade_evaluation.py`. Full output:
`results/llm_provisional/cascade/cascade_report.json`.

## Gold-Test results (n=138 binary items; policy E uses all 150)

| Policy | % Escalated | % Resolved Locally | Recall (UNSAFE coverage) | FNR | FPR | Avg. cost (ms, measured stages only) |
|---|---|---|---|---|---|---|
| A. AuthGuard alone | 0.0% | 100.0% | 0.336 | 0.664 | 0.429 | 2.90 |
| B. Static rule alone | 0.0% | 100.0% | 0.344 | 0.656 | 0.143 | 0.01 |
| C. AuthGuard-first, rule escalation | 37.0% | 63.0% | 0.344 | 0.656 | 0.143 | 2.90 |
| D. Rule-first, AuthGuard escalation | 33.3% | 66.7% | 0.336 | 0.664 | 0.143 | 0.98 |
| E. Uncertainty-triggered escalation | 8.0% | 92.0% | — (routing only) | — | — | not measured |

## Interpretation

- Policy C (AuthGuard-first, escalate the score-ambiguous middle tercile to the static rule)
  recovers the static rule's better FPR (0.143 vs. AuthGuard-alone's 0.429) while still
  resolving 63% of items from the cheap AuthGuard score alone — a genuine, measured workload
  reduction, not an assumption.
- Policy D (rule-first, escalate only rule-flagged items to AuthGuard) resolves 66.7% locally
  (as a free "not flagged → SAFE" default) at the same improved FPR, with a lower average
  measured cost (0.98ms vs. 2.90ms) since AuthGuard only runs on the escalated 33.3%.
- Neither cascade improves recall beyond AuthGuard-alone/rule-alone's shared recall ceiling
  (~0.34) — this pipeline's cascades trade workload for precision/FPR, not for coverage. That
  ceiling is a property of the underlying detectors, not the cascade logic.
- Policy E's "deeper review" cost for the 8% escalated (UNCERTAIN) items is explicitly **not
  measured** — no such downstream system was run in this pass. Reporting only the real routing
  rate avoids implying a false precision about human/deep-review cost.

## Escalation-band selection integrity

The tercile band was computed from Gold-Dev scores only, before Gold-Test was touched by this
script; Gold-Test results above did not feed back into the band (verified by
`run_cascade_evaluation.py`'s call order — band computed, then frozen, then applied once).
