# Provisional Reference-Label Methodology and Results

**Every number in this section is [PROVISIONAL — LLM_PROVISIONAL label source].**

## Methodology summary

See `LLM_PROVISIONAL_LABELING_PROTOCOL.md` for the full protocol. In brief: automated
evidence collection (verified-source check, decompilation, guard-tracing) feeds an LLM
interpretation step constrained by explicit hard rules (no UNSAFE from capability presence
alone, no SAFE from documentation alone, tx.origin flagged only when it guards a high-impact
capability, etc.), producing SAFE/UNSAFE/UNCERTAIN with a cited reason category for all 230
Pilot/Gold-Dev/Gold-Test items.

## Gold-Dev baseline (Table 7)

60 items (42 UNSAFE, 5 SAFE, 13 UNCERTAIN — 21.7% coverage excluded from binary metrics).
`authguard_sequence_dense`: AUPRC 0.925, AUROC 0.610, recall 0.357 at the frozen (Phase 1/2
validation-derived) threshold. All 4 continuous models produced the same confusion matrix at
n=47 — flagged, not hidden, as a small-sample coincidence in
`LLM_PROVISIONAL_GOLD_DEV_BASELINE_REPORT.md`.

## Retraining and provisional model selection (Tables — see retraining report)

10 fine-tuning methods compared on Gold-Dev only; `confidence_weighted` selected as the
**PROVISIONAL FINAL MODEL** basis on multi-criteria grounds (highest mean AUPRC 0.969 AND
lowest variance 0.017 across 6 CV runs, no architecture change). Full writeup:
`PROVISIONAL_FINAL_MODEL_SELECTION.md`.

## Gold-Test (Table 8)

150 items (131 UNSAFE, 7 SAFE, 12 UNCERTAIN — 8.0% exclusion). Provisional final model ranks
#1 by AUPRC (0.968, 95% CI [0.915, 0.999]) but its operating threshold (calibrated on a
~9-item Gold-Dev split) generalizes catastrophically to Gold-Test (recall 1.0, FPR 0.857 —
predicts nearly everything UNSAFE). `authguard_sequence_dense`: AUPRC 0.963 [0.928, 0.991],
recall 0.336, FPR 0.429. Source static rule: precision 0.978, recall 0.344, FPR 0.143 — the
best precision/FPR trade-off of any method compared, at the shared ~0.34 recall ceiling every
method in this comparison exhibits. All 5 models' 95% CIs overlap — the AUPRC ranking is not
statistically distinguishable at this sample size.

## Cascade (Table 10)

Escalation-band policy selected on Gold-Dev only, frozen, evaluated once on Gold-Test:
AuthGuard-first with rule-escalation for score-ambiguous items (37.0% of Gold-Test) recovers
the static rule's FPR (0.143 vs. AuthGuard-alone's 0.429) while resolving 63.0% of items from
the cheap AuthGuard score alone.

## Honest headline finding for this section

This pass's central, reportable methodological lesson is **not** "AuthGuard achieves AUPRC
X" — it is that a competitive AUPRC does not guarantee a usable operating threshold when
calibration data is scarce (47 items), and that this gap was only caught by evaluating end
to end (Gold-Dev calibration → frozen model → Gold-Test evaluation) rather than stopping at
the rank-based metric. This is exactly the kind of finding a "generate the full pipeline
before human labels arrive" exercise is supposed to surface early.
