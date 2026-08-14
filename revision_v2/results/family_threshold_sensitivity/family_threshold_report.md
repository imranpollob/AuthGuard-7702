# Family-Threshold Sensitivity Analysis (θ = 0.80 / 0.85 / 0.90)

Tests whether the headline clean-performance and Tier-B adaptive-robustness conclusions
are artifacts of the MinHash family threshold θ = 0.85.

- Repository commit: `55bcb59756772c52b2d5dc3a4cb2fb81057fe20e`
- Output directory: `revision_v2/results/family_threshold_sensitivity/`
- Frozen-artifact guard: `OK: 144 frozen files verified unchanged` before and after.
- No frozen result, no manuscript, and no LaTeX was modified.

---

# 1. Existing Family-Pipeline Audit

The current 0.85 family assignment is produced by `pipeline/01_freeze_families.py` using
helpers in `pipeline/ag_common.py`. Audited items:

| # | Item | Implementation |
|---|---|---|
| 1 | Bytecode preprocessing | `normalize_bytecode`: lowercase, strip `0x`, drop a trailing odd nibble |
| 2 | Opcode normalization | `disasm` linear sweep; `PUSH1`–`PUSH32` collapsed to a single `PUSH` token; immediates skipped; unknown opcodes → `UNK_xx` |
| 3 | Opcode 4-gram construction | `opcode_kgrams(ops, k=4)`, space-joined sliding window, as a **set**; if fewer than 4 tokens, the whole token string is the single gram; empty → `<EMPTY>` |
| 4 | MinHash implementation | `minhash_signature`, 128 permutations, xor-permutation trick: `h_p(x) = h(x) XOR seed_p`, signature entry = `min` over grams |
| 5 | Hash function | blake2b, `digest_size=8`, 8-byte salt seed; no Python `hash()`, so PYTHONHASHSEED-independent |
| 6 | Number of permutations | `NUM_PERM = 128` |
| 7 | Similarity calculation | Fraction of equal signature positions: `(sigs[j] == sigs[i]).mean()` — a MinHash **estimate** of Jaccard, not exact Jaccard |
| 8 | Threshold comparison | `>= threshold` |
| 9 | Family-building algorithm | Union-find over all pairs above threshold; deterministic root rule `parent[max(ra,rb)] = min(ra,rb)`; relabelled `F00001…` by first-appearance order |
| 10 | Connected components / transitive closure | **Yes** — union-find is a transitive closure, so families are connected components of the ≥θ similarity graph |
| 11 | Exact bytecode duplicates | Identical bytecode ⇒ identical opcode grams ⇒ similarity 1.0 ⇒ always the same family. Verified: 0 exact-duplicate groups span families at any θ |
| 12 | Proxy relationships | Not part of this family definition. Delegation-designator rows are handled separately in `task_alignment.py`; see the dependence check in §2 |
| 13 | Fold assignment | `task_alignment.py::original_fold_map`: `GroupKFold(5)` over the **original** capability corpus restricted to the task classes, grouped by `family_id`; family→fold map then applied to retained rows. `fold_id` in the v2 benchmark = `outer_fold_primary` |
| 14 | Family-disjointness verification | `build_benchmark_v2.py` asserts `groupby(family_id).fold.nunique() == 1` and the same for exact-bytecode groups |
| 15 | Random seeds for fold assignment | **None.** `GroupKFold` is unshuffled and unseeded — deterministic given the grouping. The global project seed `SEED = 7702` seeds MinHash permutations, not folds |
| 16 | Source artifacts | `capability_dataset.csv` (3,258 rows) → `family_assignment_frozen.csv` (`family_id`, `family_id_075/085/090`) → `paper_build/data_hygiene/task_aligned_dataset_v1.csv` (3,082 rows) → `revision_v2/data/authguardbench_7702_v2.csv.gz` (2,190 PRIMARY_EVALUATION) |

**Note on terminology:** the pipeline uses a MinHash *estimate* of Jaccard similarity over
opcode 4-grams. The residual-similarity analysis in §5 uses the same estimator so the
numbers are on the same scale as the threshold.

---

# 2. θ = 0.85 Reproduction Check

Recomputed from `capability_dataset.csv` through the frozen code path. All three stored
thresholds were reproduced, not only the reference.

| Metric | Current/stored | Recomputed | Difference |
|---|---|---|---|
| Families @ θ=0.75 | 1,120 | 1,120 | 0 |
| **Families @ θ=0.85** | **1,329** | **1,329** | **0** |
| Families @ θ=0.90 | 1,511 | 1,511 | 0 |
| Family IDs @ 0.85 identical (string equality, row-aligned) | — | **yes** | 0 rows differ |
| Partition identical @ 0.85 (ignoring labels) | — | yes | — |
| Primary-population observations | 2,190 | 2,190 | 0 |
| Source-flagged | 727 | 727 | 0 |
| Unflagged | 1,463 | 1,463 | 0 |
| Primary families @ 0.85 | ~790 | 790 | 0 |
| Outer folds | 5 | 5 | 0 |
| Exact-duplicate groups (primary) | — | 1,665 | — |
| Exact-dup groups spanning families | 0 | 0 | 0 |
| Exact-dup groups spanning folds | 0 | 0 | 0 |
| Families spanning folds | 0 | 0 | 0 |

Reproduction is **exact** — not merely the same partition, but bitwise-identical family ID
strings. The STOP condition is cleared.

### 2.1 Row-set dependence on θ (checked before proceeding)

The evaluated population is not obviously θ-invariant: `task_alignment.py` (lines 154–163)
decides delegation-designator retention by testing whether a recovered runtime's exact
duplicates fall in a **different family** from the designator row. Changing θ could
therefore change which rows exist, which would make the three thresholds incomparable.

All 76 designator decisions were re-derived under each θ:

| θ | Designator decisions changed |
|---|---|
| 0.80 | 0 |
| 0.85 | 0 |
| 0.90 | 0 |

The retained row set is invariant, so all three thresholds evaluate the **same 2,190
observations with the same labels**, differing only in grouping and folds.

---

# 3. Family Structure Across Thresholds

Computed over the 2,190-row primary population.

| Metric | θ = 0.80 | θ = 0.85 | θ = 0.90 |
|---|---|---|---|
| Observations | 2,190 | 2,190 | 2,190 |
| Source-flagged | 727 | 727 | 727 |
| Unflagged | 1,463 | 1,463 | 1,463 |
| **Families** | **701** | **790** | **928** |
| Singleton families | 413 | 477 | 613 |
| Singleton % | 58.92 | 60.38 | 66.06 |
| Multi-member families | 288 | 313 | 315 |
| Median family size | 1.0 | 1.0 | 1.0 |
| Mean family size | 3.124 | 2.772 | 2.360 |
| Max family size | 70 | 58 | 48 |
| Top-10 family sizes | 70, 58, 49, 46, 36, 35, 32, 32, 31, 31 | 58, 49, 48, 39, 35, 32, 32, 32, 31, 26 | 48, 48, 42, 35, 34, 28, 28, 27, 26, 26 |
| All-positive families | 158 | 184 | 240 |
| All-negative families | 517 | 581 | 672 |
| Mixed families | 26 | 25 | 16 |
| Exact-duplicate groups | 1,665 | 1,665 | 1,665 |
| Exact-dup groups spanning families | 0 | 0 | 0 |
| Exact-dup groups spanning folds | 0 | 0 | 0 |
| Families spanning folds | 0 | 0 | 0 |

### 3.1 How the partition changes

| Transition | Coarse families absorbing ≥2 finer | Finer families involved | Observations affected | Largest merged component |
|---|---|---|---|---|
| 0.90 → 0.85 | 109 | 247 | 835 | 58 obs (5 finer families) |
| 0.85 → 0.80 | 64 | 153 | 646 | 70 obs (8 finer families) |

### 3.2 Giant-component check

| θ | Max family size | % of primary | Flagged |
|---|---|---|---|
| 0.80 | 70 | 3.20 | no |
| 0.85 | 58 | 2.65 | no |
| 0.90 | 48 | 2.19 | no |

**No giant connected component at any threshold.** Merging is gradual, so the existing
`GroupKFold(5)` split algorithm remains valid at all three.

---

# 4. Family-Disjoint Split Verification

Five outer folds per θ, built by the same `original_fold_map` procedure (unshuffled,
unseeded `GroupKFold(5)` over the original capability corpus grouped by the new
`family_id`). No manual adjustment.

| θ | Fold | Train obs | Test obs | Train fams | Test fams | Train flagged prev. | Test flagged prev. | Family overlap | Exact-hash overlap |
|---|---|---|---|---|---|---|---|---|---|
| 0.80 | 0 | 1,730 | 460 | 557 | 144 | .3462 | .2783 | 0 | 0 |
| 0.80 | 1 | 1,766 | 424 | 562 | 139 | .3454 | .2759 | 0 | 0 |
| 0.80 | 2 | 1,752 | 438 | 560 | 141 | .3082 | .4269 | 0 | 0 |
| 0.80 | 3 | 1,763 | 427 | 563 | 138 | .3279 | .3489 | 0 | 0 |
| 0.80 | 4 | 1,749 | 441 | 562 | 139 | .3322 | .3311 | 0 | 0 |
| 0.85 | 0 | 1,728 | 462 | 627 | 163 | .3189 | .3810 | 0 | 0 |
| 0.85 | 1 | 1,759 | 431 | 637 | 153 | .3354 | .3179 | 0 | 0 |
| 0.85 | 2 | 1,757 | 433 | 633 | 157 | .3250 | .3603 | 0 | 0 |
| 0.85 | 3 | 1,752 | 438 | 633 | 157 | .3533 | .2466 | 0 | 0 |
| 0.85 | 4 | 1,764 | 426 | 630 | 160 | .3271 | .3521 | 0 | 0 |
| 0.90 | 0 | 1,759 | 431 | 741 | 187 | .3394 | .3016 | 0 | 0 |
| 0.90 | 1 | 1,732 | 458 | 741 | 187 | .3291 | .3428 | 0 | 0 |
| 0.90 | 2 | 1,736 | 454 | 740 | 188 | .3185 | .3833 | 0 | 0 |
| 0.90 | 3 | 1,747 | 443 | 743 | 185 | .3412 | .2957 | 0 | 0 |
| 0.90 | 4 | 1,786 | 404 | 747 | 181 | .3315 | .3342 | 0 | 0 |

Programmatic assertions, all 15 splits: `train ∩ test` families = ∅ and exact-bytecode
hashes = ∅. Validation is drawn from the training pool by the training scripts' own
`StratifiedGroupKFold`/`fold+1` procedure, unchanged, so validation families are a subset
of train families and never intersect test.

---

# 5. Residual Train/Test Similarity

Maximum MinHash similarity from each held-out test delegate to any training delegate, per
θ, using the same estimator as the family construction.

| Statistic | θ = 0.80 | θ = 0.85 | θ = 0.90 |
|---|---|---|---|
| Median | .6484 | .6797 | .7656 |
| p90 | .7656 | .8125 | .8828 |
| p95 | .7812 | .8281 | .8906 |
| Maximum | .7969 | .8438 | .8984 |
| n > 0.90 | 0 | 0 | 0 |
| % > 0.90 | 0.00 | 0.00 | 0.00 |
| n ≥ own θ | 0 | 0 | 0 |
| % ≥ own θ | 0.00 | 0.00 | 0.00 |

Band counts (test observations, 2,190 per θ):

| Band | θ = 0.80 | θ = 0.85 | θ = 0.90 |
|---|---|---|---|
| > 0.90 | 0 | 0 | 0 |
| 0.85 – 0.90 | 0 | 0 | 500 |
| 0.80 – 0.85 | 0 | 319 | 402 |
| 0.70 – 0.80 | 708 | 680 | 408 |
| < 0.70 | 1,482 | 1,191 | 880 |

By construction no test delegate can reach its own θ against training data — that is the
family-disjointness guarantee, and it holds exactly. The distribution shifts as expected:
looser families strip more near-neighbour structure out of the test side.

---

# 6. Experimental Configuration

| Item | Value |
|---|---|
| Thresholds | 0.80, 0.85 (reference), 0.90 |
| Seeds | 7702, 7703, 7704 |
| Folds | 0–4, family-disjoint, rebuilt per θ |
| Models | AuthGuard-Seq; 15-feature emulator logistic regression |
| Population | 2,190 PRIMARY_EVALUATION (727 source-flagged / 1,463 unflagged), identical at every θ |
| Training protocol | unchanged: `fit_fold_models` in `run_adaptive_attacks_v2.py`, 30 epochs, patience 5, lr 1e-3, temperature calibration on validation, validation-fitted operating thresholds |
| Operating point | nominal 5% FPR from validation negatives |
| Attack | Tier-B adaptive, score-aware |
| Tier-B action space | `metadata`, `neutral25`, `flood25`, `flood50`, `flood100`, `flood200` |
| Excluded actions | `address`, `selector` |
| Query budget / beam width / max depth | 64 / 4 / 4 |
| Flooding rule | at most one flooding action per sequence |
| Byte overhead cap | ≤ 200% of original |
| Donor isolation | unchanged, partition-isolated pools; families/folds follow the θ-specific assignment |
| Bootstrap | 10,000 replicates, family-clustered |
| Runtime | ~1,130 s per (θ, seed); 9 runs |
| Environment | Python 3.12.12, torch 2.9.0+cu128, numpy 2.3.4, pandas 2.3.3, scikit-learn 1.7.2, xgboost 3.3.0, NVIDIA RTX 2080 SUPER |

### 6.1 Tier-B action-space verification

Pre-run: 12/12 checks passed for each of the 9 runs (action list exactly Tier B; `address`
and `selector` unreachable by random search and by beam expansion; budget 64; width 4;
depth 4; one-flooding rule; 2.0× byte cap; flood levels unchanged). Saved as
`tierb_action_audit_theta0XX_s77YY.json`.

Post-run: every `random_search`/`beam_search` record in all 9 runs was decomposed. The only
actions ever emitted are the six Tier-B actions; **zero Tier-C actions observed** in any
run. Saved as `family_threshold_action_verification.json`.

The fixed comparators `M2`/`M3` (and therefore `fixed_oracle_best`) are generated outside
the search by `donor_pools/pools.py` and still use address/selector rewriting. They are
preserved in the raw records and **excluded from every statistic in this report**, which
uses `random_search` and `beam_search` only.

---

# 7. Clean Performance Across Thresholds

Convention matches `run_baseline_v2.py::aggregate`: metrics averaged over folds within a
seed, then mean ± SD (ddof=0) across the three seeds.

| θ | Model | AUPRC | AUROC | Brier | Recall @5% nominal FPR |
|---|---|---|---|---|---|
| 0.80 | AuthGuard-Seq | **.9408 ± .0136** | .9634 | .0627 | .8878 |
| 0.80 | 15-feature LR | **.9128 ± .0000** | .9673 | .0593 | .8537 |
| 0.85 | AuthGuard-Seq | **.9430 ± .0071** | .9741 | .0597 | .9119 |
| 0.85 | 15-feature LR | **.9226 ± .0000** | .9700 | .0582 | .7465 |
| 0.90 | AuthGuard-Seq | **.9549 ± .0079** | .9829 | .0557 | .8832 |
| 0.90 | 15-feature LR | **.9141 ± .0000** | .9675 | .0566 | .7822 |

The LR's SD is exactly zero at every threshold. This is **not** a stability finding: see
§15.1 — the LR fit is deterministic, so the three seeds are duplicates rather than
replicates for that model.

### 7.1 Paired clean contrasts (AuthGuard-Seq − LR)

Estimator: family-clustered bootstrap exactly as `run_statistical_analysis_v2.py` —
families resampled with replacement within each fold, the **same weight draw applied to
both models** (so the contrast is paired), sample-weighted average precision per replicate,
averaged over folds then seeds. 10,000 replicates. The repository's own
`fast_weighted_ap_batch` is used and its `verify_fast_ap()` self-test against sklearn was
run and passed before analysis.

| θ | Metric | AuthGuard | LR | Δ | 95% CI | Excludes 0 |
|---|---|---|---|---|---|---|
| 0.80 | AUPRC | .9408 | .9128 | **+.0281** | [−.0098, +.0911] | **no** |
| 0.85 | AUPRC | .9430 | .9226 | **+.0204** | [−.0077, +.0657] | **no** |
| 0.90 | AUPRC | .9549 | .9141 | **+.0407** | [+.0096, +.0855] | **yes** |
| 0.80 | Recall@5% | .8878 | .8537 | +.0342 | [−.0663, +.1757] | no |
| 0.85 | Recall@5% | .9119 | .7465 | +.1654 | [+.0809, +.2850] | **yes** |
| 0.90 | Recall@5% | .8832 | .7822 | +.1010 | [+.0027, +.2424] | **yes** |

---

# 8. Tier-B Adaptive Robustness Across Thresholds

Mean ± SD across seeds. Marginal ASR is over each model's own clean-detected population.
Robust recall is over all 727 positive observations.

| θ | Model | Clean-detected | Eligible obs | Eligible fams | Random ASR | Beam ASR | Strongest ASR | Robust recall |
|---|---|---|---|---|---|---|---|---|
| 0.80 | AuthGuard-Seq | .8670 | 630.3 | 166.3 | .2157 ± .0344 | **.1672 ± .0168** | .2157 | **.6804 ± .0401** |
| 0.80 | 15-feature LR | .8432 | 613.0 | 145.0 | .5710 ± .0000 | **.4666 ± .0000** | .5710 | **.3618 ± .0000** |
| 0.85 | AuthGuard-Seq | .9023 | 656.0 | 193.3 | .2241 ± .1145 | **.1656 ± .0780** | .2241 | **.6960 ± .0783** |
| 0.85 | 15-feature LR | .7510 | 546.0 | 147.0 | .6337 ± .0000 | **.5183 ± .0000** | .6337 | **.2751 ± .0000** |
| 0.90 | AuthGuard-Seq | .8675 | 630.7 | 231.7 | .2602 ± .0216 | **.1707 ± .0051** | .2602 | **.6419 ± .0237** |
| 0.90 | 15-feature LR | .7758 | 564.0 | 180.0 | .5035 ± .0000 | **.4060 ± .0000** | .5035 | **.3851 ± .0000** |

Attack-record accounting (summed over the three seeds):

| θ | Model | Successful evasions | Unsuccessful attacks | Invalid attacks |
|---|---|---|---|---|
| 0.80 | AuthGuard-Seq | 723 | 3,059 | 0 |
| 0.80 | 15-feature LR | 1,908 | 1,770 | 0 |
| 0.85 | AuthGuard-Seq | 782 | 3,154 | 0 |
| 0.85 | 15-feature LR | 1,887 | 1,389 | 0 |
| 0.90 | AuthGuard-Seq | 815 | 2,969 | 0 |
| 0.90 | 15-feature LR | 1,539 | 1,845 | 0 |

**Zero invalid attack records** at any threshold, for either model. No records were
discarded.

### 8.1 Why strongest-attack ASR equals random-search ASR

Under Tier B, the six actions with the "at most one flooding action" rule and depth ≤ 4
admit exactly **48** distinct sequences (6 at depth 1, 18 at depth 2, 24 at depth 3; depth 4
is unreachable because only three mutually-compatible actions exist). The 64-query budget
exceeds 48, so **random search enumerates the entire allowed composition space** — at most
44 queries were consumed after duplicate and structural-validity filtering.

Consequences, verified empirically: beam search never strictly beat random search on any of
727 observations in either model, and the strongest-attack success set equals the
random-search success set in all 18 cells. The Tier-B ASRs reported here are therefore the
**exact optimum over the entire audited action space at this depth**, not search-limited
estimates. Saved as `family_threshold_action_space_enumeration.json`.

---

# 9. Paired Robustness Contrasts

Primary comparison: **Δ_ASR(θ) = ASR_LR − ASR_AuthGuard**, computed on the common
clean-detected population (observations both models detect on clean input). Marginal ASRs
with different denominators are never subtracted.

### 9.1 Per-seed effects

| θ | Seed | Method | LR ASR | AuthGuard ASR | Δ | 95% CI | Excl. 0 | Paired obs | Families |
|---|---|---|---|---|---|---|---|---|---|
| 0.80 | 7702 | random | .6397 | .2389 | +.4008 | [+.2500, +.5350] | yes | 519 | 133 |
| 0.80 | 7702 | beam | .5260 | .1715 | +.3545 | [+.2127, +.4888] | yes | 519 | 133 |
| 0.80 | 7703 | random | .6296 | .2093 | +.4204 | [+.3009, +.5242] | yes | 540 | 138 |
| 0.80 | 7703 | beam | .5167 | .1722 | +.3444 | [+.2298, +.4545] | yes | 540 | 138 |
| 0.80 | 7704 | random | .6365 | .1431 | +.4934 | [+.3900, +.5895] | yes | 531 | 136 |
| 0.80 | 7704 | beam | .5217 | .1149 | +.4068 | [+.3062, +.5056] | yes | 531 | 136 |
| 0.85 | 7702 | random | .6403 | .0878 | +.5525 | [+.4239, +.6636] | yes | 467 | 135 |
| 0.85 | 7702 | beam | .5310 | .0664 | +.4647 | [+.3470, +.5749] | yes | 467 | 135 |
| 0.85 | 7703 | random | .6300 | .3681 | +.2619 | [+.0627, +.4547] | yes | 527 | 136 |
| 0.85 | 7703 | beam | .5161 | .2619 | +.2543 | [+.0425, +.4399] | yes | 527 | 136 |
| 0.85 | 7704 | random | .6356 | .1150 | +.5206 | [+.3799, +.6425] | yes | 461 | 136 |
| 0.85 | 7704 | beam | .5293 | .0781 | +.4512 | [+.3236, +.5633] | yes | 461 | 136 |
| 0.90 | 7702 | random | .5135 | .2370 | +.2765 | [+.1530, +.4096] | yes | 481 | 164 |
| 0.90 | 7702 | beam | .4262 | .1622 | +.2640 | [+.1546, +.3768] | yes | 481 | 164 |
| 0.90 | 7703 | random | .5136 | .2704 | +.2432 | [+.1188, +.3765] | yes | 477 | 162 |
| 0.90 | 7703 | beam | .4298 | .1614 | +.2683 | [+.1540, +.3806] | yes | 477 | 162 |
| 0.90 | 7704 | random | .5157 | .2306 | +.2851 | [+.1564, +.4192] | yes | 477 | 164 |
| 0.90 | 7704 | beam | .4340 | .1468 | +.2872 | [+.1787, +.3953] | yes | 477 | 164 |

**18 of 18 per-seed CIs exclude zero, all positive.**

### 9.2 Seed-level mean ± SD

| θ | Method | Mean | SD | Min seed | Max seed | All positive | All CIs excl. 0 |
|---|---|---|---|---|---|---|---|
| 0.80 | random | +.4382 | .0399 | +.4008 | +.4934 | yes | yes |
| 0.80 | beam | +.3686 | .0273 | +.3444 | +.4068 | yes | yes |
| 0.85 | random | +.4450 | .1301 | +.2619 | +.5525 | yes | yes |
| 0.85 | beam | +.3900 | .0962 | +.2543 | +.4647 | yes | yes |
| 0.90 | random | +.2683 | .0181 | +.2432 | +.2851 | yes | yes |
| 0.90 | beam | +.2732 | .0101 | +.2640 | +.2872 | yes | yes |

### 9.3 Seed-averaged family-clustered estimate (primary)

Estimator: per-source differences averaged across the seeds in which both models detect the
source cleanly, then family-clustered percentile bootstrap over those per-source values.
Repeated seed evaluations of the same source are **not** treated as independent
observations. Identical to the estimator used in the RQ4 replication.

| θ | Method | Δ_ASR | 95% CI | Excludes 0 | Sources | Families |
|---|---|---|---|---|---|---|
| 0.80 | random | **+.4226** | [+.3152, +.5246] | yes | 549 | 141 |
| 0.80 | beam | **+.3555** | [+.2502, +.4597] | yes | 549 | 141 |
| 0.85 | random | **+.3650** | [+.1639, +.5509] | yes | 532 | 140 |
| 0.85 | beam | **+.3033** | [+.0858, +.4949] | yes | 532 | 140 |
| 0.90 | random | **+.2538** | [+.1444, +.3520] | yes | 499 | 172 |
| 0.90 | beam | **+.2578** | [+.1574, +.3563] | yes | 499 | 172 |

---

# 10. Sensitivity Assessment

**1. How many families result at 0.80, 0.85, and 0.90?**
701, 790, and 928 respectively over the 2,190-row primary population (1,223 / 1,329 / 1,511
over the full 3,258-row clustering corpus).

**2. Does the current 0.85 setting look unusual relative to its neighbouring thresholds?**
No. Family count is monotone and the spacing is unremarkable (+89 from 0.80, +138 to 0.90).
Singleton share rises smoothly (58.9 → 60.4 → 66.1%), mean family size falls smoothly
(3.12 → 2.77 → 2.36), and the largest family shrinks monotonically (70 → 58 → 48). There is
no discontinuity, no percolation, and no giant component at or near 0.85.

**3. Does clean AuthGuard AUPRC remain broadly stable?**
Yes, within a narrow band: .9408 / .9430 / .9549. Total spread **0.0141**, and the trend is
mildly upward as families get stricter. Across-seed SD is ≤ .0136 at every threshold.

**4. Does clean LR AUPRC remain broadly stable?**
Yes: .9128 / .9226 / .9141. Total spread **0.0098**, non-monotone (peaks at 0.85).

**5. Does the clean model-selection interpretation materially change at any threshold?**
**Partly — and this is the one place the existing framing is threshold-sensitive.** On
AUPRC, the paired CI includes zero at θ=0.80 (+.0281 [−.0098, +.0911]) and at the reference
θ=0.85 (+.0204 [−.0077, +.0657]), so clean AUPRC does not statistically distinguish the two
models — consistent with the existing interpretation. At θ=0.90 the AUPRC CI **excludes**
zero (+.0407 [+.0096, +.0855]). On Recall@5%, the CI excludes zero at both 0.85 (+.1654)
and 0.90 (+.1010) but not 0.80. So the statement "clean evaluation does not establish
decisive superiority" is supported for AUPRC at 0.80 and 0.85, but not at 0.90, and is not
supported for Recall@5% at 0.85 or 0.90. The effect sizes remain small throughout
(≤ .041 AUPRC).

**6. Is Tier-B AuthGuard ASR lower than LR ASR at all three family thresholds?**
Yes, at every threshold, on both search methods, in every seed. Marginally, strongest-attack
ASR is .2157 / .2241 / .2602 for AuthGuard versus .5710 / .6337 / .5035 for LR.

**7. Is LR ASR − AuthGuard ASR positive at all three thresholds?**
Yes. All 6 seed-averaged estimates, all 6 seed-level means, and all 18 per-seed effects are
positive. No sign reversal anywhere.

**8. Does the family-clustered 95% CI remain above zero at all thresholds?**
Yes. All 6 seed-averaged CIs and all 18 per-seed CIs exclude zero. The narrowest lower
bound is **+.0425** (θ=0.85, seed 7703, beam) — thin but above zero.

**9. How much does the paired robustness effect vary across thresholds?**
Beam: +.2578 to +.3555, a spread of **.0977** (27.5% of the largest value). Random: +.2538
to +.4226, a spread of **.1688** (40.0%). Both decline monotonically as families get
stricter. This is real variation and should not be described as "unchanged".

**10. Do alternative thresholds materially change the shared eligible population?**
Modestly. Paired sources: 549 / 532 / 499 (−9.1% from 0.80 to 0.90). Paired families:
141 / 140 / 172 — roughly flat from 0.80 to 0.85, then +23% at 0.90 because the same
observations are split into more families. Clean-detection rates also move (AuthGuard
.8670 / .9023 / .8675; LR .8432 / .7510 / .7758), which shifts the eligible denominators.

**11. Does lowering the threshold reduce residual train/test structural similarity as
expected?**
Yes. Median nearest-training similarity falls .7656 → .6797 → .6484 as θ goes 0.90 → 0.85 →
0.80; p95 falls .8906 → .8281 → .7812. Direction and monotonicity are exactly as predicted.

**12. Does raising it expose noticeably more near-neighbour structure?**
Yes, moderately. Going 0.85 → 0.90 raises the median by +.0859 and p95 by +.0625, and puts
500 test observations into the 0.85–0.90 band that is empty at both lower thresholds. It
does not create any test observation above 0.90 (max .8984), so even the strictest setting
leaves no near-identical train/test pair.

**13. Is there evidence that the headline robustness conclusion depends critically on
θ = 0.85?**
No. The advantage is positive with a family-clustered CI above zero at all three
thresholds, on both search methods, in all three seeds — 18/18 per-seed CIs. If anything
θ=0.85 is the *least* favourable of the three for precision: it has the widest seed-averaged
CI (beam [+.0858, +.4949]) and the largest across-seed SD (.0962 beam), driven by seed 7703
where AuthGuard's ASR was .2619 against .0664/.0781 in the other two seeds.

**14. What is the strongest scientifically defensible conclusion?**
Absolute estimates move with the family definition — the seed-averaged beam effect ranges
from +.2578 to +.3555 across thresholds, and clean AUPRC for AuthGuard ranges .9408–.9549 —
but AuthGuard-Seq's Tier-B adaptive-robustness advantage over the 15-feature logistic
regression remains substantial and its family-clustered 95% interval remains above zero at
every evaluated threshold and in every seed. The headline robustness conclusion is therefore
not an artifact of choosing θ = 0.85. The clean-performance conclusion is weaker: the
AuthGuard advantage on clean AUPRC is small at all thresholds and statistically
indistinguishable from zero at 0.80 and 0.85, but distinguishable at 0.90, so the "clean
evaluation is not decisive" claim should be stated with reference to the operating
threshold rather than as threshold-independent.

---

# 11. Manuscript-Integration Data

Candidate compact sensitivity table (Δ_ASR = LR − AuthGuard, Tier-B, seed-averaged
family-clustered, beam search):

| Family threshold | # Families | AuthGuard AUPRC | LR AUPRC | AuthGuard Tier-B ASR | LR Tier-B ASR | Paired Δ_ASR [95% CI] |
|---|---|---|---|---|---|---|
| 0.80 | 701 | 0.941 | 0.913 | 0.166 | 0.467 | +0.356 [+0.250, +0.460] |
| **0.85** | **790** | **0.943** | **0.923** | **0.166** | **0.518** | **+0.303 [+0.086, +0.495]** |
| 0.90 | 928 | 0.955 | 0.914 | 0.171 | 0.406 | +0.258 [+0.157, +0.356] |

ASR columns are beam-search marginal ASR at the nominal 5% operating point. If the
strongest-attack (exhaustive) figure is preferred instead, substitute AuthGuard
.216 / .224 / .260 and LR .571 / .634 / .504, with Δ_ASR +.423 [+.315, +.525] / +.365
[+.164, +.551] / +.254 [+.144, +.352].

Second internal table:

| Threshold | Paired obs | Paired families | Median resid. sim. | p90 | p95 | Max | % test > 0.90 |
|---|---|---|---|---|---|---|---|
| 0.80 | 549 | 141 | .6484 | .7656 | .7812 | .7969 | 0.00 |
| 0.85 | 532 | 140 | .6797 | .8125 | .8281 | .8438 | 0.00 |
| 0.90 | 499 | 172 | .7656 | .8828 | .8906 | .8984 | 0.00 |

No plot generated: the pattern is a monotone decline across three points and is fully
communicated by the table.

---

# 12. Scientific Interpretation

**What this strengthens.** It removes a specific and reasonable reviewer objection: that
the robustness result is an artifact of a particular similarity threshold. Across the two
neighbouring family definitions the ordering never reverses, the paired effect stays
positive, and every one of the 18 per-seed family-clustered intervals stays above zero. The
reproduction check is also unusually strong — the frozen family construction is reproduced
bitwise at three thresholds, and the evaluated row population is proven invariant to θ, so
the three conditions are genuinely comparable rather than three different datasets. A
secondary strengthening: under Tier B the 64-query budget exceeds the 48-sequence action
space, so these ASRs are exact optima over the audited action space rather than
search-limited estimates.

**What this does not establish.** It does not show that absolute numbers are threshold-free;
they are not, and the paired effect varies by up to 40% of its largest value across the
range tested. It does not extend beyond the 0.80–0.90 neighbourhood — a materially different
family notion (say 0.50, or a non-opcode similarity) is untested. It does not address query
budget, and it is not a test of a stronger adversary: the exhaustiveness result is a
statement about *this* action space at depth ≤ 4, not about attackers in general. It says
nothing about label quality, since all thresholds inherit the same source-flagged /
unflagged labels. Finally, it does not establish that AuthGuard's clean advantage is real —
that remains small and threshold-dependent.

**Is the 0.85 choice consequential?** For the robustness conclusion, no. The conclusion
holds at all three thresholds, and 0.85 is neither the most favourable (0.80 gives a larger
effect) nor structurally unusual (family counts, singleton share, and component sizes all
vary smoothly through it). For the clean-performance conclusion, mildly yes: the claim that
clean AUPRC does not statistically separate the two models holds at 0.80 and 0.85 but fails
at 0.90, so that particular sentence is threshold-contingent and should be scoped to the
reference threshold.

---

# 13. Files Created

All under `revision_v2/results/family_threshold_sensitivity/`.

| File | Contents |
|---|---|
| `family_threshold_family_stats.csv` | §3 family structure per θ |
| `family_threshold_split_stats.csv` | §4 per-θ per-fold split composition and disjointness |
| `family_threshold_similarity_stats.csv` | §5 residual-similarity distribution per θ |
| `family_threshold_clean_results.csv` | §7 clean aggregates per θ/model |
| `family_threshold_clean_per_fold.csv` | clean metrics per θ/seed/fold/model |
| `family_threshold_clean_contrasts.csv` | §7.1 paired clean contrasts |
| `family_threshold_attack_results.csv` | §8 per θ/seed/model attack outcomes |
| `family_threshold_attack_aggregate.csv` | §8 aggregated over seeds |
| `family_threshold_paired_contrasts.csv` | §9 per-seed, seed-level, and seed-averaged contrasts |
| `family_threshold_compact_table.csv` | §11 candidate manuscript table |
| `family_threshold_internal_table.csv` | §11 second internal table |
| `family_threshold_summary.json` | everything above plus commit, config, file map |
| `family_threshold_structure.json` | §1–§3 audit, reproduction, merge and giant-component analysis |
| `family_threshold_action_verification.json` | §6.1 post-run Tier-B verification per run |
| `family_threshold_action_space_enumeration.json` | §8.1 sequence-space enumeration |
| `family_threshold_seed_replication.json` | §15.1 seed-independence check per θ/model |
| `family_manifest_theta0{80,85,90}.csv` | family assignment over the full clustering corpus |
| `split_manifest_theta0{80,85,90}.csv` | family/fold assignment for every benchmark row |
| `residual_similarity_theta0{80,85,90}.csv` | per-observation nearest-training similarity |
| `clean_per_fold_theta0XX_s77YY.csv` (9) | clean metrics per run |
| `clean_predictions_theta0XX_s77YY.csv.gz` (9) | per-observation clean scores, labels, families |
| `tierb_action_audit_theta0XX_s77YY.json` (9) | pre-run Tier-B validation |
| `minhash_signatures_cache.npz` | 128-perm signatures for the 3,258-row corpus |
| `family_threshold_report.md` | this report |

Attack artifacts in `revision_v2/results/adaptive_attacks_v2/`, threshold- and seed-bearing:
`attack_per_row_theta0XX_s77YY.csv.gz`, `thresholds_theta0XX_s77YY.csv`,
`donor_ledger_theta0XX_s77YY.csv.gz`, `adaptive_attack_v2_results_theta0XX_s77YY.json`
(9 each).

**Filename-collision defect.** `run_adaptive_attacks_v2.py` derives output names from
`--tag` alone and ignores `--seed`. Every run therefore used a tag carrying both threshold
and seed (`theta085_s7703`). All 9 attack files, 9 clean-metric files, and 9 prediction
files were verified before analysis to contain exactly one θ, exactly one seed matching the
filename, and all five folds; the analyzer hard-fails otherwise.

Scripts: `revision_v2/experiments/family_threshold_sensitivity/{build_family_thresholds.py,
run_theta_experiment.py, analyze_family_threshold.py}`.

---

# 14. Reproduction Commands

```bash
# Steps 0-4: audit, reproduce theta=0.85, build families/splits, residual similarity.
# Exits non-zero if the 0.85 reproduction or any leakage check fails.
python3 revision_v2/experiments/family_threshold_sensitivity/build_family_thresholds.py

# Verify the Tier-B restriction and theta wiring without running anything expensive
python3 revision_v2/experiments/family_threshold_sensitivity/run_theta_experiment.py \
    --theta 0.85 --seed 7702 --validate-only

# Steps 5-7: retrain + Tier-B attack, 9 runs, ~1,130 s each
for t in 0.80 0.85 0.90; do
  for s in 7702 7703 7704; do
    python3 revision_v2/experiments/family_threshold_sensitivity/run_theta_experiment.py \
        --theta $t --seed $s --folds 0 1 2 3 4 --budget 64
  done
done

# Steps 6, 8, 11: clean, adaptive, paired contrasts, compact table
python3 revision_v2/experiments/family_threshold_sensitivity/analyze_family_threshold.py

# Frozen-artifact guard
python3 revision_v2/experiments/common/frozen.py verify
```

Inputs (read-only): `capability_dataset.csv`, `family_assignment_frozen.csv`,
`paper_build/data_hygiene/task_aligned_dataset_v1.csv`,
`paper_build/data_hygiene/designator_audit.csv`,
`revision_v2/data/authguardbench_7702_v2.csv.gz`,
`revision_v2/experiments/baseline_v2/features_v2.npz`.

Git status at analysis time: 38 modified/untracked paths, all of them the new scripts and
new result files listed in §13. No tracked frozen artifact was modified.

---

# 15. Anomalies / Limitations / Blockers

**15.1 The 15-feature LR is bit-identical across seeds; its SD is 0 by construction.**
Verified directly: clean scores, adversarial scores, and per-source attack outcomes are
numerically identical across 7702/7703/7704 at every θ. Cause: `LogisticRegression` with
the default lbfgs solver ignores `random_state` (that parameter only affects
`sag`/`saga`/`liblinear`), and `StandardScaler` is deterministic. The attack *does* draw
different random sequences per seed — confirmed, the sequence strings differ — but the
best-of-64 outcome per source is unchanged. **Consequence: every "± .0000" in the LR rows is
determinism, not stability, and must not be reported as the LR being more reproducible than
AuthGuard-Seq.** The three seeds are genuine replicates only for AuthGuard-Seq. Recorded per
θ/model in `family_threshold_seed_replication.json`. No fix applied: changing the solver
would alter the frozen training protocol.

**15.2 θ=0.85 has the widest interval and the largest across-seed spread.** The seed-averaged
beam CI at 0.85 is [+.0858, +.4949], against [+.2502, +.4597] at 0.80 and [+.1574, +.3563]
at 0.90; across-seed SD is .0962 versus .0273 and .0101. The driver is seed 7703, where
AuthGuard's paired ASR was .2619 against .0664 and .0781 in the other two seeds — roughly a
four-fold difference from training stochasticity alone. This is reported rather than
smoothed: it means the reference threshold's effect estimate is the least precise of the
three, though still bounded away from zero.

**15.3 Training is not bitwise reproducible for AuthGuard-Seq.** `set_seed` calls
`torch.use_deterministic_algorithms(False)` and training runs on CUDA, so re-running a seed
gives a different model. Cross-θ comparisons of *marginal* quantities therefore conflate the
family definition with training variation. The paired contrasts in §9 are unaffected, since
both models are compared within the same run on a common population. The training recipe
was not modified to force determinism.

**15.4 Random search is exhaustive under Tier B.** As quantified in §8.1, the 64-query
budget exceeds the 48-sequence action space. This strengthens the ASR interpretation but
means the "query budget" is not a binding constraint in the Tier-B setting, so these results
say nothing about how the models would compare under a budget small enough to matter. Any
future query-budget sensitivity study should account for this.

**15.5 Fixed comparators are not action-restricted.** `M2`, `M3` and `fixed_oracle_best` are
generated outside the search and still use address/selector rewriting. They are preserved in
the raw records and excluded from every statistic here.

**15.6 Clean-detection rates move with θ, changing eligible denominators.** AuthGuard's
clean-detection rate is .8670 / .9023 / .8675 and the LR's is .8432 / .7510 / .7758, so the
paired eligible population is not constant across thresholds (549 / 532 / 499 sources). The
paired estimator handles this correctly by construction — every contrast is computed on the
population both models detect within that condition — but marginal ASRs across thresholds
are not strictly like-for-like.

**15.7 Scope.** θ = 0.80 was not previously frozen and had to be constructed; 0.75 was
recomputed only as a pipeline check and is not part of the sensitivity claim. Query-budget
sensitivity was not run. RQ4 parameter-matched controls were not re-run. No new models were
added. The manuscript and LaTeX sources were not touched.

**15.8 Terminology.** Positives are *source-flagged* delegates and the task is *structural
screening*. These are not malicious/benign ground-truth labels, and nothing here should be
read as such.

**Blockers: none.** All STOP conditions were checked and cleared — 0.85 reproduced exactly,
the pipeline changed only in the similarity threshold, no family or exact-bytecode leakage
was detected, no giant component appeared, and the Tier-B restriction verified in all nine
runs both before and after execution.
