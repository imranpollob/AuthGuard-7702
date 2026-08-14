# RQ4 Parameter-Matched Aggregation Controls — Tier-B Action Space Only

Three-seed replication (7702 / 7703 / 7704) of the RQ4 parameter-matched aggregation
experiment with the adaptive attacker restricted to the Tier-B (audit-supported)
transformation classes.

- Repository commit: `11b64575c1434553776250849da52b06013c7c8f`
- Output directory: `revision_v2/results/rq4_replication_3seed_tierb/`
- The completed full-eight-action replication in `revision_v2/results/rq4_replication_3seed/`
  was **not** re-run, altered, or overwritten. It is read read-only in Section 6.
- Frozen-artifact guard re-verified during this work: `OK: 144 frozen files verified unchanged`.

---

## 1. Tier-B action-space verification

### 1.1 Action list

| | Actions |
|---|---|
| Full eight-action space (unchanged experiment) | `metadata`, `address`, `selector`, `neutral25`, `flood25`, `flood50`, `flood100`, `flood200` |
| **Tier-B space used here** | `metadata`, `neutral25`, `flood25`, `flood50`, `flood100`, `flood200` |
| Excluded | `address` (address-immediate rewriting), `selector` (selector rewriting) |

### 1.2 How the restriction was applied

The restriction lives entirely in a new isolated entry point,
`revision_v2/experiments/rq4_replication/run_rq4_tierb.py`. It patches the `ACTIONS`
global of the shared `search` module in the loaded process and then delegates to the
existing runner's own `main()`. **No shared attack code, runner, architecture, training
routine, threshold procedure, split, or statistical routine was modified.** Every other
constraint continues to be enforced by exactly the same code that produced the
full-action replication.

`FLOOD_ACTIONS` was deliberately left untouched, so the "at most one flooding action"
rule, the depth limit, the query budget, the byte-overhead budget, donor isolation, the
threshold fitting, and the success definition all remain as they were.

### 1.3 Pre-run validation (Step 1) — 12/12 checks passed, per seed

Saved to `tierb_action_audit_s7702.json`, `..._s7703.json`, `..._s7704.json`.

| Check | Result |
|---|---|
| Action list is exactly the Tier-B set | PASS |
| `address` excluded | PASS |
| `selector` excluded | PASS |
| Random search cannot sample `address`/`selector` (exhaustive enumeration of emitted sequences) | PASS |
| Random search respects max depth | PASS |
| Random search respects the one-flooding rule | PASS |
| Beam search cannot expand `address`/`selector` (closure over depth-4 expansion) | PASS |
| Query budget is 64 | PASS |
| Beam width is 4 | PASS |
| Max depth is 4 | PASS |
| Byte-overhead cap is 2.0 | PASS |
| Flood levels unchanged (25/50/100/200) | PASS |

### 1.4 Post-run verification against the produced records

Stronger than the pre-run audit, because it inspects what the attack actually emitted
rather than what it was configured to emit. Saved to `tierb_sequence_verification.json`.

Every `random_search` / `beam_search` record in all three seeds was parsed and its action
composition decomposed:

| Seed | Searched rows | Distinct actions actually used | Tier-C actions observed |
|---|---|---|---|
| 7702 | 4,362 | `flood100`, `flood200`, `flood25`, `flood50`, `metadata`, `neutral25` | none |
| 7703 | 4,362 | `flood100`, `flood200`, `flood25`, `flood50`, `metadata`, `neutral25` | none |
| 7704 | 4,362 | `flood100`, `flood200`, `flood25`, `flood50`, `metadata`, `neutral25` | none |

The runner's own results JSON independently records `actions: ["metadata", "neutral25",
"flood25", "flood50", "flood100", "flood200"]` for each seed.

### 1.5 What the restriction does *not* govern (important)

The fixed comparator conditions `M2` and `M3` are **not** produced by the search. They are
built by `make_variant_isolated()` in `revision_v2/experiments/donor_pools/pools.py`
(lines 170–183), which calls `mut_addr_immediates` and `mut_selector_rewrite` directly and
never reads `search.ACTIONS`. Consequently each raw output file still contains `M1`, `M2`,
`M3`, `F25`–`F200` and `fixed_oracle_best` rows, and the `M2`/`M3`/`fixed_oracle_best`
rows may use Tier-C transformations.

These rows are **preserved in the raw records** (17,448 rows per seed) and are **excluded
from every Tier-B statistic** in this report. All marginal ASRs, strongest-attack
statistics, robust recall, and paired contrasts below are computed over
`random_search` and `beam_search` only — which is exactly the population the full-action
replication used, so Section 6 compares like with like.

---

## 2. Experimental configuration

| Item | Value |
|---|---|
| Seeds | 7702, 7703, 7704 |
| Folds | 0, 1, 2, 3, 4 (family-disjoint) |
| Models | `chunk_attention_16384`, `chunk_mean_16384`, `flat_control_16384` |
| Trainable parameters (counted directly from the instantiated modules) | attention 30,050; mean 29,985; flat 29,985 |
| Positive observations attacked | 727 per seed |
| Search methods analysed | random search, beam search |
| Query budget | 64 |
| Beam width | 4 |
| Max composition depth | 4 |
| Max byte overhead | 2.0× |
| Flooding rule | at most one flooding action per sequence |
| Operating point | nominal 5% FPR fitted on validation negatives, per fold, per model |
| Bootstrap | family-clustered percentile bootstrap, 10,000 replicates |
| Epochs | 30 (runner default, unchanged) |
| Environment | Python 3.12.12, torch 2.9.0+cu128, numpy 2.3.4, pandas 2.3.3, CUDA device |
| Wall time | seed 7702: 1,308 s; seed 7703: 1,331 s; seed 7704: not captured (the monitor expired mid-run), artifact timestamps place it at ≈23 min |

Splits, checkpoints, tokenisation, donor pools, and threshold fitting are produced by the
same runner invocation as in the full-action replication; nothing was reused across the
two experiments and nothing was reused across seeds.

---

## 3. Results by seed

Marginal ASR is over each model's own cleanly-detected observations at its own fold
threshold. Robust recall is over **all** 727 positive observations.

| Seed | Architecture | Params | Clean detect. | Eligible obs. | Eligible fam. | Rand. succ. | Random ASR | Beam succ. | Beam ASR | Robust recall | Invalid | Failed | Queries |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 7702 | Chunk attention | 30,050 | .8583 | 624 | 186 | 61 | **.0978** | 44 | **.0705** | **.7744** | 0 | 1,143 | 42,440 |
| 7702 | Chunk mean | 29,985 | .7758 | 564 | 176 | 555 | .9840 | 524 | .9291 | .0124 | 0 | 49 | 42,181 |
| 7702 | Flat control | 29,985 | .8308 | 604 | 191 | 533 | .8825 | 413 | .6838 | .0977 | 0 | 262 | 42,326 |
| 7703 | Chunk attention | 30,050 | .8239 | 599 | 185 | 52 | **.0868** | 45 | **.0751** | **.7524** | 0 | 1,101 | 42,230 |
| 7703 | Chunk mean | 29,985 | .7827 | 569 | 174 | 559 | .9824 | 529 | .9297 | .0138 | 0 | 50 | 42,223 |
| 7703 | Flat control | 29,985 | .8116 | 590 | 181 | 486 | .8237 | 406 | .6881 | .1431 | 0 | 288 | 42,314 |
| 7704 | Chunk attention | 30,050 | .9257 | 673 | 188 | 61 | **.0906** | 41 | **.0609** | **.8418** | 0 | 1,244 | 42,514 |
| 7704 | Chunk mean | 29,985 | .7909 | 575 | 180 | 564 | .9809 | 524 | .9113 | .0151 | 0 | 62 | 42,207 |
| 7704 | Flat control | 29,985 | .8157 | 593 | 186 | 530 | .8938 | 461 | .7774 | .0867 | 0 | 195 | 42,311 |

Per-fold validation thresholds (5% FPR), by seed and model:

| Seed | Architecture | Thresholds (folds 0–4, sorted) |
|---|---|---|
| 7702 | Chunk attention | .3088, .3549, .4094, .4665, .8459 |
| 7702 | Chunk mean | .3834, .4857, .5737, .6939, .7594 |
| 7702 | Flat control | .2271, .3341, .4467, .6439, .7071 |
| 7703 | Chunk attention | .3285, .3712, .3884, .5474, .6385 |
| 7703 | Chunk mean | .4558, .6390, .6770, .7649, .7989 |
| 7703 | Flat control | .3018, .3925, .6568, .6945, .7999 |
| 7704 | Chunk attention | .2745, .3431, .4468, .4630, .9165 |
| 7704 | Chunk mean | .4783, .5423, .5809, .6540, .7804 |
| 7704 | Flat control | .2970, .4662, .7044, .7880, .7953 |

**Invalid attack records: zero in all nine seed × model cells.** Failed (unsuccessful)
records are retained, not discarded; they are the complement of the successes within the
eligible population across both search methods.

---

## 4. Three-seed summary

Mean ± SD across the three seed-level point estimates (n = 3 seeds; SD is a
three-point dispersion, not a confidence interval).

| Architecture | Params | Clean detection | Random ASR | Beam ASR | Robust recall |
|---|---|---|---|---|---|
| Chunk attention | 30,050 | .8693 ± .0423 | **.0917 ± .0045** | **.0689 ± .0059** | **.7895 ± .0380** |
| Chunk mean | 29,985 | .7831 ± .0062 | .9824 ± .0013 | .9234 ± .0085 | .0138 ± .0011 |
| Flat control | 29,985 | .8193 ± .0083 | .8666 ± .0307 | .7164 ± .0431 | .1091 ± .0244 |

The three architectures are within 65 parameters of each other, so the separation is not
attributable to capacity.

---

## 5. Paired robustness contrasts

All contrasts are computed on the **common cleanly-detected population** — observations
that *both* compared models detect on clean input — never by subtracting marginal ASRs.
95% CIs are family-clustered percentile bootstrap, 10,000 replicates.

### 5.1 Per-seed effects

| Seed | Contrast | Method | Left ASR | Right ASR | Effect | 95% CI | Excl. 0 | Paired obs. | Families |
|---|---|---|---|---|---|---|---|---|---|
| 7702 | chunk_mean − chunk_attention | random | .9834 | .0869 | +.8965 | [+.8220, +.9527] | yes | 541 | 167 |
| 7702 | chunk_mean − chunk_attention | beam | .9261 | .0628 | +.8632 | [+.8022, +.9150] | yes | 541 | 167 |
| 7702 | flat_control − chunk_attention | random | .8791 | .0760 | +.8031 | [+.7383, +.8609] | yes | 579 | 179 |
| 7702 | flat_control − chunk_attention | beam | .6788 | .0518 | +.6269 | [+.5653, +.6964] | yes | 579 | 179 |
| 7703 | chunk_mean − chunk_attention | random | .9815 | .0830 | +.8985 | [+.8309, +.9476] | yes | 542 | 164 |
| 7703 | chunk_mean − chunk_attention | beam | .9262 | .0720 | +.8542 | [+.7871, +.9074] | yes | 542 | 164 |
| 7703 | flat_control − chunk_attention | random | .8131 | .0526 | +.7604 | [+.6756, +.8377] | yes | 551 | 170 |
| 7703 | flat_control − chunk_attention | beam | .6697 | .0490 | +.6207 | [+.5197, +.7104] | yes | 551 | 170 |
| 7704 | chunk_mean − chunk_attention | random | .9796 | .0465 | +.9331 | [+.9010, +.9575] | yes | 538 | 170 |
| 7704 | chunk_mean − chunk_attention | beam | .9052 | .0316 | +.8736 | [+.8247, +.9198] | yes | 538 | 170 |
| 7704 | flat_control − chunk_attention | random | .8908 | .0537 | +.8371 | [+.7561, +.9025] | yes | 577 | 177 |
| 7704 | flat_control − chunk_attention | beam | .7712 | .0381 | +.7331 | [+.6478, +.8095] | yes | 577 | 177 |

**12 of 12 per-seed CIs exclude zero, all in the same direction.**

### 5.2 Seed-level mean ± SD

| Contrast | Method | Mean | SD | Min seed | Max seed | All positive | All CIs excl. 0 |
|---|---|---|---|---|---|---|---|
| chunk_mean − chunk_attention | random | +.9094 | .0168 | +.8965 | +.9331 | yes | yes |
| chunk_mean − chunk_attention | beam | +.8637 | .0079 | +.8542 | +.8736 | yes | yes |
| flat_control − chunk_attention | random | +.8002 | .0314 | +.7604 | +.8371 | yes | yes |
| flat_control − chunk_attention | beam | +.6602 | .0516 | +.6207 | +.7331 | yes | yes |

### 5.3 Family-clustered seed-averaged estimate

Per-source differences are averaged across the seeds in which both models detect the
source cleanly, and the family-clustered bootstrap is then applied to those per-source
values. Repeated seed evaluations of the same source are **not** treated as independent
observations.

| Contrast | Method | Effect | 95% CI | Excl. 0 | Sources | Families |
|---|---|---|---|---|---|---|
| chunk_mean − chunk_attention | random | **+.8812** | [+.8129, +.9325] | yes | 599 | 184 |
| chunk_mean − chunk_attention | beam | **+.8484** | [+.7954, +.8935] | yes | 599 | 184 |
| flat_control − chunk_attention | random | **+.7794** | [+.7153, +.8361] | yes | 627 | 190 |
| flat_control − chunk_attention | beam | **+.6486** | [+.5841, +.7104] | yes | 627 | 190 |

---

## 6. Comparison with the full eight-action replication

Full-action values are read read-only from `revision_v2/results/rq4_replication_3seed/`.

### 6.1 Marginals (three-seed means)

| Architecture | Metric | Tier B | Full 8-action | Δ (B − full) |
|---|---|---|---|---|
| Chunk attention | Random ASR | .0917 ± .0045 | .0997 ± .0225 | −.0079 |
| Chunk attention | Beam ASR | .0689 ± .0059 | .0772 ± .0133 | −.0083 |
| Chunk attention | Clean detection | .8693 ± .0423 | .8386 ± .0068 | +.0307 |
| Chunk attention | Robust recall | .7895 ± .0380 | .7542 ± .0260 | +.0353 |
| Chunk mean | Random ASR | .9824 ± .0013 | .9923 ± .0047 | −.0098 |
| Chunk mean | Beam ASR | .9234 ± .0085 | .9393 ± .0127 | −.0159 |
| Chunk mean | Clean detection | .7831 ± .0062 | .7707 ± .0069 | +.0124 |
| Chunk mean | Robust recall | .0138 ± .0011 | .0046 ± .0017 | +.0092 |
| Flat control | Random ASR | .8666 ± .0307 | .8800 ± .0304 | −.0133 |
| Flat control | Beam ASR | .7164 ± .0431 | .7294 ± .0355 | −.0130 |
| Flat control | Clean detection | .8193 ± .0083 | .8180 ± .0091 | +.0014 |
| Flat control | Robust recall | .1091 ± .0244 | .0922 ± .0237 | +.0170 |

### 6.2 Seed-averaged paired contrasts

| Contrast | Method | Tier B | Full 8-action | Δ | Both excl. 0 |
|---|---|---|---|---|---|
| chunk_mean − chunk_attention | random | +.8812 [+.8129, +.9325] | +.8844 [+.8314, +.9274] | −.0032 | yes |
| chunk_mean − chunk_attention | beam | +.8484 [+.7954, +.8935] | +.8555 [+.8068, +.8954] | −.0071 | yes |
| flat_control − chunk_attention | random | +.7794 [+.7153, +.8361] | +.7852 [+.7278, +.8389] | −.0058 | yes |
| flat_control − chunk_attention | beam | +.6486 [+.5841, +.7104] | +.6512 [+.5818, +.7130] | −.0027 | yes |

The four paired effects differ by at most 0.0071 between the two action spaces, and the
CIs overlap almost completely.

### 6.3 Answers to the seven questions

**1. Does chunk attention remain less vulnerable than chunk mean for every seed under
Tier B?**
Yes. Marginally, for all three seeds and both search methods (random: .0978/.0868/.0906
vs .9840/.9824/.9809; beam: .0705/.0751/.0609 vs .9291/.9297/.9113). In the paired
analysis, all six per-seed chunk_mean − chunk_attention effects are positive with CIs
excluding zero.

**2. Does chunk attention remain less vulnerable than flat for every seed?**
Yes. Marginally, for all three seeds and both methods (random: vs .8825/.8237/.8938;
beam: vs .6838/.6881/.7774). In the paired analysis, all six per-seed
flat_control − chunk_attention effects are positive with CIs excluding zero.

**3. Do all paired effects remain positive?**
Yes. All 12 per-seed effects, all 4 seed-level means, and all 4 family-clustered
seed-averaged estimates are positive. No sign reversal occurs in any cell.

**4. Do the family-clustered CIs exclude zero?**
Yes. 12 of 12 per-seed CIs and 4 of 4 seed-averaged CIs exclude zero. The narrowest
margin between a CI lower bound and zero is +.5197 (flat − attention, beam, seed 7703).

**5. Does the mechanism ordering remain the same under Tier B and the broader attack
space?**
Yes. Under both action spaces the ordering by vulnerability is
`chunk_mean` > `flat_control` > `chunk_attention`, on both search methods, in every seed,
and in both the marginal and paired analyses. Robust recall preserves the same ordering
in reverse (attention .7895, flat .1091, mean .0138 under Tier B; .7542, .0922, .0046
under the full space).

**6. How much do absolute ASRs change when address/selector rewrites are removed?**
Little, and always in the direction of a slightly weaker attacker. Across the six
architecture × method cells the three-seed mean ASR falls by between 0.79 and 1.59
percentage points (attention −0.79 random / −0.83 beam; mean −0.98 / −1.59;
flat −1.33 / −1.30). **This estimate is confounded** — see §10.1: the Tier-B run retrained
its own models, and GPU training is not bitwise reproducible in this codebase, so the
cross-run marginal deltas mix the action-space effect with training variation. The
per-seed spread from training variation alone is of comparable magnitude (e.g. flat-control
random ASR ranges .8237–.8938 across seeds *within* Tier B). The paired contrasts in
§6.2, which are computed within a single run against a same-run reference model, are the
sounder basis for comparison: there the two action spaces differ by ≤0.0071.

**7. Does the evidence support saying that the selective-aggregation advantage persists
under both the primary audit-supported adversary and the broader stress test?**
Yes, and the support is direct rather than inferred. The claim holds under the Tier-B
(audit-supported) adversary on its own evidence: 12/12 per-seed paired CIs exclude zero,
effects range +.6207 to +.9331, and robust recall is .7895 for chunk attention versus
.1091 and .0138 for the parameter-matched controls. It independently holds under the full
eight-action space in the prior replication. The two agree to within 0.0071 on the
seed-averaged paired effects. The advantage is therefore not an artifact of admitting
transformations whose execution-preservation evidence is weaker.

The one thing this comparison does **not** license is a claim that the action-space
restriction has a precisely quantified effect on absolute ASR; see Q6 and §10.1.

---

## 7. Scientific interpretation

The Tier-B restriction removes the two transformation classes whose
execution-preservation evidence is weakest, leaving an adversary composed only of
transformations with independent audit support. This is the more conservative and more
defensible threat model, and the result is that it changes nothing material.

Under this restricted adversary, three architectures matched to within 65 trainable
parameters — differing only in how per-chunk representations are aggregated — separate by
roughly 0.65 to 0.93 in attack success rate. Mean pooling collapses almost completely
(robust recall .0138); the flat control is only marginally better (.1091); selective
attention retains .7895. Because the parameter budget is held fixed, the surviving
explanation is the aggregation mechanism rather than capacity.

The comparison with the full eight-action stress test is the substantive contribution of
this run. A reviewer could reasonably have suspected that the robustness gap was
manufactured by the Tier-C actions — that attention looked robust mainly because address
and selector rewriting happened to be the transformations it handled well. That
hypothesis is not supported. Removing both actions moves the seed-averaged paired effects
by at most 0.0071 and leaves every CI excluding zero.

Two limits on what this establishes. First, this is a query-budgeted score-aware attack at
64 queries; a stronger or better-resourced adversary is not covered. Second, the
experiment compares aggregation mechanisms under a shared protocol — it is evidence about
*why* the architecture is more robust, not a claim that the absolute robust recall of
.7895 is adequate for deployment.

---

## 8. Machine-readable files created

All in `revision_v2/results/rq4_replication_3seed_tierb/`:

| File | Contents |
|---|---|
| `rq4_tierb_per_seed.csv` | Section 3, one row per seed × model |
| `rq4_tierb_contrasts.csv` | Section 5: per-seed, seed-level mean ± SD, and family-clustered seed-averaged contrasts |
| `rq4_tierb_aggregate.csv` | Section 4 three-seed summary |
| `rq4_tierb_vs_full_action.csv` | Section 6.1 marginal comparison |
| `rq4_tierb_summary.json` | Everything above plus commit, config, source-file map, sequence verification |
| `tierb_action_audit_s{7702,7703,7704}.json` | Section 1.3 pre-run validation, per seed |
| `tierb_sequence_verification.json` | Section 1.4 post-run verification, per seed |
| `raw_attack_per_row_tierb_s{7702,7703,7704}.csv.gz` | Preserved raw attack records, seed-specific filenames, 21,810 rows each |
| `rq4_tierb_report.md` | This report |

Primary run artifacts (seed-bearing tags, in `revision_v2/results/adaptive_attacks_v2/`):
`attack_per_row_tierb_s{seed}.csv.gz`, `thresholds_tierb_s{seed}.csv`,
`donor_ledger_tierb_s{seed}.csv.gz`, `adaptive_attack_v2_results_tierb_s{seed}.json`.

**Filename-collision defect.** `run_adaptive_attacks_v2.py` derives output filenames from
`--tag` alone and ignores `--seed`. The wrapper therefore passes a seed-bearing tag
(`tierb_s7702`, `tierb_s7703`, `tierb_s7704`), which makes collision impossible. Every
file was verified before analysis: each contains exactly one seed value, matching its
filename, and all five folds. The analysis script hard-fails if this does not hold.

## 9. Reproduction commands

```bash
# Validate the restriction only (no attack run)
python3 revision_v2/experiments/rq4_replication/run_rq4_tierb.py --seed 7702 --validate-only

# Full three-seed run (~23 min per seed on this machine)
for s in 7702 7703 7704; do
  python3 revision_v2/experiments/rq4_replication/run_rq4_tierb.py \
      --seed $s --folds 0 1 2 3 4 --budget 64
done

# Analysis, comparison, and machine-readable outputs
python3 revision_v2/experiments/rq4_replication/analyze_rq4_tierb.py

# Frozen-artifact guard
python3 revision_v2/experiments/common/frozen.py verify
```

## 10. Anomalies and limitations

**10.1 Training is not bitwise reproducible, so cross-run marginal deltas are
confounded.** `set_seed()` calls `torch.use_deterministic_algorithms(False)` and training
runs on CUDA, so re-running the same seed produces a different trained model. Verified
directly: comparing clean scores for the same (fold, sid) between the full-action and
Tier-B runs, no model matches — maximum absolute clean-score differences reach .94
(attention, seed 7702) and .17–.78 elsewhere. The visible consequence is seed 7704 chunk
attention, whose clean detection is .9257 here versus .8308 in the full-action run.
This inflates the apparent "Tier B improves clean detection / robust recall" columns in
§6.1, which are not effects of the action restriction at all. The training recipe was
**not** modified to force determinism, per the standing rule. The paired contrasts are
unaffected: they compare models trained within the same run against a same-run reference,
which is why §6.2 is the sound comparison and §6.1 carries the caveat.

**10.2 Fixed comparators are not action-restricted.** As documented in §1.5, `M2`, `M3`
and therefore `fixed_oracle_best` still use address and selector rewriting, because they
are generated outside the search. They are preserved in the raw records and excluded from
every statistic here. A Tier-B fixed-oracle could in principle be formed from `M1` and
`F25`–`F200`, but constructing one would be a new analysis and was out of scope.

**10.3 Empty-sequence records increase under Tier B.** Rows whose best candidate is the
unmodified bytecode are recorded with `sequence = "clean_noop"`. These rose from 2 / 28 / 2
(full action, seeds 7702/7703/7704) to 159 / 35 / 36 under Tier B. Inspection confirms
these are legitimate unsuccessful attacks, not errors: adversarial score equals clean
score exactly, byte overhead is 0.0, queries were spent (16–20+), and none is counted as a
success. The direction is what a smaller action space predicts — the search more often
finds nothing that reduces the score. Seed 7702's count is high relative to the other two;
this is consistent with 10.1 (a differently-trained attention model that seed) but is not
separately explained. These records were retained, not discarded.

**10.4 Zero invalid records.** No structural-validity failures occurred in any seed or
model, so no records were dropped on validity grounds.

**10.5 Seed-level SD is a three-point dispersion.** The ± values in Sections 4 and 6.1 are
computed over three seeds and should not be read as confidence intervals. All inferential
claims rest on the family-clustered bootstrap CIs in Section 5.

**10.6 Scope.** Query budget 64, beam width 4, depth 4, and the 2× byte cap were held
fixed. Query-budget sensitivity and family-threshold sensitivity were not run, as
instructed. The manuscript and LaTeX sources were not touched.

**10.7 Terminology.** Throughout, "positives" are *source-flagged* delegates and the task
is *structural screening*. These labels are not malicious/benign ground truth, and nothing
in this report should be read as such.
