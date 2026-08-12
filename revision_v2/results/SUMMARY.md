# AuthGuard-7702 final sprint — results summary

Git commit `8ebce5f`, branch `review1`. Frozen-artifact guard green (144 files) before and
after every run. Full machine-readable values in `results/frozen_numbers.json`, which keeps
**stored_artifact** and **regenerated_experiment** in separate top-level blocks that are
never averaged together.

---

# Paper-impact summary

The sprint set out to test whether AuthGuard-Seq stays substantially more robust than the
clean-equivalent emulator once the attacker is confined to transformations with empirical
execution-preservation support. It does, and the evidence is now stronger than the
manuscript currently claims. The expanded preservation audit upgraded Tier B from a
speculative tier to an **audit-supported compositional attack space**: flooding, metadata
rewrite, and neutral insertion each preserved externally visible behaviour on 100% of
several hundred to several thousand real-EVM calls across 120 distinct bytecode families.
Under that audited action space, adaptive search still separates the two clean-equivalent
screeners by **+0.370 ASR (95% CI [+0.208, +0.520])** across three seeds, and end-to-end
robust recall is **0.679 versus 0.378**. The headline result should therefore move from the
full eight-primitive space to Tier B, because it is both better evidenced and nearly as
large. Two secondary results deserve promotion: robust recall is a far more legible
deployment number than ASR and now exists for every configuration, and the weak-preservation
primitives turn out to buy the attacker very little (1–13% of Tier-C successes are
unreachable within Tier B at the same budget), which defuses the obvious objection that the
robustness claim rests on transformations that may not preserve behaviour. Three manuscript
corrections are required, one of which is an error introduced during the last rewrite.

---

## Phase 0 — restricted fixed oracles from stored records

The seven stored fixed conditions are not seven independent primitives: `M1` is metadata
rewrite alone, `M2`/`M3` bundle address (and selector) rewrite *with* 20% flooding, and
neutral insertion never existed as a fixed condition. Tier-B-fixed is therefore flooding +
metadata only. Recomputing the Tier-C-fixed oracle from stored adversarial scores
reproduced the published `fixed_oracle_best` **exactly** — 0 score mismatches and 0
attack-success mismatches over 8,724 keys — which validates the whole recomputation.

Restricting to flooding barely moves AuthGuard-Seq (.1365 → .1343) but costs the emulator
noticeably (.3433 → .3017), and the paired contrast still excludes zero at Tier A
(+0.184, CI [+0.035, +0.330]). Metadata rewrite adds nothing to that pair.

## Phase 1 — seed scope and factual repairs

The published −0.133 contrast is **correct**: the paired join on `(seed, sid)` already
restricts to seed 7702, so like-for-like and "3-seed" variants are byte-identical. What is
wrong is the surrounding table, which juxtaposes a 3-seed marginal (.181) with 1-seed rows
(.062) and a paired statistic computed on a third population (n=593). Robust recall computed
directly from source-level outcomes agrees with `clean × (1 − ASR)` to 1.1e-16, so there is
no aggregation artefact. Benchmark total 3,082 is correct. Byte budget caps *added* bytes at
2× (final ≤ 3×). Live-holdout facts all verified.

## Phase 2 — expanded execution-preservation audit

120 delegates, one per bytecode family, real EVM, equivalence definition imported unchanged.

| Class | Preserved | Rate | Wilson 95% |
|---|---:|---:|---|
| flooding | 3464/3464 | 1.0000 | [0.9989, 1.0000] |
| metadata rewrite | 866/866 | 1.0000 | [0.9956, 1.0000] |
| neutral insertion | 866/866 | 1.0000 | [0.9956, 1.0000] |

Zero failures, so the failure taxonomy is empty. Coverage includes 480 empty-calldata
(`receive`/`fallback`) and 480 zero-selector executions for flooding, and 788 calls whose
original trace actually reached an external call. Address and selector rewrite were not
audited into the tier; their 23/100 result stands.

## Phase 3 — regenerated and frozen checkpoints

40 checkpoints (seed 7702 × 4 models; seeds 7703/7704 × AuthGuard-Seq and emulator), each
carrying weights or estimator, temperature, all three thresholds, architecture, environment,
git commit and SHA-256. The training recipe was **not** modified to force determinism.

## Phase 4/5 — tiered attack against frozen checkpoints

14,540 + 14,540 attack rows and **614,757 persisted query candidates** with full
reconstruction parameters. Every tier for a given (model, seed, fold) used the same frozen
weights.

| Model | Tier | Clean | Best-of ASR | 95% CI | Robust recall | Seeds |
|---|---|---:|---:|---|---:|---:|
| **AuthGuard-Seq** | A | .8450 | **.1492** | [.105, .203] | **.7189** | 3 |
| | B | .8450 | **.1970** | [.148, .256] | **.6786** | 3 |
| | C | .8450 | .2084 | [.158, .268] | .6690 | 3 |
| 15-feature emulator | A | .8253 | .3083 | [.218, .413] | .5708 | 3 |
| | B | .8253 | .5417 | [.427, .645] | .3783 | 3 |
| | C | .8253 | .5722 | [.461, .675] | .3530 | 3 |
| Flat CNN | A | .6836 | .8109 | [.718, .889] | .1293 | 1 |
| | B | .6836 | .9356 | [.893, .972] | .0440 | 1 |
| | C | .6836 | .9477 | [.914, .978] | .0358 | 1 |
| Hist.+4-gram XGBoost | A | .6190 | .8111 | [.754, .866] | .1169 | 1 |
| | B | .6190 | .9844 | [.967, .997] | .0096 | 1 |
| | C | .6190 | .9911 | [.981, .998] | .0055 | 1 |

Central paired comparison, emulator − AuthGuard-Seq, 3 seeds, n = 1,503, 209 families:

| Tier | Emulator | AuthGuard | Difference | 95% CI | Excludes 0 |
|---|---:|---:|---:|---|---|
| A | .3353 | .1271 | **+0.2083** | [+0.076, +0.334] | yes |
| B | .5369 | .1670 | **+0.3699** | [+0.208, +0.520] | yes |
| C | .5635 | .1810 | +0.3826 | [+0.223, +0.524] | yes |

---

# Required answers

**1. Does AuthGuard-Seq substantially outperform the emulator under Tier A?** Yes. ASR .149
vs .308; paired +0.208, CI [+0.076, +0.334]. Robust recall .719 vs .571.

**2. Under Tier B?** Yes, and by more. ASR .197 vs .542; paired +0.370, CI [+0.208, +0.520].
Robust recall .679 vs .378.

**3. Are those differences statistically supported?** Yes. Both family-clustered paired CIs
exclude zero, over 3 seeds, 1,503 paired observations and 209 families.

**4. Does the four-model ordering survive under Tier A?** Partly. AuthGuard-Seq (.149) <
emulator (.308) < {Flat CNN .8109, XGBoost .8111}. The two weakest models are **statistically
tied at Tier A** — .8109 vs .8111 — so the ordering between them is not resolved there. The
top two positions are unambiguous.

**5. Under Tier B?** Yes, fully: .197 < .542 < .936 < .984, all four distinct.

**6. Direct robust recall for every model/tier?** See the table above; computed from
source-level outcomes, agreeing with `clean × (1 − ASR)` to 1.1e-16.

**7. How much additional evasion does Tier C obtain over Tier B at the same budget?**
Little. Tier-C-only successes: AuthGuard-Seq 46/384 (12.0%), emulator 137/1030 (13.3%),
Flat CNN 14/471 (3.0%), XGBoost 5/446 (1.1%). Not a claim of logical necessity — only what
the evaluated 64-query attacker achieved.

**8. What fraction of historical full-space winners contain weak-preservation primitives?**
AuthGuard-Seq 68.7%, Flat CNN 60.6%, XGBoost 58.3%, emulator 53.5% contain address or
selector rewrite. Winner-only statistics, so Tier-A/B-only fractions (6.9–9.7% and
31.3–46.5%) are lower bounds.

**9. Do metadata rewrite and neutral insertion pass the expanded audit?** Yes — 866/866 each,
Wilson [0.9956, 1.0000], across 120 families.

**10. Does Tier B qualify as an audit-supported compositional attacker?** Yes. All three of
its transformation classes passed at 100%. Address and selector rewrite remain excluded.

**11. How far do regenerated Tier-C results differ from the historical run?** Max |Δ| =
**0.011** across all models and metrics at seed 7702. AuthGuard-Seq: clean −0.0041, beam
+0.0040, random +0.0059. Flat CNN: clean −0.0110, beam +0.0085, random +0.0010.

**12. Pipeline mismatch, or expected stochastic variation?** Stochastic only. Both
deterministic estimators — the logistic-regression emulator and XGBoost — reproduce
**exactly** (Δ = 0.0000 on clean detection, beam ASR and random ASR). A data, fold,
preprocessing, or hyperparameter mismatch would have moved them too.

**13. Why 3,082 vs raw sum 3,085?** 3,082 is correct and is the actual row count. The 3,085
comes from using 8 production controls; the benchmark contains **5** `QUALITATIVE_CONTROL`
rows. The 8 named projects live in a separate registry (`benign_7702_bytecode.csv`, 45 rows /
8 projects / 30 unique bytecodes) that is not part of the benchmark. `sample_id` is unique
throughout; 2 bytecode hashes appear in more than one population but do not affect the count.

**14. What does the 2× byte budget mean?** `MAX_OVERHEAD = 2.0` enforced as
`len(final) <= original*(1+2.0)+1`: **added** bytes ≤ 2× original, **final** size ≤ 3×.
Empirically for Flood-200% (n=13,086): median final/original 2.962, p95 2.986, max 3.001.

**15. Which results are single-seed and which are multi-seed?** AuthGuard-Seq and the
emulator: seeds 7702/7703/7704 in every tier. Flat CNN and XGBoost: seed 7702 only. The
historical augmented-training and 30K-control blocks: seed 7702 only. Rows are never ranked
across differing seed scopes.

---

# Manuscript corrections required

1. **Table II says 8 audited implementations; the benchmark contains 5.** Introduced during
   the last rewrite. Revert to 5 and describe the 8-project registry as a separate population.
2. **Table V juxtaposes three populations without saying so** — a 3-seed marginal (.181), a
   1-seed marginal (.062), and a paired statistic on n=593. Add the seed-7702 AuthGuard-Seq
   reference row (clean .8404, F200 .1326, beam .1522, random .1882).
3. **"Edits are capped at 2× the original executable size"** should read "appended content
   ≤ 2× the original (final size ≤ 3×)".

# What did not change

The ASR definition, attack primitives, threshold fitting, family bootstrap, folds,
preprocessing, and architectures were untouched. No new architectures or datasets were
created. Retraining occurred only in Phase 3, as authorised, using the unmodified recipe.
