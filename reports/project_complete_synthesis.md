# AuthGuard-7702 — Project Complete Synthesis

Sources of truth: frozen artifacts, result JSONs, `paired_results.csv`, figures, and
`paper/authguard7702.tex`. Where artifact and paper disagree, the artifact wins (noted inline).
Full number provenance in `result_reconciliation.md`.

## Phase 0 — Verification summary (gate; complete before narrative)

| Quantity | Value | Artifact |
|--|--|--|
| Total dataset | 3,258 | `capability_dataset.csv` |
| malicious | 793 | " |
| benign_cleared (weak neg.) | 1,657 | " |
| benign_general (closer-to-clean) | 800 | " |
| benign_AA (hand-verified) | 8 | " |
| Frozen families (all rows, sim 0.85) | 1,329 | `results/family_structure.json` |
| Singleton families | 912 (68.6%) | " |
| Largest family | 58 | " |
| Malicious-bearing families | 214 (178 pure-malicious) | `results/family_structure.md` |
| Malicious singletons | 113 (52.8% of malicious families) | " |
| **Clean family-grouped AUPRC (headline, G-DET)** | AuthGuard **0.856**±0.043; opcode-XGB 0.789; opcode-RF 0.775; selector-LR 0.519; name-rule 0.344; struct-rule 0.341; blocklist 0.324; oracle 1.000(tautological) | `results/detection_results.json` |
| Random-split AUPRC | AuthGuard 0.961; opcode-XGB 0.948; blocklist 0.558 | " |
| **Memorization gap** (AuthGuard) | 0.961 − 0.856 = **0.105** | derived from `detection_results.json` |
| Blocklist gap (clearest) | 0.558 − 0.324 = 0.234 | " |
| Mutation M0→M3 retained recall (G-MUT, in-sample thr) | name-rule 0.038→0.000; struct 1.000 flat; blocklist 0.000; opcode-XGB 0.656→0.518; AuthGuard 0.641→0.588 | `results/mutation_curve.json` |
| Original +200% (G-VOL, M3-base flood, in-sample thr) | AuthGuard **0.139**; opcode-XGB 0.485 | `results/mutation_volume.json` |
| Latest +200% (G-ADV, M0-base flood, val thr) | AuthGuard-M0 recall 0.624 / AUPRC 0.596; **AuthGuard-aug 0.790 / 0.750** | `advtrain_results.json` |
| AuthGuard-M0 vs aug clean (G-ADV) | AUPRC 0.830→0.849; recall 0.797→0.761; benign FPR 0.192→0.164 | " |
| opcode-XGB vs XGB-aug @+200% | recall 0.606→0.701; FPR 0.352→0.324; clean AUPRC 0.772→0.758 | " |
| Benign FPR @+200% | AuthGuard-M0 0.314 → aug 0.275 (still high) | " |
| Singleton-family recall @+200% (M0→aug) | 0.655→0.850 | `reports/advtrain_analysis.json` T7 |
| Family-macro recall @+200% (M0→aug) | 0.674→0.844 | " |
| Paired bootstrap Δrecall @+200% | +0.161, 95% CI [0.131, 0.193] | " T8 |
| Paired bootstrap Δrecall @M3 | +0.014, 95% CI [−0.009, 0.037] (n.s.) | " T8 |
| Measured runtime | 3.37 ms mean / 2.47 p50 / 10.67 p95 (300 timed) | `results/supporting.json` |
| Decompiler runtime | `[NOT MEASURED]` (no Gigahorse/Soufflé run) | phase-0 recon |
| Explanation audit | fired-signal coverage 1.00; NN-malicious rate 0.34 (0.65 at sim≥0.70) | `supporting.json` |
| Contamination (benign_cleared) | ≤8.1% same-family-as-malicious; 1.2% exact-dup | " |
| Independent truly-novel confirmed | **1** → INSUFFICIENT DATA | `reports/funnel.json` |

### Unresolved discrepancies (all reconciled in `result_reconciliation.md`, none open)
- 0.856 vs 0.830 → train-size (4 vs 3 fold), **not** threshold (AUPRC is threshold-free). R1/R6.
- 0.139 vs 0.624 → different condition (M3+flood vs M0+flood) **and** protocol. R3.
- 0.588 vs 0.787 (M3) → threshold-selection protocol + train size. R4.
- Compound M3+heavy-flood was **not** retested under augmentation. R5.

### Paper-vs-artifact conflicts to fix before submission
1. Abstract/§mutation says **"semantics-preserving"** — artifacts verify only opcode-skeleton /
   control-flow identity (`results/mutation_preservation.json`). Must become
   **"structure-preserving."** (Ground-rule 3 violation in current `.tex`.)
2. Abstract's "under heavy dead-code flooding the learned model degrades faster than a plain
   opcode histogram" predates the augmentation study; it is now **partially addressed**
   (aug recovers +200% recall to 0.790 > opcode-XGB-aug 0.701). Update.
3. `0xef0100\,\|\,address` renders as `0xef0100\textbackslash,\textbar{}address` in the current
   `.tex` (line 115) — a LaTeX-escaping artifact to fix.

## One-paragraph project status
The tool and all four experiment families (detection, mutation/evasion, adversarial-training,
independent validation) are implemented and reproducible with frozen seeds and leakage
assertions. The evidence supports three honestly-scoped contributions (pre-signing screen;
family-grouped leakage-resistant evaluation; evasion benchmark + augmentation robustness). The
main risks are label circularity (all positives rule-derived), weak negatives, and the fact that
independent prospective validation yielded only one confirmed novel delegate (INSUFFICIENT DATA).
No claim depends on running the full USENIX pipeline (not executed) or on decompiler timing
(not measured).
