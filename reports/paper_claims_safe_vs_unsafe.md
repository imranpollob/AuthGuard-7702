# Safe vs Unsafe Claims Matrix

| Proposed claim | Evidence | Qualification | SAFE wording | UNSAFE wording | Reviewer risk if unsafe |
|--|--|--|--|--|--|
| Pre-signing detection accuracy | AUPRC 0.856 LFO (`detection_results.json`) | rule-labeled vs rule-silent | "separates rule-labeled malicious from rule-silent delegates at 0.856 AUPRC under family holdout" | "detects malicious EIP-7702 delegates at 0.86 AUPRC" | circular-label rejection |
| Speed | 3.4 ms (`supporting.json`) | excludes network fetch | "scores a contract in ~3.4 ms with no decompiler" | "orders of magnitude faster than decompiler analysis" | unmeasured-baseline (O2) |
| Random-split inflation | 0.856→0.961 | threshold 0.85 | "random splits inflate AUPRC by ~0.10; leave-family-out is materially harder" | "prior evaluations are invalid" | overreach; unverified |
| Rule brittleness | name-rule 0.038→0.000 at M3 | reimplemented facts | "the deployed rule's shipped name-match and hashing collapse under a rename" | "the USENIX detector cannot catch mutated delegates" | full-pipeline-not-run (O2) — **must avoid** |
| Mutation validity | 793/793 skeleton preserved | not EVM-executed | "structure-preserving / attack-capability-preserving mutations" | "semantics-preserving mutations" | equivalence-overclaim — **must avoid** |
| Augmentation recovery | +200% 0.624→0.790, CI [0.131,0.193] | held-out severity; pure-M0 | "augmentation significantly improves robustness to a held-out flooding severity" | "augmentation makes AuthGuard robust to evasion" | compound case untested; O3 |
| Recovered the 0.139 collapse | — | different condition (R3/R5) | "the compound M3+heavy-flood worst case is left for future work" | "augmentation recovers the heavy-flooding collapse" | reconciliation error — **must avoid** |
| No shortcut | aug FPR<M0 all severities | residual FPR high | "no padding shortcut; benign FPR falls rather than rises" | "immune to padding attacks" | residual 27.5% FP (O3) |
| Clean cost | AUPRC 0.830→0.849 | small recall dip | "no clean-data cost (AUPRC rises, FPR falls)" | "augmentation is strictly better" | recall dip is significant |
| Independent validation | 1 novel (`funnel.json`) | INSUFFICIENT DATA | "independent sourcing yielded one confirmed novel delegate — insufficient for quantitative validation" | "AuthGuard generalizes to independently-sourced malware" | fabrication-adjacent — **must avoid** |
| Novelty of setting | no prior pre-signing EIP-7702 tool found | PROVISIONAL | "to our knowledge, the first pre-signing screen for this surface" | "no prior work exists" | unverifiable absolute |
| Explanations | coverage 1.0, NN-mal 0.34 | modest | "a lightweight nearest-family/fired-signal explanation, audited on 50 cases" | "interpretable detections users can trust" | over-reads a 0.34 hit rate |
| Full-pipeline superiority | not run | — | (omit) | "we outperform the USENIX pipeline" | **must avoid entirely** |
| Decompiler speedup | not measured | — | (omit / deployment concern) | "N× faster than Gigahorse" | **must avoid entirely** |

**Must-avoid list (hard):** "semantics-preserving"; "beats/outperforms the USENIX detector/pipeline";
"recovers the heavy-flooding collapse"; "generalizes to independent malware"; "N× faster than a
decompiler"; "no prior work exists"; "robust to evasion/adversaries" (unscoped).
