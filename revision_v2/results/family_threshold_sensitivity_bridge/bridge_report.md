# Bridge Condition: θ = 0.85 on the Frozen Benchmark `fold_id`

Links the family-threshold sensitivity experiment to the paper's primary θ=0.85 evaluation.

- Repository commit: `55bcb59756772c52b2d5dc3a4cb2fb81057fe20e`
- Output directory: `revision_v2/results/family_threshold_sensitivity_bridge/`
- Frozen-artifact guard: `OK: 144 frozen files verified unchanged` before and after.
- θ=0.80 and θ=0.90 were **not** rerun. No manuscript, LaTeX, or frozen fold was touched.

---

# 1. Input verification

The frozen benchmark's `family_id` **is already** the θ=0.85 assignment — verified in the
consistency audit at 0 differing rows out of 2,190. The bridge therefore performs **no data
patching at all**: `run_bridge.py` calls the unmodified runner, which reads `fold_id` and
`family_id` directly from `revision_v2/data/authguardbench_7702_v2.csv.gz`. The single
intended difference from the sensitivity run is exact by construction rather than by
careful substitution.

| Check | Expected | Observed | Pass |
|---|---|---|---|
| Primary rows | 2,190 | 2,190 | yes |
| Source-flagged | 727 | 727 | yes |
| Unflagged | 1,463 | 1,463 | yes |
| Families | 790 | 790 | yes |
| Fold source | frozen `fold_id` | frozen `fold_id`, unmodified | yes |
| Folds present | 0–4 | 0, 1, 2, 3, 4 | yes |
| Families spanning folds | 0 | 0 | yes |
| Exact-bytecode groups | — | 1,665 | — |
| Exact-bytecode groups spanning folds | 0 | 0 | yes |
| Family IDs match θ=0.85 assignment | exact | exact, 0 differing rows | yes |

Rows per frozen fold: 446 / 446 / 427 / 447 / 424.

### 1.1 Post-run fold verification

Re-checked against the produced attack records, so the condition cannot be mislabelled:

| Seed | Attacked sources | Carrying frozen `fold_id` | Also matching the regenerated θ=0.85 fold |
|---|---|---|---|
| 7702 | 727 | **727 (100%)** | 367 (50.5%) |
| 7703 | 727 | **727 (100%)** | 367 (50.5%) |
| 7704 | 727 | **727 (100%)** | 367 (50.5%) |

Only half the sources share a fold between the two partitions, confirming the bridge really
is evaluating a different split from the sensitivity θ=0.85 condition.

### 1.2 Tier-B action verification

12/12 pre-run checks passed for each seed. Post-run, every searched sequence was
decomposed: the only actions emitted are `metadata`, `neutral25`, `flood25`, `flood50`,
`flood100`, `flood200`; **zero Tier-C actions observed**. The unrestricted fixed comparators
(`M2`, `M3`, `fixed_oracle_best`) are preserved in the raw records and excluded from every
statistic.

---

# 2. Bridge experimental configuration

| Item | Value |
|---|---|
| Condition | θ = 0.85, frozen benchmark `fold_id` |
| Seeds | 7702, 7703, 7704 |
| Folds | 0–4, frozen |
| Models | AuthGuard-Seq; 15-feature emulator logistic regression |
| Action space | metadata, neutral25, flood25, flood50, flood100, flood200 |
| Excluded | address, selector |
| Query budget / beam width / max depth | 64 / 4 / 4 |
| Flooding rule | at most one per sequence |
| Byte overhead cap | ≤ 200% |
| Operating point | validation-fitted nominal 5% FPR |
| Donor isolation | unchanged |
| Validity checks / success definition | unchanged |
| Bootstrap | 10,000 replicates, family-clustered |
| Runtime | 1,135 / 1,127 / 1,131 s per seed |
| `load_primary` patched | **no** |

---

# 3. Results by seed

| Seed | Model | Clean detected | Eligible obs | Eligible fams | Random ASR | Beam ASR | Strongest ASR | Robust recall | Successes | Failures | Invalid |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 7702 | AuthGuard-Seq | .8514 | 619 | 191 | .1405 | .1163 | .1405 | .7318 | 87 | 532 | 0 |
| 7702 | 15-feature LR | .8253 | 600 | 160 | .5417 | .4317 | .5417 | .3783 | 325 | 275 | 0 |
| 7703 | AuthGuard-Seq | .8473 | 616 | 187 | .2192 | .1721 | .2192 | .6616 | 135 | 481 | 0 |
| 7703 | 15-feature LR | .8253 | 600 | 160 | .5417 | .4317 | .5417 | .3783 | 325 | 275 | 0 |
| 7704 | AuthGuard-Seq | .8721 | 634 | 185 | .1877 | .1372 | .1877 | .7084 | 119 | 515 | 0 |
| 7704 | 15-feature LR | .8253 | 600 | 160 | .5417 | .4317 | .5417 | .3783 | 325 | 275 | 0 |

Zero invalid attack records. The LR rows are identical across seeds, as expected from its
deterministic fit (`LogisticRegression` with lbfgs ignores `random_state`).

---

# 4. Sensitivity-style paired result (Estimator A)

Convention: per-seed marginals, seed-level mean ± SD, and a per-source seed-averaged paired
effect with a family-clustered bootstrap. `rq4_metrics.py`, unchanged.

### 4.1 Per-seed

| Seed | Method | LR ASR | AuthGuard ASR | Δ | 95% CI | Excl. 0 | Paired obs | Families |
|---|---|---|---|---|---|---|---|---|
| 7702 | random | .5369 | .1437 | +.3932 | [+.2218, +.5465] | yes | 501 | 146 |
| 7702 | beam | .4491 | .1198 | +.3293 | [+.1604, +.4907] | yes | 501 | 146 |
| 7703 | random | .5376 | .2177 | +.3198 | [+.1361, +.4927] | yes | 519 | 147 |
| 7703 | beam | .4470 | .1811 | +.2659 | [+.0867, +.4378] | yes | 519 | 147 |
| 7704 | random | .5402 | .1533 | +.3870 | [+.2428, +.5295] | yes | 522 | 147 |
| 7704 | beam | .4483 | .1130 | +.3352 | [+.1845, +.4826] | yes | 522 | 147 |

6 of 6 per-seed CIs exclude zero.

### 4.2 Seed-level mean ± SD

| Method | Mean | SD | Min | Max | All positive | All CIs excl. 0 |
|---|---|---|---|---|---|---|
| random | +.3667 | .0332 | +.3198 | +.3932 | yes | yes |
| beam | +.3102 | .0314 | +.2659 | +.3352 | yes | yes |

### 4.3 Seed-averaged family-clustered

| Method | Δ_ASR | 95% CI | Excl. 0 | Sources | Families |
|---|---|---|---|---|---|
| random | **+.3510** | [+.1907, +.5025] | yes | 527 | 152 |
| beam | **+.2970** | [+.1318, +.4540] | yes | 527 | 152 |

---

# 5. Main-paper pooled paired result (Estimator B)

Convention: a faithful transcription of `sprint_phase4/analyze_tiered.py` — per-observation
strongest attack within the tier, marginal ASR over the **pooled** seed-observations, and a
family-clustered bootstrap over pooled `(seed, fold, sid)` rows using the same seed material
`phase4:{left}:{right}:B`.

| Model | Clean detection | Random ASR | Beam ASR | Best-of ASR | n_eligible | Eligible families |
|---|---|---|---|---|---|---|
| AuthGuard-Seq | .856946 | .182451 | .141787 | **.182451** | 1,869 | 197 |
| 15-feature LR | .825309 | .541667 | .431667 | **.541667** | 1,800 | 160 |

| Paired contrast | Value |
|---|---|
| LR ASR on common population | .538262 |
| AuthGuard ASR on common population | .171855 |
| **LR − AuthGuard** | **+0.366407** |
| Family-clustered 95% CI | **[+0.211040, +0.517936]** |
| Excludes zero | yes |
| n_paired | 1,542 |
| Families | 209 |
| Seed scope | 7702, 7703, 7704 |

Estimators A and B are stored in separate files and are not combined anywhere.

---

# 6. Comparison with the frozen main experiment

Against `frozen_numbers.json → .regenerated_experiment.phase4_analysis` (Estimator B on
both sides).

| Quantity | Frozen main | Bridge | Δ |
|---|---|---|---|
| **LR Tier-B marginal ASR** | 0.5416666666666666 | **0.5416666666666666** | **0.000000** |
| **LR beam ASR** | 0.4316666666666666 | **0.4316666666666666** | **0.000000** |
| **LR clean detection** | 0.8253094910591472 | **0.8253094910591472** | **0.000000** |
| **LR n_eligible** | 1,800 | **1,800** | **0** |
| AuthGuard Tier-B marginal ASR | 0.19696147585458493 | 0.18245050829320492 | −0.014511 |
| AuthGuard beam ASR | 0.15897992403689637 | 0.14178700908507224 | −0.017193 |
| AuthGuard clean detection | 0.8450252177900046 | 0.8569464824 | +0.011921 |
| AuthGuard n_eligible | 1,843 | 1,869 | +26 |
| **Paired LR − AuthGuard** | +0.3699268130405855 | **+0.3664072632944228** | **−0.003520** |
| 95% CI | [+0.207903, +0.519536] | [+0.211040, +0.517936] | nearly identical |
| n_paired | 1,503 | 1,542 | +39 |
| **Families** | 209 | **209** | **0** |

### 6.1 The LR reproduces the frozen result exactly

Every deterministic quantity matches to full double precision: marginal ASR, beam ASR,
clean detection, and eligible count. This is the decisive result of the bridge. The
consistency audit predicted it — the LR is deterministic, so once the frozen `fold_id` is
restored, nothing remains that could make it differ. **The LR discrepancy in the sensitivity
run (0.6337 vs 0.5417) was caused entirely by the regenerated folds, and by nothing else in
the feature pipeline, model configuration, threshold calibration, or attack.**

### 6.2 AuthGuard differences are ordinary training variation

AuthGuard's marginal ASR differs by −0.0145. Its across-seed SD within this bridge is 0.040
(per-seed values .1405 / .2192 / .1877), so the gap from the frozen value is well inside
one standard deviation of seed-to-seed variation. Clean detection differs by +0.0119, which
shifts its eligible population from 1,843 to 1,869 and hence the paired population from
1,503 to 1,542. `torch.use_deterministic_algorithms(False)` plus CUDA makes this
irreducible without changing the training recipe. **This is expected stochastic variation,
not a pipeline discrepancy.**

The paired effect lands within 0.0035 of the frozen value with an almost coincident CI, and
the family count is identical at 209.

---

# 7. Connection to the θ = 0.80 / 0.85 / 0.90 sensitivity

**Split provenance differs by block and must be read accordingly.** The first two rows use
the frozen benchmark split. The last three use threshold-specific family-disjoint splits
regenerated per θ, because no stored split exists for 0.80 or 0.90.

| Condition | Split | Estimator | Paired Tier-B Δ_ASR [95% CI] |
|---|---|---|---|
| Frozen main θ=.85 | frozen benchmark | B pooled | +0.3699 [+0.2079, +0.5195] |
| **Bridge θ=.85** | **frozen benchmark** | B pooled | **+0.3664 [+0.2110, +0.5179]** |
| **Bridge θ=.85** | **frozen benchmark** | A seed-averaged, beam | **+0.2970 [+0.1318, +0.4540]** |
| Sensitivity θ=.80 | regenerated | A seed-averaged, beam | +0.3555 [+0.2502, +0.4597] |
| Sensitivity θ=.85 | regenerated | A seed-averaged, beam | +0.3033 [+0.0858, +0.4949] |
| Sensitivity θ=.90 | regenerated | A seed-averaged, beam | +0.2578 [+0.1574, +0.3563] |

Random-search variant, same estimator A: bridge +0.3510 [+0.1907, +0.5025]; sensitivity
+0.4226 / +0.3650 / +0.2538 at θ = 0.80 / 0.85 / 0.90.

### The like-for-like comparison

Holding θ at 0.85 and the estimator at A, changing only the split:

| Method | Frozen split (bridge) | Regenerated split (sensitivity) | Δ |
|---|---|---|---|
| beam | +0.2970 | +0.3033 | +0.0063 |
| random | +0.3510 | +0.3650 | +0.0140 |

### Answers

**1. Does the bridge support the same qualitative robustness conclusion as the frozen main
result?**
Yes. Under the main-paper estimator the bridge gives +0.3664 [+0.2110, +0.5179] against the
frozen +0.3699 [+0.2079, +0.5195] — a 0.0035 difference with nearly coincident intervals,
both excluding zero, on an identical 209 families. The deterministic half of the comparison
matches exactly.

**2. Does the regenerated θ=0.85 sensitivity condition give a materially different paired
robustness conclusion from the frozen-fold bridge?**
No. Compared like-for-like (estimator A, θ=0.85), the two splits differ by +0.0063 on beam
and +0.0140 on random, far inside either CI. Both are positive and both exclude zero. The
regenerated split changes marginal ASRs noticeably — the eligible denominators move — but
leaves the paired effect essentially unchanged.

**3. Is the cross-threshold conclusion still defensible?**
Yes. All three sensitivity conditions were generated by one procedure, so their comparison
is internally valid; all three paired effects are positive with CIs above zero, and all 18
per-seed CIs exclude zero. The bridge now anchors the θ=0.85 end of that range to the
frozen benchmark, showing that the regenerated-split family does not shift the conclusion.
What remains out of reach is anchoring θ=0.80 and θ=0.90 to the frozen procedure, since the
historical fold generator could not be reconstructed.

**4. What is the cleanest manuscript-safe statement?**

> Using threshold-specific family-disjoint partitions, the paired Tier-B robustness
> advantage of AuthGuard-Seq over the 15-feature logistic regression remains positive with
> a family-clustered 95% interval above zero across θ = 0.80–0.90 (seed-averaged effect
> +0.358 to +0.258 for beam search). A bridge evaluation at θ = 0.85 using the frozen
> benchmark split reproduces the primary result (+0.366 [+0.211, +0.518] against the
> frozen +0.370 [+0.208, +0.520], with the deterministic baseline reproducing exactly),
> linking the sensitivity analysis to the paper's primary benchmark.

That wording is supported. It should not be strengthened to claim the sensitivity conditions
themselves run on the frozen split — they do not.

---

# 8. Scientific interpretation

The bridge does two things.

It **closes the audit**. The exact reproduction of every deterministic LR quantity —
marginal ASR, beam ASR, clean detection, eligible count, all to full precision — converts
the audit's diagnosis from a well-supported inference into a demonstration. The sensitivity
run's LR discrepancy was the fold vector, and only the fold vector. Nothing in the feature
extraction, the 15 features, the scaler, the LogisticRegression arguments, the threshold
calibration, the eligibility rule, or the attack contributed.

It **connects the sensitivity experiment to the paper**. The θ=0.85 sensitivity condition
was previously an island: internally consistent with 0.80 and 0.90 but not comparable to any
frozen number. The bridge shows that moving from the frozen split to a regenerated split at
the same θ perturbs the paired effect by less than 0.014 — smaller than the variation across
thresholds (0.098 for beam) and far smaller than the CI width. The cross-threshold
conclusion can now be reported alongside the primary result without implying they share a
split.

What the bridge does **not** establish: that θ=0.80 and θ=0.90 would give the same answers
on frozen-equivalent splits, since no such splits exist for them; that AuthGuard's absolute
ASR is reproducible (it is not — CUDA training variation moves it by more than the
split does); or anything about clean metrics, which were recorded but are not the object
here.

---

# 9. Files created

All under `revision_v2/results/family_threshold_sensitivity_bridge/`.

| File | Contents |
|---|---|
| `bridge_input_verification.json` | §1 pre-run input checks |
| `bridge_audit_s{7702,7703,7704}.json` | §1.2 Tier-B validation + in-run input verification |
| `bridge_estimatorA_per_seed.csv` | §3 per-seed results |
| `bridge_estimatorA_contrasts.csv` | §4 per-seed, seed-level, seed-averaged contrasts |
| `bridge_estimatorB_marginals.csv` | §5 pooled marginals |
| `bridge_estimatorB_paired.csv` | §5 pooled paired contrast |
| `bridge_clean_per_fold_s{seed}.csv`, `bridge_clean_per_fold_all.csv` | clean metrics (internal only) |
| `bridge_clean_predictions_s{seed}.csv.gz` | per-observation clean scores |
| `bridge_summary.json` | everything above plus commit, config, verifications, comparison |
| `bridge_report.md` | this report |

Attack artifacts in `revision_v2/results/adaptive_attacks_v2/`, seed-bearing:
`attack_per_row_bridge085_s{seed}.csv.gz`, `thresholds_bridge085_s{seed}.csv`,
`donor_ledger_bridge085_s{seed}.csv.gz`,
`adaptive_attack_v2_results_bridge085_s{seed}.json`.

Scripts: `revision_v2/experiments/family_threshold_sensitivity/{run_bridge.py,
analyze_bridge.py}`.

---

# 10. Reproduction commands

```bash
# Verify inputs and the Tier-B restriction without running
python3 revision_v2/experiments/family_threshold_sensitivity/run_bridge.py \
    --seed 7702 --validate-only

# Bridge, three seeds, ~1,130 s each
for s in 7702 7703 7704; do
  python3 revision_v2/experiments/family_threshold_sensitivity/run_bridge.py \
      --seed $s --folds 0 1 2 3 4 --budget 64
done

# Both estimators, comparison with the frozen main result
python3 revision_v2/experiments/family_threshold_sensitivity/analyze_bridge.py

# Frozen-artifact guard
python3 revision_v2/experiments/common/frozen.py verify
```

---

# 11. Anomalies / limitations

**11.1 AuthGuard is not bitwise reproducible.** `set_seed` calls
`torch.use_deterministic_algorithms(False)` and training runs on CUDA. Per-seed ASR within
this bridge spans .1405–.2192 (SD .040), which is larger than the gap to the frozen value
(−.0145). Absolute AuthGuard numbers should not be compared across runs; paired contrasts
should.

**11.2 The paired population is not identical to the frozen one.** 1,542 vs 1,503, because
AuthGuard's clean-detected set moved. The family count is identical at 209. This is a
consequence of 11.1, not of the protocol.

**11.3 The LR's zero SD is determinism, not stability.** All three seeds produce identical
LR rows. This must not be reported as the LR being more reproducible than AuthGuard-Seq.

**11.4 The frozen fold generator remains unreconstructed.** The bridge sidesteps this by
consuming the stored `fold_id` rather than regenerating it. θ=0.80 and θ=0.90 still have no
frozen-equivalent split, and none can be produced without first freezing a new documented
generator.

**11.5 Estimator A and Estimator B are not interchangeable.** A averages per seed and
per source; B pools seed-observations. On the same bridge data they give +0.2970 (A, beam)
and +0.3664 (B, best-of). Both are correct under their own convention; comparisons must hold
the estimator fixed, which every table here does.

**11.6 Clean metrics are recorded but not reconciled.** Per instruction, no attempt was made
to reconcile against the `gate_0a` LR clean AUPRC of .911, which the audit established comes
from a different estimator (4/5 training, inner-OOF threshold, uncalibrated probabilities).
For the record, bridge clean values are AuthGuard AUPRC .9289 ± .0215 and LR .9153 ± .0000.
No change to the manuscript's clean table is proposed.

**11.7 Scope.** θ=0.80 and θ=0.90 were not rerun. No query-budget sensitivity. No
manuscript or LaTeX changes. Positives are *source-flagged* delegates under *structural
screening*, not malicious/benign ground truth.
