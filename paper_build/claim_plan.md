# Claim Plan — Task-Aligned v1

## Claim discipline

The paper should claim an implemented bytecode-scoring prototype and a task-aligned, leakage-controlled evaluation—not a novel classifier, verified maliciousness oracle, or complete wallet product. Every classification result is scoped to USENIX-artifact positives versus rule-silent weak negatives. Original-cohort values are sensitivity evidence only.

Do not use “first,” “novel,” “state of the art,” “semantics-preserving,” “formally verified,” or “robust to arbitrary evasion.”

## Defensible contribution sentences

1. **Practical scorer.** We present AuthGuard-7702, an implemented bytecode-only, decompiler-free risk-scoring prototype for screening EIP-7702 delegate runtime code before authorization; it separates 727 USENIX-artifact positives from 1,553 rule-silent delegates at **0.881 ± 0.028 AUPRC** over five preserved family folds, while local feature extraction plus prediction averages **3.411 ms per contract** on an Apple M1.

2. **Task-aligned family evaluation.** We audit 76 delegation designators and 23 cross-class exact-bytecode conflicts, freeze an outcome-blind exclusion/recovery policy, and evaluate 3,082 task-aligned samples in 1,258 retained frozen families. AuthGuard reaches **0.975 AUPRC under a seeded random diagnostic versus 0.881 under family grouping**, and the exact-hash blocklist reaches 0.551 versus 0.321; family-grouped testing controls related-bytecode leakage and provides a more demanding generalization estimate.

3. **Evasion benchmark and augmentation.** We provide a checker-defined structure-preserving M0–M3 benchmark and source-balanced family-disjoint augmentation. Under G-ADV, augmentation changes held-out pure-M0 F200 fold-mean recall/AUPRC/FPR from **0.484/0.561/0.217 to 0.727/0.758/0.174**; the paired family-clustered pooled recall gain is **0.253 (95% CI [0.144, 0.379])**, with fold heterogeneity and residual false positives disclosed.

## Core claim matrix

| ID | Safe claim | Evidence | Required qualification | Planned location |
|---|---|---|---|---|
| C1 | AuthGuard is an implemented scorer for a pre-signing integration point | feature/model code; G-DET; runtime protocol | scorer core only; wallet/RPC/UI path not implemented or timed | design, RQ1, runtime |
| C2 | Task-aligned AuthGuard reaches .881 ± .028 family AUPRC | task-aligned G-DET | rule-derived positives vs weak negatives; five preserved outer folds | Table 2 |
| C3 | Random evaluation is more optimistic on this corpus | G-DET family/random outputs | AuthGuard gap .094; diagnostic, not a universal estimate | Figure 2 |
| C4 | Outcome-blind hygiene removes designator inputs and cross-class exact conflicts | protocol, designator audit, conflict audit, manifest | 176 exclusions; three recovered runtime rows retained; no relabeling/reclustering | dataset/Table 1 |
| C5 | Family grouping controls related-bytecode leakage | frozen IDs/folds; exact-hash assertions | similarity families are not attacker attribution; same-class duplicates remain within families | methodology |
| C6 | Sensitive selector rewriting reduces the name approximation's retained recall to zero | G-MUT | approximation only; full USENIX pipeline unexecuted | Table 3 |
| C7 | AuthGuard retains .530 recall at M3 | G-MUT | checker-defined structure preservation, not execution equivalence | Table 3 |
| C8 | Compound G-VOL F200 reduces AuthGuard recall to .130 | G-VOL | distinct from pure-M0 G-ADV F200; not recovered by tested augmentation | limitations |
| C9 | G-ADV augmentation improves aggregate F200 robustness | fold means, paired file, family bootstrap | distinguish fold means from pooled differences; effects heterogeneous; residual FPR .174 | Table 4/Figure 3 |
| C10 | Clean and M3 recall changes are uncertain under family resampling | family bootstrap | clean CI [-.045,.133]; M3 CI [-.040,.080] include zero | results/discussion |
| C11 | Local scorer-core mean is 3.411 ms, p95 9.514 ms | frozen runtime benchmark | Apple M1; preloaded bytecode; excludes network/wallet/model loading | runtime sentence |
| C12 | Independent generalization is unresolved | independent funnel | exactly one novel confirmed positive; insufficient for inference | limitations |

## Required terminology

Use exactly:

- **sensitive-name rule approximation**;
- **external-call structural over-approximation**;
- **full USENIX Gigahorse/Datalog pipeline**;
- **family-grouped testing controls related-bytecode leakage and provides a more demanding generalization estimate**;
- **structure-preserving transformations under our opcode-skeleton checker**.

Never label either approximation as the “USENIX detector,” and never claim AuthGuard beats the full pipeline.

## Statistical policy

- Main G-DET and G-ADV tables use five-fold means; report population SD only where specified.
- Paired pooled values must be labeled pooled and kept distinct from fold means.
- Inferential robustness claims use the 10,000-replicate family-clustered paired bootstrap.
- F200 supports aggregate improvement: recall +.253 [.144,.379], FPR -.049 [-.086,-.014], and AUPRC +.248 [.177,.322].
- Clean and M3 recall intervals include zero; do not claim statistically resolved recall gains for those conditions.
- The old contract-level interval is superseded and must not appear in the submission.

## Dataset and mutation policy

- State that the observation unit is chain/address and that 233 same-class exact groups covering 787 observations remain, controlled within frozen family folds.
- State that 115/1,553 weak negatives share a positive-bearing similarity family; call 7.4% a conservative malicious-like-family heuristic, not contamination truth.
- Report 32/76 runtimes recovered, 3 safely retained, 29 excluded as cross-family exact duplicates, 44 unresolved, and 73 total designator-source exclusions.
- Report complete quarantine of 23 conflicting hashes/103 rows and zero retained cross-class exact hashes.
- “727/727 variants preserved the original pre-metadata opcode-token sequence” is allowed only with the checker limitation.

## Runtime policy

Safe wording: “On an Apple M1 local evaluation environment, preloaded-bytecode feature extraction plus model prediction averaged 3.411 ms per contract (p95 9.514 ms; 3,000 single-contract calls); timed 300-contract batches averaged 3.197 ms per contract.”

Unsafe: “end-to-end wallet latency,” “network-inclusive latency,” “complete pre-signing latency,” “real-time” without a boundary, or a speedup against Gigahorse.

## Claims to omit

- AuthGuard discovers missed malicious families or generalizes independently at scale.
- `benign_cleared` is verified benign, or 7.4% is its true contamination rate.
- Family grouping “removes memorization” or proves attacker-level independence.
- Mutations are semantically or behaviorally equivalent.
- Augmentation recovered the G-VOL compound F200 result.
- Clean/M3 recall gains are statistically established.
- Robustness is complete; AuthGuard-aug still has .174 fold-mean FPR at F200.
- The estimator is a research novelty or the full USENIX pipeline was reproduced.
- A deployed wallet warning UI, production RPC/cache path, user study, or end-to-end benchmark exists.

## Exact abstract-safe numeric set

Use no more than three numeric result clauses:

- task-aligned G-DET family/random AuthGuard AUPRC: **.881 ± .028 / .975 ± .012**;
- G-ADV pure-M0 F200 fold-mean recall/AUPRC/FPR: **.484/.561/.217 → .727/.758/.174**;
- family-clustered F200 pooled recall difference: **+.253, 95% CI [.144,.379]**.

Latency may replace, not supplement, one of these clauses if the abstract becomes crowded. Always retain the rule-derived-label and scorer-boundary qualifications.

## Proposed title

**AuthGuard-7702: Task-Aligned, Family-Grouped Bytecode Risk Screening for EIP-7702 Delegation**
