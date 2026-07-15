# Claim → Artifact Map

Every paper claim traced to a file, field, result, and qualification. Literature-status tags:
LITERATURE-VERIFIED / EXPERIMENT-SUPPORTED / PROVISIONAL / NOT SUPPORTED.

| # | Claim | Artifact | Field/Table | Result | Qualification | Status |
|--|--|--|--|--|--|--|
| 1 | Pre-signing bytecode-only screen, 0.856 AUPRC LFO | `detection_results.json` | primary/leave_family_out/authguard | 0.856±0.043 | label scope = rule-labeled vs rule-silent | EXPERIMENT-SUPPORTED |
| 2 | 3.4 ms/contract, no decompiler | `supporting.json` | latency | 3.37 ms mean/10.67 p95 | excludes network fetch; 1 machine | EXPERIMENT-SUPPORTED |
| 3 | Random splits inflate ~0.10 AUPRC | `detection_results.json` | random vs LFO/authguard | 0.961 vs 0.856 (gap 0.105) | threshold 0.85 dependent | EXPERIMENT-SUPPORTED |
| 4 | Blocklist memorization | same | blocklist random/LFO | 0.558 vs 0.324; recall 0 LFO | — | EXPERIMENT-SUPPORTED |
| 5 | 1,329 families, 68.6% singletons, largest 58 | `family_structure.json` | 0.85 | as stated | opcode-similarity clusters | EXPERIMENT-SUPPORTED |
| 6 | Malicious pop: 214 families, 52.8% singletons | `family_structure.md` | malicious section | as stated | — | EXPERIMENT-SUPPORTED |
| 7 | Name-match trivially evaded (→0 at M3) | `mutation_curve.json` | usenix_name_rule/M3 | 0.038→0.000 | structure-preserving; in-sample thr | EXPERIMENT-SUPPORTED |
| 8 | Structural over-approx robust but non-discriminative | `mutation_curve.json` + `independent_detection.json` | struct rule | 1.000 flat; 88–92% benign flag | — | EXPERIMENT-SUPPORTED |
| 9 | Learned model degrades gracefully M0–M3 | `mutation_curve.json` | authguard | 0.641→0.588 | in-sample thr (G-MUT) | EXPERIMENT-SUPPORTED |
| 10 | Preservation verified 793/793 | `mutation_preservation.json` | — | 793/793 opcode-skeleton | not EVM-execution-verified | EXPERIMENT-SUPPORTED |
| 11 | Original heavy-flood weakness (M0) | `mutation_volume.json` | authguard/2.0 | 0.139 (M3-base +200%) | compound condition (G-VOL) | EXPERIMENT-SUPPORTED |
| 12 | Augmentation recovers +200% (pure-M0) | `advtrain_results.json` | AuthGuard-M0/-aug F200 recall | 0.624→0.790 | held-out severity; G-ADV | EXPERIMENT-SUPPORTED |
| 13 | Paired Δrecall +200% CI excludes 0 | `advtrain_analysis.json` | T8/F200 | +0.161 [0.131,0.193] | paired bootstrap | EXPERIMENT-SUPPORTED |
| 14 | No clean cost (AUPRC ↑, FPR ↓) | `advtrain_results.json` | M0 AUPRC/FPR | 0.830→0.849; 0.192→0.164 | small clean-recall dip −0.032 | EXPERIMENT-SUPPORTED |
| 15 | No padding shortcut | `advtrain_analysis.json` | T6 benign_flag_rate | aug < M0 every severity | residual FPR rises with pad | EXPERIMENT-SUPPORTED |
| 16 | Recovery generalizes to singletons | `advtrain_analysis.json` | T7/F200 | singleton 0.655→0.850 | — | EXPERIMENT-SUPPORTED |
| 17 | Residual 27.5% benign FP @+200% | `advtrain_results.json` | AuthGuard-aug/F200/FPR | 0.275 | weak-negative + threshold | EXPERIMENT-SUPPORTED |
| 18 | Representation > padding exposure | `advtrain_results.json` | F200 recall aug vs XGB-aug | 0.790 vs 0.701 | — | EXPERIMENT-SUPPORTED |
| 19 | benign_cleared ≤8.1% contaminated | `supporting.json` | contamination | 135/1657; 1.2% exact | upper bound | EXPERIMENT-SUPPORTED |
| 20 | Explanation audit modest | `supporting.json` | explanation | coverage 1.0; NN-mal 0.34 | supporting only | EXPERIMENT-SUPPORTED |
| 21 | Independent validation | `funnel.json` | funnel | 1 truly-novel confirmed | INSUFFICIENT DATA | EXPERIMENT-SUPPORTED (as negative) |
| 22 | "First pre-signing tool for this surface" | — | — | — | no prior pre-signing EIP-7702 tool found in reviewed lit | PROVISIONAL |
| 23 | Full USENIX pipeline comparison | — | — | — | NOT run | NOT SUPPORTED (must not claim) |
| 24 | Decompiler runtime speedup | — | — | `[NOT MEASURED]` | deployment concern only | NOT SUPPORTED (must not claim) |
| 25 | Robustness to arbitrary evasion | — | — | only tested transform family | scope to tested mutations | NOT SUPPORTED (must not claim) |
