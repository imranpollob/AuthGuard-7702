# Final Three Contributions (Paper §5)

Selected from completed evidence. The independent malicious-set experiment is **excluded**
(INSUFFICIENT DATA, N=1). Verified that these three are the strongest supported claims.

---

## C1 — Pre-signing, decompiler-free AI screen
**Contribution sentence.** We present AuthGuard-7702, the first pre-signing, bytecode-only,
decompiler-free risk screen for EIP-7702 delegate contracts, which under leave-family-out
evaluation attains 0.856 AUPRC while scoring a contract in 3.4 ms.
- **Evidence:** AUPRC 0.856±0.043, AUROC 0.930, precision 0.871 (`detection_results.json`, G-DET); latency 3.37 ms mean / 10.67 ms p95 (`supporting.json`).
- **Research question:** RQ1 (family-held-out accuracy), RQ6 (latency).
- **Figure/table:** Table 2 (main performance), Table 6 (runtime), Fig. `fig_auprc.png`.
- **Qualification:** positives are rule-derived; negatives are weak (`benign_cleared` ≤8.1% contaminated). Claim is "separates rule-labeled malicious from rule-silent contracts," not "detects all malicious delegates."
- **Safe wording:** "a decompiler-free pre-signing screen that separates rule-labeled malicious from rule-silent delegates at 0.856 AUPRC under family holdout."
- **Unsafe wording:** "detects malicious EIP-7702 delegates with 0.86 AUPRC" (overstates label scope).
- **Reviewer objection:** circular labels — the model may re-learn the rule. **Rebuttal:** the name-rule footprint fires on ~4% of held-out positives, and at M3 that footprint is removed yet AuthGuard retains detection, so 0.856 is not the rule in disguise (`mutation_curve.json`).

## C2 — Family-grouped leakage-resistant evaluation
**Contribution sentence.** We freeze a deterministic, global family clustering of all 3,258
contracts and show that random splits inflate AUPRC by ~0.10 absolute, establishing
leave-family-out as the necessary protocol for this surface.
- **Evidence:** AuthGuard 0.856 (family) vs 0.961 (random), gap 0.105; blocklist 0.324 vs 0.558, gap 0.234 (`detection_results.json`). Family structure: 1,329 families, 68.6% singletons, largest 58 (`family_structure.json`).
- **Research question:** RQ2 (inflation magnitude).
- **Figure/table:** Table 3 (random vs family), Fig. `fig_random_vs_family.png`, Fig. `fig_family_size.png`.
- **Qualification:** clustering threshold 0.85 (sensitivity 0.75/0.90 reported); families are opcode-similarity clusters, not provenance-verified attacker groups.
- **Safe wording:** "random splits inflate AUPRC by ~0.10; the blocklist inflates from useless to deceptively strong."
- **Unsafe wording:** "prior work is invalid" (we did not re-run prior work).
- **Reviewer objection:** family clustering is arbitrary. **Rebuttal:** deterministic (byte-identical across `PYTHONHASHSEED`), sensitivity-tested at three thresholds, and leakage-safe (identical bytecode → one family; verified by the blocklist's collapse under holdout).

## C3 — Evasion benchmark + leakage-safe augmentation robustness
**Contribution sentence.** We build a verified structure-preserving mutation benchmark (M0–M3
plus dead-code flooding) and a source-balanced, leakage-safe augmentation protocol that
significantly improves robustness to a held-out +200% flooding severity (AuthGuard recall
0.624→0.790, ΔCI [0.131,0.193]) without a clean-data cost and without a padding shortcut.
- **Evidence:** rule brittleness — name-rule 0.038→0.000 at M3 (`mutation_curve.json`); augmentation — clean AUPRC 0.830→0.849, +200% recall 0.624→0.790 / AUPRC 0.596→0.750, benign FPR 0.314→0.275, singleton recall 0.655→0.850, paired ΔCI [0.131,0.193] (`advtrain_results.json`, `advtrain_analysis.json`); no shortcut — aug benign FPR below M0 at every severity; representation matters — aug beats opcode-XGB-aug at +200% (0.790 vs 0.701).
- **Research question:** RQ3 (mutation robustness), RQ4 (augmentation generalization), RQ5 (clean/FP cost).
- **Figure/table:** Table 4 (M0–M3), Table 5 (adversarial training), Figs. `fig_mutation_curve.png`, `fig_advtrain_heldout.png`, `fig_advtrain_scoredist.png`.
- **Qualification (critical):** verdict is PARTIALLY RECOVERS — residual 27.5% benign flag rate at +200%, and the flooding axis is pure-M0, so the paper's worst-case compound M3+heavy-flood (0.139) was **not** retested. "Structure-preserving," not "semantics-preserving."
- **Safe wording:** "augmentation partially recovers robustness to a held-out flooding severity without clean cost or padding shortcut."
- **Unsafe wording:** "augmentation makes AuthGuard robust to evasion" (overclaims; compound worst case untested, FP still high).
- **Reviewer objection:** mutations may not preserve behavior; recovery is on a milder condition. **Rebuttal:** opcode-skeleton/control-flow identity verified for all 793 (`mutation_preservation.json`); we explicitly scope recovery to the held-out severity/condition and disclose the untested compound case.

---

## Are these the strongest three? — Yes.
Candidate alternatives rejected: (a) capability-surrogate — abandoned, positives-only, not
built; (b) signer-context relational scoring — synthetic only, no victim data; (c)
independent-set superiority — INSUFFICIENT DATA (N=1); (d) explanation layer — modest
(NN-malicious 0.34), better as a supporting analysis than a headline. C1–C3 are the only
claims with paired, leakage-safe, reproduced evidence.
