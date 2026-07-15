# Evaluation Inventory (Paper §7) — by Research Question

Every value traced to an artifact; protocol group (G-DET/G-MUT/G-VOL/G-ADV) noted so
incompatible numbers are never mixed. See `result_reconciliation.md`.

## RQ1 — Family-held-out detection accuracy
- **Subset:** malicious 793 vs benign_cleared 1,657. **Split:** leave-family-out. **Fold:** GroupKFold(5) on frozen `family_id`, train=4 folds. **Threshold:** in-sample max-F1. **Metrics:** AUPRC(primary),AUROC,P,R,F1. **Group:** G-DET. **Artifact:** `detection_results.json`.
- **Results (mean±std):** AuthGuard AUPRC **0.856±0.043**, AUROC 0.930, P 0.871, R 0.641; opcode-XGB 0.789±0.060; opcode-RF 0.775±0.076; selector-LR 0.519; name-rule 0.344; struct-rule 0.341; blocklist 0.324; oracle 1.000 (tautological).
- **Interpretation:** learned bytecode model clearly beats rules/blocklist under holdout. **Limitation:** weak negatives; positives rule-derived; secondary task (add benign_general) raises AuthGuard to 0.877.

## RQ2 — Random-split inflation
- **Split:** random 5-fold vs family. **Group:** G-DET. **Artifact:** `detection_results.json`.
- **Results:** AuthGuard 0.961 (random) vs 0.856 (family) → **gap 0.105**; opcode-XGB 0.948 vs 0.789; **blocklist 0.558 vs 0.324** (gap 0.234, the clearest memorization signature; recall 0.000 under holdout).
- **Interpretation:** random splits scatter near-duplicates across train/test, inflating all learned methods and rescuing the blocklist. **Limitation:** magnitude depends on family threshold (0.85); reported for 0.75/0.90 too.

## RQ3 — Robustness to structure-preserving mutation (M0–M3)
- **Subset:** held-out malicious mutants (split-before-mutate). **Group:** G-MUT (in-sample threshold). **Artifact:** `mutation_curve.json`; preservation `mutation_preservation.json` (793/793 opcode-skeleton preserved).
- **Results (retained recall M0→M3):** name-rule 0.038→**0.000** (rename defeats it); struct-rule 1.000 flat but non-discriminative; blocklist 0.000 throughout; opcode-XGB 0.656→0.518; **AuthGuard 0.641→0.588**.
- **Interpretation:** the rule's precision-bearing name-match and exact-hash blocklisting collapse; the learned model degrades gracefully on M1–M3. **Limitation:** "structure-preserving," not EVM-execution-verified; these are absolute recalls at an in-sample threshold (not comparable to G-ADV).

## RQ4 — Does augmentation improve held-out conditions/severities?
- **Subset:** mutated mal+benign test. **Split:** LFO, 3-fold train-fit + val. **Threshold:** held-out clean-M0 val max-F1, frozen across conditions. **Group:** G-ADV. **Artifacts:** `advtrain_results.json`, `advtrain_analysis.json`; leakage log `advtrain_leakage_assertions.txt` (all pass).
- **Results:** held-out **+200% recall 0.624→0.790** (paired Δ+0.161, 95% CI **[0.131,0.193]**), AUPRC 0.596→0.750; **singleton-family recall 0.655→0.850**, family-macro 0.674→0.844; held-out **M3 recall 0.787→0.801** (Δ+0.014, CI [−0.009,0.037], **n.s.**), AUPRC 0.754→0.814. AuthGuard-aug > opcode-XGB-aug at +200% (0.790 vs 0.701).
- **Interpretation:** significant, family-generalizing recovery on held-out flooding *severity*; M3 recall gain not significant (but AUPRC/FPR improve). **Limitation:** compound M3+heavy-flood not tested (R5); flooding axis pure-M0.

## RQ5 — Clean cost & padded-benign false positives (shortcut check)
- **Group:** G-ADV. **Artifacts:** `advtrain_results.json`, `advtrain_analysis.json` (T6/T7), `fig_advtrain_scoredist.png`.
- **Results:** clean AUPRC 0.830→0.849 (+0.019), clean recall 0.797→0.761 (paired CI [−0.053,−0.009]), clean benign FPR 0.192→0.164. **No shortcut:** aug benign FPR below M0 at every severity (M0 0.189→…→0.313; aug 0.158→…→0.266). **Residual:** aug +200% benign FPR **0.275** (high; rises with padding).
- **Interpretation:** no clean-data cost (mild net gain), no padding shortcut, but robustness improved-not-achieved. **Limitation:** absolute FPR inflated by max-F1 threshold and weak-negative contamination.

## RQ6 — Latency
- **Group:** measured, 300 sampled. **Artifact:** `supporting.json`.
- **Results:** 3.37 ms mean, 2.47 ms p50, 10.67 ms p95, 3.18 ms batched, no decompiler.
- **Interpretation:** compatible with pre-signing interactive use. **Limitation:** single machine; excludes `eth_getCode` network fetch; decompiler runtime `[NOT MEASURED]` so no "N× faster" claim.

## Supporting (not an RQ)
- Contamination ≤8.1% same-family-as-malicious (1.2% exact-dup) in benign_cleared (`supporting.json`).
- Explanation audit: fired-signal coverage 1.00; NN-malicious 0.34 overall / 0.65 at sim≥0.70 (`supporting.json`) — modest; supporting only.
- Independent validation: 1 truly-novel confirmed → **INSUFFICIENT DATA** (`funnel.json`); not a superiority claim.
