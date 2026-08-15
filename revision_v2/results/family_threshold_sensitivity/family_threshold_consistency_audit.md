# Consistency Audit: why θ=0.85 sensitivity ≠ frozen main-paper metrics

Targeted audit. No experiment was rerun, no manuscript touched, no query-budget work started.

---

# 1. Original artifact provenance

| Reference value | Traced to | Script |
|---|---|---|
| AuthGuard-Seq clean AUPRC **0.9244 ± 0.0140** | `revision_v2/results/baseline_v2/baseline_summary.csv`, row `authguard_seq`, `AUPRC_mean` | `revision_v2/experiments/baseline_v2/run_baseline_v2.py` |
| 15-feature LR clean AUPRC **0.910636** | `revision_v2/results/gate_0a_rule_emulator/gate_0a_summary.csv`, row `logreg_l2`, `auprc_macro` (identical for all three seeds) | `revision_v2/experiments/gate_0a_rule_emulator/run_gate_0a.py` |
| AuthGuard Tier-B marginal ASR **0.19696** (n_eligible 1843) | `frozen_numbers.json` → `.regenerated_experiment.phase4_analysis.tier_table[1].ASR_random_search` | `revision_v2/experiments/sprint_phase4/analyze_tiered.py` @ commit `8ebce5f` |
| LR Tier-B marginal ASR **0.541667** (n_eligible 1800) | same, `tier_table[4]` | same |
| Paired Tier-B LR − AuthGuard **+0.3699268**, CI **[+0.20790, +0.51954]**, n_paired 1503, 209 families, seeds 7702/7703/7704 | same, `paired_contrasts[1]` | same |
| Underlying attack rows | `revision_v2/results/sprint_phase4/tiered_attack_rows_s{7702,7703,7704}.csv.gz` | `revision_v2/experiments/sprint_phase4/run_tiered_attack.py` |

`run_tiered_attack.py` calls `runner.load_primary()` from `run_adaptive_attacks_v2.py` and
reads `frame["fold_id"]` — i.e. the **stored** folds in the benchmark CSV.

---

# 2. Row-wise family / fold comparison

θ=0.85 sensitivity assignment vs `revision_v2/data/authguardbench_7702_v2.csv.gz`:

| Check | Result |
|---|---|
| Rows compared (PRIMARY_EVALUATION) | 2,190 |
| **Family IDs identical (string equality)** | **yes — 0 differing rows** |
| Family partition identical (ignoring labels) | yes |
| Exact-bytecode groups | 1,665, and grouping identical (max families per hash = 1 in both) |
| **Fold IDs identical** | **NO — 1,307 of 2,190 rows differ (59.7%)** |

Examples:

| sample_id | family_id | stored fold | θ=0.85 fold |
|---|---|---|---|
| optimism:0x2f1211e38436327cc90408565ea2f16dfc082600 | F00002 | 4 | 0 |
| optimism:0xbe7ae1e53867f9f1778c8b728b533c00900a38be | F00003 | 1 | 0 |
| optimism:0x68d333198c60c8160848437b2870f3a5be693107 | F00005 | 4 | 1 |

Both assignments are valid and family-disjoint; they are simply different partitions.

### 2.1 The fold generator is not reproducible today

Using the **frozen** `family_id` from `family_assignment_frozen.csv` (not my recomputed
ones), re-running `task_alignment.py::original_fold_map` under the current environment
fails to reproduce the stored folds: **1,374 of 2,280 rows differ**. Candidates tested,
none of which reproduce `outer_fold_primary`:

| Candidate generator / population | Differing rows |
|---|---|
| `GroupKFold(5)`, capability corpus, primary classes (the documented path) | 1,374 |
| Legacy greedy-by-size GroupKFold algorithm, same population | 1,374 |
| `GroupKFold(5)`, task-aligned retained rows, primary classes | 1,734 |
| `GroupKFold(5)`, capability corpus, secondary classes | 1,742 |
| `GroupKFold(5)`, capability corpus, all classes | 1,673 |
| `GroupKFold(5)`, designator-excluded candidate set, primary classes | 1,410 |
| `StratifiedGroupKFold(5)` default | 1,672 |
| `StratifiedGroupKFold(5, shuffle, random_state=7702/0/42)` | 1,834 / 1,926 / 1,785 |

The stored assignment is nevertheless a well-formed, size-balanced, family-disjoint split
(capability-corpus rows per fold: 471/472/473/466/459; families per fold:
166/162/165/164/162), so it was produced by a GroupKFold-style objective under an
environment or code state that is no longer reconstructible from the repository.
**Conclusion: `fold_id` must be treated as a frozen input, not as something to regenerate.**

---

# 3. LR pipeline comparison

Two *different* LR pipelines exist in the repository, and this matters.

| Aspect | `gate_0a` `logreg_l2` (source of clean .911) | adaptive runner `emulator_logreg` (source of Tier-B, and what the sensitivity run used) | Sensitivity run |
|---|---|---|---|
| Feature matrix | `emulator_features.featurize(runtime_bytecode)` | same function, via `emulator_feature_matrix(frame)` | same |
| 15 features & order | `FEATURE_NAMES` (has_selfdestruct, n_hardcoded_addresses, balance_sweep, immutable_call_target, has_caller_guard, erc20_selector_present, code_bytes, unique_opcode_count, n_external_call_ops, has_external_call, has_dispatcher, has_fallback_path, fallback_reaches_external_call, fallback_reaches_external_call_over, n_fallback_reachable_blocks) | identical | identical |
| **Training population** | **`folds != f` → 4/5 of data** | **`folds ∉ {f, (f+1)%5}` → 3/5 of data** | 3/5 (runner) |
| Validation fold | none held out | `fold_id == (fold+1)%5` | same |
| StandardScaler fit on | training rows (4/5) | training rows (3/5) | same as runner |
| LogisticRegression args | `make_models(seed)` L2 | `LogisticRegression(penalty="l2", C=1.0, max_iter=5000, random_state=seed, class_weight="balanced")` | same as runner |
| Score | raw `predict_proba` | **temperature-calibrated** via `fusion.fit_temperature` on validation | same as runner |
| **Threshold calibration** | **inner family-grouped OOF, recall-at-5%-FPR on the training pool** | **`WarningPolicy.from_validation_negatives`, quantile of validation negatives** | same as runner |
| Folds | stored `fold_id` | stored `fold_id` | **recomputed θ=0.85 folds** |
| Labels | benchmark `label` | same | same |
| Metric aggregation | `auprc_macro` = mean over 5 folds | — | mean over folds, then mean ± SD over seeds |

**First point of divergence, sensitivity run vs the Tier-B reference:** the fold assignment.
Everything downstream is literally the same code (`fit_fold_models`).

**First point of divergence, sensitivity run vs the clean .911 anchor:** the pipeline
itself — training fraction (3/5 vs 4/5), threshold rule, and calibration. The sensitivity
clean LR number can never equal .911 regardless of folds, because it is produced by a
different estimator.

For AuthGuard the clean anchor (.9244, `baseline_v2`) *does* share the runner's convention
(`val_fold = (fold+1)%5`, train 3/5, temperature calibration), so folds are the only
structural difference there.

---

# 4. LR prediction comparison (row by row)

Both arms trained through the **unmodified** `runner.fit_fold_models`, seed 7702, differing
only in the fold vector. LR is deterministic, so any difference is attributable to folds.

| Fold (stored arm) | max abs Δ | mean abs Δ | exactly equal | stored threshold |
|---|---|---|---|---|
| 0 | 0.295700 | 0.030105 | 0 / 446 | 0.837733 |
| 1 | 0.310619 | 0.051224 | 0 / 446 | 0.083993 |
| 2 | 0.706844 | 0.038604 | 0 / 427 | 0.672275 |
| 3 | 0.228337 | 0.021737 | 0 / 447 | 0.843137 |
| 4 | 0.480442 | 0.033494 | 0 / 424 | 0.787396 |
| **All** | **0.706844** | **0.035011** | **0 / 2,190** | — |

θ=0.85 arm thresholds: 0.758317, 0.775519, 0.796911, 0.808366, 0.856103.

Fold-averaged clean metrics from the same code path:

| Arm | AUPRC | AUROC | Recall @5% |
|---|---|---|---|
| stored `fold_id` | **0.9153** | 0.9690 | 0.8270 |
| θ=0.85 recomputed | **0.9226** | 0.9700 | 0.7465 |

Not one row of 2,190 matches. The deterministic LR discrepancy is **fully explained by the
fold assignment**.

Note the stored arm's fold-1 threshold of 0.0840 against ~0.8 elsewhere — a genuine
instability in the validation-negative calibration on that partition (it yields
recall@5% = 1.0000 for that fold). Present in the reference protocol, not introduced here.

---

# 5. AuthGuard comparison

Structural comparison only; bitwise equality is not expected because
`torch.use_deterministic_algorithms(False)` plus CUDA makes training non-reproducible.

| Aspect | baseline_v2 / tiered reference | Sensitivity run |
|---|---|---|
| Architecture, config | `FusionConfig(active_views=(True,False,False))` | identical |
| Train / val / test rule | `val_fold=(fold+1)%5`, train 3/5 | identical |
| Epochs, patience, lr | 30, 5, 1e-3 | identical |
| Calibration | `fusion.fit_temperature` on validation | identical |
| Operating threshold | validation negatives, 5% FPR | identical |
| **Folds** | **stored `fold_id`** | **recomputed θ=0.85 folds** |

**Verdict for AuthGuard: not explained by retraining stochasticity alone.** It carries the
same 1,307-row fold difference as the LR, plus CUDA non-determinism on top. The clean gap
(.9430 sensitivity vs .9244 baseline_v2) is larger than the observed across-seed SD at
θ=0.85 (.0071), so stochasticity alone is not a sufficient account.

---

# 6. Attack-protocol comparison

| Element | Reference (`run_tiered_attack.py`, Tier B) | Sensitivity run | Same? |
|---|---|---|---|
| Action list | `TIER_ACTIONS["B"] = ("metadata","neutral25") + sorted(flood25/50/100/200)` | `("metadata","neutral25","flood25","flood50","flood100","flood200")` | **yes** |
| Restriction mechanism | patches `search.ACTIONS`, restores after | patches `search.ACTIONS` via the RQ4 Tier-B wrapper | yes |
| Random / beam / strongest | random + beam; `ASR_best_of` = min adversarial score over methods | same; strongest = min adversarial score over methods | yes |
| Query budget | 64 | 64 | yes |
| Beam width / max depth | 4 / 4 | 4 / 4 | yes |
| One-flood rule | `FLOOD_ACTIONS`, unchanged | unchanged | yes |
| Byte overhead cap | 2.0× | 2.0× | yes |
| Clean-detected eligibility | `clean_detected` at validation 5% FPR threshold | identical | yes |
| Threshold source | `policy.threshold_05` from validation negatives | identical | yes |
| Paired population | common clean-detected, keyed `["seed","fold","sid"]` | identical keying | yes |
| CI estimator | family-clustered percentile bootstrap, 10,000 replicates | identical (`rq4_metrics.py`) | yes |
| **Seed aggregation** | **pools seed-observations** (n_eligible 1843 ≈ 3×614; n_paired 1503 ≈ 3×501) | **per-seed marginals then mean ± SD; paired via per-source averaging across seeds** | **no** |
| **Model checkpoints** | frozen, one training per (model, seed, fold), reused across tiers | retrained inside each θ run | n/a |
| **Folds** | stored `fold_id` | recomputed θ folds | **no** |

The attack definition is identical. The two differences are seed aggregation and folds.

---

# 7. Root cause

**Primary — fold assignment.** `build_family_thresholds.py` regenerated the outer folds for
every θ, including θ=0.85, by re-running the documented `original_fold_map` procedure. That
procedure is not reproducible in the current environment: fed the frozen family IDs it
disagrees with the stored `fold_id` on 1,374/2,280 rows. The θ=0.85 sensitivity condition
therefore evaluated a different family-disjoint partition than every frozen experiment. The
A/B test in §4 isolates this: same code, same seed, same features, only the fold vector
swapped, and no LR prediction survives unchanged.

**Secondary — clean-metric estimator for LR.** The .911 anchor comes from `gate_0a`
(4/5 training, inner-OOF threshold, uncalibrated probabilities). The sensitivity run reports
the adaptive runner's `emulator_logreg` (3/5 training, validation-negative threshold,
temperature-calibrated). These are different estimators and would disagree even on identical
folds.

**Tertiary — seed aggregation.** The reference pools seed-observations; the sensitivity run
averages per seed. This does not contribute to the LR gap (pooling three identical
deterministic copies changes nothing) but does make the marginal counts non-comparable.

---

# 8. Why the paired effect stays close (+0.365 vs +0.370)

Three reasons, and they are worth stating because it is the most reassuring finding here:

1. **The contrast is conditioned within a run.** Both models are evaluated on the same
   common clean-detected sources and differenced per source. Repartitioning changes which
   sources are eligible and shifts both models' absolute ASRs, but it shifts them together.
2. **The quantity is a property of the model pair, not the partition.** How much more a
   15-feature emulator yields to flooding than a hierarchical attention model is largely
   invariant to which families sit in the test fold.
3. **The intervals are wide and overlap heavily.** Sensitivity [+0.086, +0.495] against
   reference [+0.208, +0.520]. A 0.005 difference in point estimate is far inside noise.

Marginal ASRs are the fragile quantities (LR .6337 vs .5417, AuthGuard .2241 vs .1970)
because each depends on its own eligible denominator, which the repartition changes
directly. The paired estimator is robust to exactly this.

---

# 9. Final verdict

**B. COMPARABLE AFTER CORRECTION.**

A specific configuration difference was found and fully accounts for the deterministic-LR
discrepancy: the sensitivity experiment **regenerated the outer folds instead of using the
benchmark's frozen `fold_id`**, and the fold generator is not reproducible in the current
environment.

Verdict A is excluded: the LR difference is not stochastic variation. Verdict C is too
strong: the attack definition, feature pipeline, model configuration, threshold rule, and
statistical estimators are all correct and identical to the reference — the defect is
confined to one input vector, and the internal cross-θ comparison remains valid because all
three conditions were generated the same way.

### 9.1 Minimal correction

**Do not rerun all nine experiments.** The existing runs are internally consistent and
support the cross-θ claim; what they do not support is equating the θ=0.85 row with the
frozen main-paper numbers.

Minimal fix, in order of cost:

1. **Change the reporting scope (zero compute).** State that the θ=0.85 condition is a
   re-derived reference under regenerated folds, not the frozen experiment, and remove any
   implication that it reproduces .924 / .911 / .1970 / .5417. The sensitivity conclusion —
   the paired effect is positive with CI above zero at all three θ — is unaffected.

2. **Add one bridge condition (~1 hour, 3 runs).** Rerun θ=0.85 only, with
   `fold_id` taken from the benchmark instead of recomputed, seeds 7702/7703/7704. This
   isolates fold-generation from θ and lets the θ=0.85 row be stated against the frozen
   protocol. Concretely, in `run_theta_experiment.py::theta_frames`, for θ=0.85 keep
   `bench.fold_id` and only swap `family_id`.

3. **Optional, for full comparability of marginals.** Add a pooled-seed aggregation
   alongside the per-seed one, matching `analyze_tiered.py`, so marginal ASRs can be placed
   next to the frozen table.

Regenerating 0.80 and 0.90 against the historical fold generator is **not** possible — that
generator could not be reconstructed (§2.1). If the reviewer requires all three thresholds
anchored to the frozen procedure, the only sound route is to freeze a new fold generator,
document it, and regenerate all three conditions with it, accepting that θ=0.85 will then
differ from the manuscript's stored folds.

**Stopping here for review as instructed. No correction has been applied.**
