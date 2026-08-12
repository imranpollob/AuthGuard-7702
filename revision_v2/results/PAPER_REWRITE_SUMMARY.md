# Paper rewrite summary — TPS 2026

Source: `revision_v2/paper_final/AuthGuard_7702_tps2026.tex`
Build: `revision_v2/paper_final/build_tps/AuthGuard_7702_tps2026.pdf` — 11 pages, 0 errors,
0 overfull boxes, 0 undefined references or citations.
Previous draft preserved at `AuthGuard_7702_tps2026.tex.prev`.
Numerical source of truth: `revision_v2/results/frozen_numbers.json`, `results/SUMMARY.md`.
Git commit `8ebce5f`.

Verification run before declaring completion: **47/47 headline numbers match the frozen
ledger exactly**, and **29/29 consistency checks pass**
(`revision_v2/experiments/sprint_phase6/audit_manuscript.py`).

---

## 1. New central claims

- Clean classification metrics cannot select a pre-authorization screener: a 15-feature
  logistic regression is statistically indistinguishable from the hierarchical attention
  model on clean bytecode ($\Delta$AUPRC $-0.021$, 95% CI $[-0.078,+0.035]$).
- The transformation space used for robustness claims is itself independently audited
  against a real EVM. Flooding, metadata rewrite, and neutral insertion preserve externally
  visible behaviour on **all 5,196 audited executions across 120 distinct bytecode
  families**, with no observed failure. Address and selector rewriting are *not* promoted.
- **Headline.** Under the audit-supported compositional adversary (Tier B), the
  clean-equivalent emulator suffers **+0.370** higher attack success than AuthGuard-Seq,
  95% CI **[+0.208, +0.520]**, across three seeds.
- End-to-end **robust recall is 0.679 vs 0.378** under the same adversary.
- Widening to the weaker-evidence action space (Tier C) adds little: only **12.0%** and
  **13.3%** of Tier-C successes for AuthGuard-Seq and the emulator are unreachable within
  Tier B at the same 64-query budget. The separation does not rest on transformations whose
  behaviour we cannot vouch for.
- Fixed perturbation testing **materially underestimates** the gap adaptive composition
  exposes (fixed flooding oracle $+0.184$ vs audited adaptive $+0.370$). The old categorical
  claim that fixed transformations *cannot rank* models has been removed as indefensible.
- Selective aggregation, not capacity, is the associated mechanism: parameter-matched
  controls plus direct attention-mass measurement (37.6% of mass on appended chunks where
  uniform weighting would place 63.1%).
- No architectural novelty is claimed.

## 2. Headline numbers

Every value below is quoted from `frozen_numbers.json` and was re-verified against it.

| Value | Number | Denominator / population | Marginal or paired | Seed scope | Frozen source |
|---|---|---|---|---|---|
| Tier B paired difference | +0.3699, CI [+0.2079, +0.5195] | 1,503 paired obs., 209 families | **paired** | 7702/03/04 | `regenerated_experiment.phase4_analysis.paired_contrasts[B]` |
| Tier A paired difference | +0.2083, CI [+0.0757, +0.3342] | 1,503 paired obs. | **paired** | 7702/03/04 | same, tier A |
| Tier C paired difference | +0.3826, CI [+0.2226, +0.5237] | 1,503 paired obs. | **paired** | 7702/03/04 | same, tier C |
| AuthGuard-Seq Tier B ASR | .1970, CI [.1476, .2562] | 1,843 eligible of 2,181 obs. | marginal | 7702/03/04 | `phase4_analysis.tier_table` |
| Emulator Tier B ASR | .5417, CI [.4269, .6454] | 1,800 eligible of 2,181 obs. | marginal | 7702/03/04 | same |
| Flat CNN Tier B ASR | .9356, CI [.8934, .9720] | 497 eligible of 727 obs. | marginal | **7702 only** | same |
| XGBoost Tier B ASR | .9844, CI [.9674, .9973] | 450 eligible of 727 obs. | marginal | **7702 only** | same |
| Robust recall Tier B | .6786 / .3783 / .0440 / .0096 | all positive obs. (2,181 / 2,181 / 727 / 727) | direct source-level | 3 / 3 / 1 / 1 | same |
| Tier-C-only fraction | 46/384 = .1198; 137/1030 = .1330 | Tier-C successes | — | 7702/03/04 | `phase4_analysis.tier_c_only` |
| Flooding preservation | 3,464/3,464, Wilson [0.9989, 1.0] | 120 families | — | n/a | `phase2_preservation_audit` |
| Metadata preservation | 866/866, Wilson [0.9956, 1.0] | 120 families | — | n/a | same |
| Neutral preservation | 866/866, Wilson [0.9956, 1.0] | 120 families | — | n/a | same |
| Fixed flooding oracle paired | +0.1839, CI [+0.0348, +0.3300] | 1,512 paired obs. | **paired** | 7702/03/04 | `stored_artifact.phase0_paired_ladder` |
| Flood-200-only paired | +0.0820, CI [−0.0466, +0.2181] | 1,512 paired obs. | **paired** | 7702/03/04 | same |
| Clean tie (emulator) | −0.021, CI [−0.078, +0.035] | 790 families | **paired** | 7702/03/04 | Gate 0A |
| Replication max delta | 0.011; deterministic models Δ=0.0000 | all models/metrics | — | 7702 | `regenerated_vs_historical_s7702.csv` |
| Augmentation contrast | −0.1332, CI [−0.1939, −0.0864] | 593 shared obs. | **paired** | **7702 only** | `phase1_seed_scope` |
| Byte budget (F200) | median 2.962, p95 2.986, max 3.001 | n = 13,086 | — | 7702/03/04 | `phase1_facts.byte_budget` |

**Populations that must never be merged.** `stored_artifact` values were recomputed from the
historical attack records whose models no longer exist; `regenerated_experiment` values come
from the Phase 3 frozen checkpoints. Both appear in the paper and are attributed in text
(Section on frozen models and replication); they are never averaged.

## 3. Structural changes

**Added**
- §III-D "Attack Tiers and Their Evidentiary Status" — defines Tier A/B/C by strength of
  behavioural evidence, in the threat model, before any result.
- §V-C "Frozen Models and Replication" — one paragraph, keeps the replication result out of
  the results narrative.
- §VI-B-1 "Execution-preservation audit" + Table \ref{tab:preservation} — placed *inside*
  the central evaluation section, not in Limitations.
- Table \ref{tab:tiers} (marginal ASR + robust recall by tier) and Table \ref{tab:central}
  (paired contrast), deliberately separated so the two statistics cannot be conflated.
- §VI-C RQ3 "What the Broader Action Space Adds" — Tier-C-only analysis.
- §VIII AI Disclosure.
- Methods paragraph defining marginal vs paired statistics.

**Restructured**
- Evaluation moved from four RQs to five, reorganised so RQ2 (audited adversary) is the
  centre of gravity. Mechanism evidence moved from RQ1 to RQ4; operational evidence to RQ5.
- Abstract and Introduction rewritten around the audited Tier-B result. Contributions went
  from three to four, led by the methodology + preservation-audit pairing.
- Related work restructured to acknowledge that robustness-aware contract classifiers exist,
  and to state the distinction narrowly.

**Replaced**
- Old Table V (single ASR table mixing seed scopes) → Tables \ref{tab:tiers} and
  \ref{tab:central}, each with explicit scope labelling.
- Old "fixed transformations cannot rank" subsection → "Adaptive composition versus fixed
  perturbation" with the quantified two-fold understatement.

**Removed**
- The clean-vs-ASR dumbbell figure (superseded by the tier tables; the generator and PDF are
  retained for the compression pass).
- The old Tier-C-centred headline framing throughout.

**Retained**
- Attention-dilution figure and parameter-matched ablation (now RQ4), temporal population
  and cost analysis (now RQ5), benchmark construction and family protocol.

## 4. Corrected factual errors

| Error in previous draft | Correction |
|---|---|
| "8 audited implementations" listed as a benchmark population | Benchmark contains **5** `QUALITATIVE_CONTROL` rows. Total 3,082 = 2,190 + 797 + 5 + 90. The 8-project registry (45 rows, 30 unique bytecodes) is now shown as a **separate resource**, explicitly excluded from the total. |
| Live holdout described as family-disjoint | **70 of 752 (9.3%)** live delegates reach the 0.85 family threshold. Now "independently collected later temporal population with explicit family-overlap auditing"; leakage-clean denominator 682 reported alongside. Exact-hash overlap 0 is stated but no longer presented as sufficient. |
| "Edits are capped at 2× the original executable size" | **Appended content** ≤ 2× original, so final size ≤ approximately **3×**. Empirical F200 ratio median 2.962, p95 2.986, max 3.001, n = 13,086. |
| Table juxtaposed 3-seed marginal .181, 1-seed marginal .062, and paired −.133 | Augmentation contrast now states its 593-observation shared population, is labelled seed 7702 only, and the text explicitly says the contrast is *not* obtained by subtracting the marginal values. Seed-7702 AuthGuard reference values (clean .8404, F200 .1326, beam .1522, random .1882) are used for the like-for-like comparison. |
| "Fixed transformations cannot rank these models" | Removed. A fixed flooding oracle *does* separate them (+0.184, CI [+0.035, +0.330]); a single Flood-200% does not (+0.082, CI spans zero). Replaced with the accurate and stronger claim that fixed testing **materially underestimates** the gap. |
| "deployed model" for the 63,266-parameter configuration | "reference AuthGuard-Seq configuration". |
| "length-invariant attention" | "length-robust selective aggregation". |
| Implied uniform three-seed replication | Table caption states seed scope differs by model; Limitations names the single-seed rows. |

## 5. Related-work changes

Positioning rewritten after reading the three works.

- **FinDet** (Liu et al., arXiv 2509.18934) is the closest neighbour: bytecode-only,
  pre-deployment, robustness-oriented, real-world validated. It made the previous blanket
  claim that prior work reports only clean metrics **untenable**, and that sentence was
  removed. Distinction drawn on *task* (it detects exploiter contracts attacking other
  contracts; we screen a delegate for the authority it would gain over a user's account) and
  on *adversary* (it reports robustness to unseen attack patterns and feature obfuscation,
  not a score-aware attacker querying the model).
- **ContractShield** (Tran-Duong et al., arXiv 2604.02771) evaluates multi-label
  vulnerability detection under obfuscation applied at source and bytecode level. Distinction
  on *inputs* — it consumes source code alongside opcode and CFG modalities, which the
  pre-authorization setting does not supply — and on the obfuscation being a predefined set.
- **ORACAL** (Tran Duong et al., arXiv 2603.28128) reports ASR 3% under adversarial attack
  using CFG/DFG/CG graph inputs. Distinction on inputs and on the adversary being predefined
  rather than score-aware.

Net effect: the novelty claim narrowed from "first adversarial evaluation" (which would have
been false) to a query-budgeted **score-aware** adversary over an **independently
execution-audited** transformation space, applied to the EIP-7702 pre-authorization decision.
Table \ref{tab:related} gained "adaptive attacker" (fixed vs score-aware) and "preservation
audited" columns. Statements about what these systems do *not* do are hedged with "to our
knowledge" and "do not report", since they are based on abstracts and available summaries.

## 6. Remaining weaknesses

Genuine, reviewer-facing, after the rewrite:

1. **Label provenance.** Reference labels remain a decompiler-derived structural condition,
   not adjudicated maliciousness. The relative framing reduces dependence but does not
   remove it; clean numbers still inherit the rule's definition.
2. **Preservation is empirical, not proof.** 5,196 executions over a finite calldata suite.
   Strong, but not semantic equivalence.
3. **Residual evadability.** AuthGuard-Seq's Tier-B ASR of 0.197 means roughly one in five
   detected risky delegates is still evadable inside our own threat model.
4. **Threat model is not white-box.** A wallet-side deployment implies an adversary with the
   weights; results are lower bounds for that case.
5. **Uneven replication depth.** The central comparison has three seeds; Flat CNN, XGBoost,
   the augmentation block, and the parameter-matched block are seed 7702 only.
6. **Live holdout is unlabeled** and carries 9.3% measured family overlap; its flag rate is
   not an FPR and cannot be decomposed.
7. **Family threshold is a design choice.** 43.6% of test rows fall in the 0.7–0.9 similarity
   band, so near-duplicate structure crosses folds below the 0.85 threshold.
8. **Production controls are effectively n=5** after excluding the three registry projects
   that overlap training families.
9. **Page length.** 11 pages against a 10-page limit; compression pass still required.


---

## 7. Post-review corrections (second pass)

Applied after reviewer inspection of the first rewrite. Build re-verified: 11 pages,
0 errors, 0 overfull boxes, 0 undefined references. Audits re-run: 29/29 original checks
plus 18/18 new checks, and the new matched-capacity table verified against frozen data.

| # | Issue | Correction |
|---|---|---|
| 1 | Abstract said "181k-token hierarchical attention model" — conflated the discredited inflated parameter count with token capacity | Now "63K-parameter hierarchical attention model" |
| 2 | Discussion claimed robust evaluation "selects a different model than clean AUPRC" — **false**: AuthGuard-Seq leads on both clean AUPRC (.924) and robust recall | Replaced with the correct and stronger claim: clean AUPRC does not *statistically distinguish* AuthGuard-Seq from the emulator, whereas audited adaptive evaluation separates them by a large supported margin. Clean metrics leave the choice underdetermined; the audited criterion resolves it |
| 3 | Abstract said 12–13% of Tier-C successes were "unreachable" within Tier B — stronger than the evidence | Now "not also reproduced within the audited space at the same 64-query budget", matching the precise formulation already used in RQ3 |
| 4 | RQ3 compared the *historical* fixed oracle (+.184) against the *regenerated* Tier-B gap (+.370), mixing populations | Now leads with the within-experiment comparison from Table VI: Tier A +.2083 → Tier B +.3699, same frozen checkpoints, same paired population, same bootstrap. Historical Flood-200-only (+.082, CI spans zero) retained as supporting evidence at the weaker end |
| 5 | Mechanism claim rested on flooding-only ablation plus attention mass | Restored the matched-capacity **adaptive** result as Table VII: at ~30K parameters and identical token budget, attention .0747 vs flat .8891 vs mean .9857 random-search ASR; paired +0.710 and +0.838 against the reference configuration. Capacity held fixed, so the separation is attributable to the aggregation rule. Labelled stored-artifact, seed 7702, not pooled with the regenerated tiers |
| 6 | "clean-equivalent emulator" implied a formal equivalence test | Replaced globally with "clean-indistinguishable emulator" (evidence is a non-significant difference, CI spanning zero, not an equivalence test with a prespecified margin) |
| 7 | §IV claimed three design requirements "each tested" | Now three design *hypotheses*, with explicit statement that hypothesis 3 (selective aggregation) has the strongest direct support, hypothesis 1 (coverage) is **not established**, and hypothesis 2 (order sensitivity) is supported only indirectly and not isolated by a dedicated control |
| 8 | AI disclosure was generic and understated the role | Now names the tool (Anthropic Claude via Claude Code), enumerates materially influenced parts across implementation, analysis, **methodology**, and writing, cross-references the body sections where the AI-influenced methodology appears, and states verification boundaries |
| w1 | Title | "Pre-Authorization Screening of EIP-7702 Delegates under an Execution-Audited Adaptive Adversary" — "pre-authorization" is the clearest distinction from FinDet and conventional vulnerability detection |
| w2 | "Robust recall is the number a deployment cares about" | "a deployment-relevant end-to-end metric", noting precision, calibration, alert volume, and latency remain separately relevant |
| w3 | "a newly encountered delegate is a cache miss by construction" | "a delegate not previously seen by the screening service is a cache miss" |

**Net effect on claims.** Items 2, 4, and 5 each *strengthen* the paper: item 2 replaces a
false claim with a defensible and sharper one; item 4 removes cross-population mixing from
the central methodological argument; item 5 extends the mechanism evidence from flooding to
the adaptive adversary at matched capacity. Items 1, 3, 6, and 7 remove overstatements.

**Page structure.** The conclusion ends on page 10 with the bibliography running onto page 11,
which is compatible with a 10-page limit that excludes references. A compression pass is
still advisable but may no longer be strictly required.
