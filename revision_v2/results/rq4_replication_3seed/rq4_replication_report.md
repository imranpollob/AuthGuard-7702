# RQ4 parameter-matched robustness — three-seed replication report

Scope: replicate the existing RQ4 parameter-matched aggregation experiment for seeds 7702,
7703, 7704 without changing the experimental design. No manuscript was edited and no LaTeX
was produced.

---

# 1. Pipeline Audit

Everything below was read from repository code and artifacts, not assumed from the brief.

**Architectures.** `ControlledSequenceCNN` in
`revision_v2/experiments/long_context_ablation_v3/run_long_context_ablation_v3.py`. All three
variants share an identical encoder — `Embedding(VOCAB, 32, padding_idx=PAD)`, `Conv1d(32→64,
k=5, pad=2)`, GELU, `Conv1d(64→64, k=3, pad=2, dilation=2)`, GELU, masked max-pool over
tokens — and an identical `Linear(64→1)` risk head with dropout 0.15. They differ **only** in
the aggregation over chunks:

| Variant | Aggregation | Extra parameters |
|---|---|---|
| Chunk attention | softmax over `Linear(64→1)` chunk logits, masked | +65 (64 weights + 1 bias) |
| Chunk mean | uniform weights over valid chunks | none |
| Flat control | single chunk (`n_chunks == 1` enforced) | none |

**Parameter matching** is therefore structural, not tuned: the attention variant carries
exactly one extra 64→1 linear layer. Verified counts: attention **30,050**, mean **29,985**,
flat **29,985**.

**Representation.** `select_representation` applies each variant's declared token budget over
the whole opcode stream. Flat uses a single uniformly-subsampled window of 16,384 tokens;
chunk variants use 256-token chunks capped at `budget // 256 = 64` chunks, evenly spaced when
the program is longer.

**Training** (`train_controlled` in `run_adaptive_attacks_v2.py`): AdamW, lr 1e-3, weight
decay 1e-4, batch size 16, gradient clipping 5.0, class-weighted `BCEWithLogitsLoss` with
`pos_weight` = train-fold negative/positive ratio, at most 30 epochs, early stopping on
validation average precision with patience 5, best-AP checkpoint restored. Seeded via
`ablation.set_seed(seed + fold)`.

**Dataset and splits.** `revision_v2/data/authguardbench_7702_v2.csv.gz`, population
`PRIMARY_EVALUATION`: 2,190 rows, 727 source-flagged positives, 790 bytecode-similarity
families, five fixed family-disjoint folds via the stored `fold_id`. For test fold *f*,
validation is fold *(f+1) mod 5*, training the remaining three. Attack sources are the
held-out positives of the test fold, so 727 source-seed observations per model per seed.

**Calibration and threshold.** Temperature fitted on validation logits only
(`fusion.fit_temperature`), then `WarningPolicy.from_validation_negatives` derives the
nominal 1/5/10% FPR thresholds from validation-negative calibrated scores. Only the 5%
threshold is persisted and only it is used here. **No threshold is fitted on test data.**

**Eligibility and success.** `clean_detected = clean_score >= threshold_05`;
`attack_success = clean_detected AND adversarial_score < threshold_05`. Marginal ASR is the
mean of `attack_success` over that model's own eligible observations.

**Attack.** `revision_v2/experiments/adaptive_attacks/search.py`, unchanged. Random search
over seeded sampled action sequences and score-guided beam search (width 4, depth 4), both
under a 64-query budget. Action space `ACTIONS` = metadata, address, selector, neutral25,
flood25/50/100/200; at most one flooding action per sequence; maximum composition depth 4.
Validity requires successful disassembly, an opcode-skeleton preservation check against the
source, and `len(final) <= original*(1+MAX_OVERHEAD)+1` with `MAX_OVERHEAD = 2.0` — i.e.
appended content ≤ 2× original, final size ≤ ~3× original. Flooding donors come from
partition-isolated pools; a donor never shares the recipient's family and never crosses the
train/validation/test boundary (`pools.assert_disjoint(fold)` runs per fold).

**Confidence intervals.** Family-clustered percentile bootstrap: bytecode families resampled
with replacement, identical multiplicities applied to both members of a pair, 10,000
replicates, RNG seeded deterministically from the contrast identity.

### Two protocol discrepancies between the brief and the repository

**(a) The paired anchors in the brief are mislabelled.** The brief lists "flat minus
attention +0.710 [+0.636,+0.772]" and "chunk mean minus attention +0.838 [+0.775,+0.884]".
Recomputation shows these are contrasts against **`authguard_seq`** (the 63,266-parameter
reference configuration), not against the 30,050-parameter chunk-attention control:

| Contrast (random search, seed 7702) | Recomputed | Brief's anchor |
|---|---|---|
| flat_control − **authguard_seq** | +0.7103 [+0.6362,+0.7727] | +0.710 [+0.636,+0.772] ✔ match |
| chunk_mean − **authguard_seq** | +0.8375 [+0.7756,+0.8844] | +0.838 [+0.775,+0.884] ✔ match |
| flat_control − **chunk_attention** | +0.8322 [+0.7780,+0.8789] | — |
| chunk_mean − **chunk_attention** | +0.9363 [+0.8974,+0.9644] | — |

The genuine matched-capacity contrasts against chunk attention are **larger** than the
anchors. This is a labelling issue in the brief, not a reproduction failure. Because the
brief names "chunk attention vs. chunk mean" as the primary scientific comparison, this
report replicates the contrasts **against chunk attention**, which is also the comparison
that holds capacity fixed.

**(b) The existing RQ4 controlled run used the full eight-action space, not Tier B.** The
brief's audit list refers to "Tier-B attacks". The stored seed-7702 winning sequences contain
`address` (2,124 occurrences) and `selector` (1,196), which are Tier-C-only primitives. The
replication therefore uses the **full eight-action space**, matching the experiment as
actually run. Switching to Tier B would have changed the design.

---

# 2. Seed-7702 Reproduction Check

Recomputed from `attack_per_row_seed7702_ext.csv.gz` and from direct instantiation of the
architectures. Reference values are the brief's anchors.

| Metric | Reference | Recomputed | Difference |
|---|---:|---:|---:|
| Chunk attention — parameters | 30,050 | 30,050 | 0 |
| Chunk attention — clean detection | 0.8473 | 0.8473 | 0.0000 |
| Chunk attention — random ASR | 0.0747 | 0.0747 | 0.0000 |
| Chunk attention — beam ASR | 0.0682 | 0.0682 | 0.0000 |
| Flat control — parameters | 29,985 | 29,985 | 0 |
| Flat control — clean detection | 0.8308 | 0.8308 | 0.0000 |
| Flat control — random ASR | 0.8891 | 0.8891 | 0.0000 |
| Flat control — beam ASR | 0.7053 | 0.7053 | 0.0000 |
| Chunk mean — parameters | 29,985 | 29,985 | 0 |
| Chunk mean — clean detection | 0.7689 | 0.7689 | 0.0000 |
| Chunk mean — random ASR | 0.9857 | 0.9857 | 0.0000 |
| Chunk mean — beam ASR | 0.9231 | 0.9231 | 0.0000 |
| Paired: flat − authguard_seq (random) | +0.710 [+0.636,+0.772] | +0.7103 [+0.6362,+0.7727] | ≤0.0007 |
| Paired: chunk_mean − authguard_seq (random) | +0.838 [+0.775,+0.884] | +0.8375 [+0.7756,+0.8844] | ≤0.0006 |

**Verdict: reproduced.** Every marginal metric matches to four decimal places, and both
paired anchors reproduce once their true left/right operands are identified. Proceeded to
Step 2.

---

# 3. Experimental Configuration

| Item | Value |
|---|---|
| Seeds | 7702 (existing), 7703, 7704 (new) |
| Folds | 0–4, family-disjoint, stored `fold_id` |
| Sources per seed per model | 727 held-out source-flagged positives |
| Models | chunk_attention_16384, chunk_mean_16384, flat_control_16384 |
| Token budget | 16,384 for all three |
| Operating point | nominal 5% FPR from validation negatives |
| Attack | random search + beam search (width 4, depth 4) |
| Query budget | 64 |
| Action space | full eight actions; ≤1 flooding action; depth ≤4 |
| Byte budget | appended ≤ 2× original (final ≤ ~3×) |
| Bootstrap | family-clustered percentile, 10,000 replicates |
| Changed between runs | seed only |

Nothing was tuned for 7703/7704. Architectures, optimiser, early stopping, calibration,
thresholds, attack implementation, and statistics are byte-identical code paths.

---

# 4. Results by Seed

Marginal metrics. ASR denominators are each model's own eligible observations.

| Seed | Architecture | Params | Clean det. | Val. thresholds (5 folds) | Elig. obs | Elig. fam | Rand. succ | Random ASR | Beam succ | Beam ASR | Robust recall | Invalid | Failed | Queries |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 7702 | Chunk attention | 30,050 | .8473 | .0197–.7641 | 616 | 186 | 46 | .0747 | 42 | .0682 | .7840 | 0 | 1,144 | 59,292 |
| 7702 | Chunk mean | 29,985 | .7689 | .3804–.7841 | 559 | 176 | 551 | .9857 | 516 | .9231 | .0069 | 0 | 51 | 58,731 |
| 7702 | Flat control | 29,985 | .8308 | .2182–.7071 | 604 | 191 | 537 | .8891 | 426 | .7053 | .0894 | 0 | 245 | 58,867 |
| 7703 | Chunk attention | 30,050 | .8377 | see JSON | 609 | 187 | 58 | .0952 | 41 | .0673 | .7579 | 0 | 1,119 | 58,264 |
| 7703 | Chunk mean | 29,985 | .7799 | see JSON | 567 | 174 | 565 | .9965 | 541 | .9541 | .0028 | 0 | 28 | 58,435 |
| 7703 | Flat control | 29,985 | .8116 | see JSON | 590 | 181 | 495 | .8390 | 415 | .7034 | .1224 | 0 | 270 | 58,820 |
| 7704 | Chunk attention | 30,050 | .8308 | see JSON | 604 | 179 | 78 | .1291 | 58 | .0960 | .7208 | 0 | 1,072 | 58,631 |
| 7704 | Chunk mean | 29,985 | .7634 | see JSON | 555 | 173 | 552 | .9946 | 522 | .9405 | .0041 | 0 | 36 | 58,677 |
| 7704 | Flat control | 29,985 | .8116 | see JSON | 590 | 185 | 538 | .9119 | 460 | .7797 | .0646 | 0 | 182 | 58,648 |

Per-fold threshold values for every seed are in `rq4_replication_summary.json`.

**Clean AUPRC is not reported** because it is not computable from this pipeline's artefacts:
the attacked population consists entirely of source-flagged positives, so there are no
negatives against which to compute a precision–recall curve. The RQ4 attack protocol records
clean *detection at the operating point*, not clean AUPRC. Clean AUPRC for these variants
exists only in the separate long-context ablation experiment and is out of scope here.

**Invalid attack records: 0** in all nine model-seed cells — every candidate that reached
scoring passed structural validity. **Failed records** are eligible observations the attacker
did not evade; they are retained, not discarded, and are simply the complement of successes.

---

# 5. Three-Seed Summary

Mean ± SD across the three seed-level values (n = 3 seeds).

| Configuration | Params | Clean detection | Random ASR | Beam ASR | Robust recall |
|---|---:|---|---|---|---|
| **Chunk attention** | 30,050 | .8386 ± .0068 | **.0997 ± .0225** | **.0772 ± .0133** | **.7542 ± .0260** |
| Flat control | 29,985 | .8180 ± .0091 | .8800 ± .0304 | .7294 ± .0355 | .0922 ± .0237 |
| Chunk mean | 29,985 | .7707 ± .0069 | .9923 ± .0047 | .9393 ± .0127 | .0046 ± .0017 |

---

# 6. Paired Robustness Contrasts

All contrasts computed over the **common population** — observations that both compared
models detect cleanly — never by differencing marginal ASRs.

### Per seed (family-clustered bootstrap within seed, 10,000 replicates)

| Method | Contrast | Seed | Effect | 95% CI | n paired | Families |
|---|---|---|---:|---|---:|---:|
| random | chunk_mean − chunk_attention | 7702 | +0.9363 | [+0.8980, +0.9642] | 534 | 166 |
| random | chunk_mean − chunk_attention | 7703 | +0.9238 | [+0.8792, +0.9588] | 551 | 166 |
| random | chunk_mean − chunk_attention | 7704 | +0.8745 | [+0.7849, +0.9406] | 510 | 157 |
| random | flat_control − chunk_attention | 7702 | +0.8322 | [+0.7780, +0.8786] | 578 | 179 |
| random | flat_control − chunk_attention | 7703 | +0.7838 | [+0.7048, +0.8526] | 555 | 169 |
| random | flat_control − chunk_attention | 7704 | +0.7846 | [+0.6778, +0.8752] | 557 | 168 |
| beam | chunk_mean − chunk_attention | 7702 | +0.8764 | [+0.8327, +0.9129] | 534 | 166 |
| beam | chunk_mean − chunk_attention | 7703 | +0.9020 | [+0.8579, +0.9385] | 551 | 166 |
| beam | chunk_mean − chunk_attention | 7704 | +0.8431 | [+0.7559, +0.9142] | 510 | 157 |
| beam | flat_control − chunk_attention | 7702 | +0.6488 | [+0.5784, +0.7204] | 578 | 179 |
| beam | flat_control − chunk_attention | 7703 | +0.6505 | [+0.5566, +0.7347] | 555 | 169 |
| beam | flat_control − chunk_attention | 7704 | +0.6768 | [+0.5698, +0.7732] | 557 | 168 |

**All 12 intervals exclude zero.**

### Three-seed summaries

Two estimators are reported because the same families are evaluated under every seed, so
seed-level results are repeated measures and must not be pooled as independent rows.

**(a) Seed-level summary** — seed as the unit of replication; mean and SD of the three
per-seed family-clustered point estimates. Makes no independence assumption across seeds.

| Contrast | Method | Mean effect | SD | Range | All seeds positive | All seed CIs exclude 0 |
|---|---|---:|---:|---|---|---|
| chunk_mean − chunk_attention | random | **+0.9115** | 0.0267 | [+0.8745, +0.9363] | yes | yes |
| chunk_mean − chunk_attention | beam | **+0.8738** | 0.0241 | [+0.8431, +0.9020] | yes | yes |
| flat_control − chunk_attention | random | **+0.8002** | 0.0226 | [+0.7838, +0.8322] | yes | yes |
| flat_control − chunk_attention | beam | **+0.6587** | 0.0128 | [+0.6488, +0.6768] | yes | yes |

**(b) Family-clustered, seed-averaged estimate** — the per-observation difference is first
averaged within each source across the seeds in which both models detect it cleanly,
collapsing the repeated measurement; the family bootstrap is then applied to those collapsed
values. This respects family clustering without treating three evaluations of one family as
three independent observations.

| Contrast | Method | Effect | 95% CI | Sources | Families |
|---|---|---:|---|---:|---:|
| chunk_mean − chunk_attention | random | **+0.8844** | [+0.8314, +0.9274] | 610 | 187 |
| chunk_mean − chunk_attention | beam | **+0.8555** | [+0.8068, +0.8954] | 610 | 187 |
| flat_control − chunk_attention | random | **+0.7852** | [+0.7278, +0.8389] | 627 | 191 |
| flat_control − chunk_attention | beam | **+0.6512** | [+0.5818, +0.7130] | 627 | 191 |

The two estimators agree closely (differences ≤ 0.03), which is expected given how stable the
per-seed effects are. Estimator (b) is the recommended single number; estimator (a) is the
conservative reading. Neither is presented as a significance test beyond the interval stated.

---

# 7. Replication Assessment

**1. Is chunk-attention ASR lower than chunk-mean ASR for all three seeds?** Yes, without
exception. Random search: .0747 vs .9857, .0952 vs .9965, .1291 vs .9946. Beam: .0682 vs
.9231, .0673 vs .9541, .0960 vs .9405.

**2. Is chunk-attention ASR lower than flat-control ASR for all three seeds?** Yes. Random:
.0747 vs .8891, .0952 vs .8390, .1291 vs .9119. Beam: .0682 vs .7053, .0673 vs .7034, .0960
vs .7797.

**3. Is the direction of the paired effect consistent across all seeds?** Yes. All 12
per-seed paired contrasts are positive and all 12 CIs exclude zero.

**4. How variable are the effect sizes across seeds?** Very little. SD across seeds ranges
from 0.0128 (flat − attention, beam) to 0.0267 (chunk_mean − attention, random), against
effect sizes of 0.66–0.91 — a coefficient of variation under 4% in every case.

**5. Does any 95% CI cross zero?** No. Not one of the 12 per-seed intervals, nor any of the
four seed-averaged intervals.

**6. Does the conclusion hold for random search, beam search, or both?** Both, independently.
Random search is the stronger attacker against every configuration, so it produces the larger
contrasts, but the ordering and the exclusion of zero hold under each.

**7. Does replication strengthen, weaken, or materially change the interpretation?**
Strengthens it. The single-seed result is not an artefact: direction, ordering, and magnitude
all replicate, with small between-seed variance. One honest qualification (see Q9): seed 7702
was the most favourable of the three for chunk attention, so the replicated mean ASR is
somewhat higher than the single-seed figure.

**8. Are the replicated effect sizes still practically large?** Yes. Under the strongest
attacker the matched-capacity mean-pooling control is evaded on 99.2% of its eligible
observations while the attention control is evaded on 10.0%. End-to-end robust recall is
.7542 versus .0046 and .0922 — two orders of magnitude for chunk mean.

**9. Did any seed reveal an anomaly?** Three observations, none invalidating:

- **Chunk-attention ASR rises monotonically across seeds** (.0747 → .0952 → .1291 random
  search). Seed 7702, the originally reported seed, is the most favourable of the three. The
  three-seed mean of .0997 is ~33% higher in relative terms than the single-seed .0747,
  though still small in absolute terms. Any manuscript text quoting .0747 as *the* figure
  should move to the three-seed mean ± SD.
- **Chunk mean has systematically lower clean detection** (.7634–.7799) than both attention
  (.8308–.8473) and flat (.8116–.8308). It is therefore worse on clean data *and* far worse
  under attack; its very low robust recall reflects both.
- **Flat control shows the largest between-seed spread** in random-search ASR (.8390–.9119,
  range .073), roughly triple the spread of the other two configurations.

---

# 8. Scientific Interpretation

What the experiment supports:

> Across three independently seeded replications, holding trainable parameter count fixed at
> ~30K and the token budget fixed at 16,384, the configuration using selective (attention)
> chunk aggregation is evaded far less often by a 64-query adaptive attacker than
> configurations using uniform chunk aggregation or a single flat window. The paired
> difference is positive in every seed under both search strategies, with family-clustered
> intervals excluding zero throughout, and the effect is large: +0.88 (mean pooling) and
> +0.79 (flat) in the seed-averaged random-search estimate.

What it does **not** support:

- It is **not** a causal claim that attention *causes* robustness. The design varies the
  aggregation rule while holding capacity and encoder fixed, which rules out capacity as the
  explanation and makes aggregation the operative difference *within this comparison set*.
  It does not isolate a mechanism, exclude confounds outside the manipulated variable, or
  establish that any attention mechanism in any architecture would behave this way.
- The correct phrasing is that **selective aggregation is consistently associated with lower
  adaptive attack success**, not that attention causes robustness.
- Labels remain **source-flagged** versus **unflagged** under a structural screening rule.
  Nothing here reinterprets them as malicious or benign ground truth.
- The attacker is the evaluated eight-action, 64-query, bounded-overhead adversary. Results
  do not generalise to unevaluated adversaries, and the residual chunk-attention ASR of
  ~10% means the configuration is not immune within this threat model.

---

# 9. Manuscript-Integration Data

**Compact replacement table** (n = 3 seeds, mean ± SD, full eight-action adaptive attack,
64-query budget, nominal 5% FPR operating point):

| Configuration | Params | Clean Detection | Random ASR | Beam ASR |
|---|---:|---|---|---|
| Chunk attention | 30,050 | .8386 ± .0068 | .0997 ± .0225 | .0772 ± .0133 |
| Flat control | 29,985 | .8180 ± .0091 | .8800 ± .0304 | .7294 ± .0355 |
| Chunk mean | 29,985 | .7707 ± .0069 | .9923 ± .0047 | .9393 ± .0127 |

Optional robust-recall column: .7542 ± .0260 / .0922 ± .0237 / .0046 ± .0017.

**Compact contrast summary** (family-clustered, seed-averaged across three seeds):

| Contrast | Method | Effect | 95% CI | Direction across seeds |
|---|---|---:|---|---|
| Chunk mean − Chunk attention | random | +0.8844 | [+0.8314, +0.9274] | 3/3 positive, 3/3 CIs exclude 0 |
| Chunk mean − Chunk attention | beam | +0.8555 | [+0.8068, +0.8954] | 3/3 positive, 3/3 CIs exclude 0 |
| Flat control − Chunk attention | random | +0.7852 | [+0.7278, +0.8389] | 3/3 positive, 3/3 CIs exclude 0 |
| Flat control − Chunk attention | beam | +0.6512 | [+0.5818, +0.7130] | 3/3 positive, 3/3 CIs exclude 0 |

**Points an editor must not get wrong:**

1. These contrasts are **against chunk attention**. The previously circulated +0.710 / +0.838
   figures are contrasts against **AuthGuard-Seq (63,266 params)**, a different comparison.
   Do not mix the two families in one table without labelling the right-hand operand.
2. ASR values are **marginal** (each model's own eligible observations); contrast values are
   **paired** over the common population. They are not interchangeable and one cannot be
   derived from the other by subtraction.
3. The attack is the **full eight-action space**, not the audit-supported subset.
4. All three configurations now carry **three seeds**; no single-seed caveat is needed for
   this table.

---

# 10. Files Created

New output directory: `revision_v2/results/rq4_replication_3seed/`

| Path | Contents |
|---|---|
| `revision_v2/results/rq4_replication_3seed/rq4_replication_per_seed.csv` | one row per seed × architecture, all Step-3 metrics |
| `revision_v2/results/rq4_replication_3seed/rq4_replication_contrasts.csv` | 12 per-seed contrasts + 4 seed-averaged + 4 seed-level summaries |
| `revision_v2/results/rq4_replication_3seed/rq4_replication_aggregate.csv` | three-seed mean ± SD marginal table |
| `revision_v2/results/rq4_replication_3seed/rq4_replication_summary.json` | full configuration, thresholds, per-seed, aggregate, contrasts, provenance |
| `revision_v2/results/rq4_replication_3seed/rq4_replication_report.md` | this report |
| `revision_v2/results/rq4_replication_3seed/raw_attack_per_row_*.csv.gz` | preserved copies of the three seeds' raw records |

New code (only orchestration and statistics; no existing source file was modified):

| Path | Purpose |
|---|---|
| `revision_v2/experiments/rq4_replication/rq4_metrics.py` | metric and contrast definitions read off the existing pipeline: eligibility, marginal ASR, robust recall, family-clustered paired bootstrap |
| `revision_v2/experiments/rq4_replication/analyze_rq4_replication.py` | loads the three seeds, emits per-seed table, contrasts, aggregate, JSON summary, raw copies |

Raw run outputs (written by the existing runner, preserved under seed-bearing names):

- `revision_v2/results/adaptive_attacks_v2/attack_per_row_seed7703_rq4rep.csv.gz` (21,810 rows)
- `revision_v2/results/adaptive_attacks_v2/attack_per_row_seed7704_rq4rep.csv.gz` (21,810 rows)
- matching `donor_ledger_*`, `thresholds_*`, `adaptive_attack_v2_results_*` per seed
- seed 7702 reuses the pre-existing `attack_per_row_seed7702_ext.csv.gz`; it was not re-run
  and was not modified.

---

# 11. Reproduction Commands

```bash
cd /home/pollmix/Coding/AuthGuard-7702

# Seeds 7703 and 7704 (seed 7702 already exists as attack_per_row_seed7702_ext.csv.gz).
# NOTE: the runner names outputs from --tag only, so each seed must be renamed
# immediately after its run or the next seed overwrites it. See Section 12.
for s in 7703 7704; do
  python3 revision_v2/experiments/adaptive_attacks_v2/run_adaptive_attacks_v2.py \
    --seed $s --folds 0 1 2 3 4 --budget 64 \
    --models chunk_attention_16384 chunk_mean_16384 flat_control_16384 \
    --tag rq4rep
  cd revision_v2/results/adaptive_attacks_v2
  cp attack_per_row_rq4rep.csv.gz  attack_per_row_seed${s}_rq4rep.csv.gz
  cp donor_ledger_rq4rep.csv.gz    donor_ledger_seed${s}_rq4rep.csv.gz
  cp thresholds_rq4rep.csv         thresholds_seed${s}_rq4rep.csv
  cp adaptive_attack_v2_results_rq4rep.json adaptive_attack_v2_results_seed${s}_rq4rep.json
  cd -
done

# Analysis (per-seed metrics, contrasts, aggregate, JSON, raw copies)
python3 revision_v2/experiments/rq4_replication/analyze_rq4_replication.py

# Integrity guard, run before and after
python3 revision_v2/experiments/common/frozen.py verify   # expects: OK: 144 files
```

**Environment.** Repository commit `989ca9ca2092ee5ce31019d2a67c153352e20e1c`, branch `rq4`,
clean working tree at launch. Python 3.12.12, torch 2.9.0+cu128, CUDA 12.8, cuDNN 91002,
numpy 2.3.4, pandas 2.3.3, scikit-learn 1.7.2, xgboost 3.3.0. GPU: NVIDIA GeForce RTX 2080
SUPER. Seeds 7702 / 7703 / 7704; per-fold training seed is `seed + fold`. Wall time ≈ 1,760 s
per seed for three models across five folds.

---

# 12. Anomalies / Limitations / Blockers

**Anomalies**

1. **Output-filename collision in the existing runner (defect, not caused by this task).**
   `run_adaptive_attacks_v2.py` builds its output filename from `--tag` alone and ignores
   `--seed`, so two runs sharing a tag silently overwrite each other. Seed 7703's records were
   copied to a seed-bearing filename before seed 7704 completed; both are intact and verified
   (21,810 rows each, correct seed column). Prior multi-seed runs escaped this only because
   they used seed-bearing tags. Recommend making the runner include the seed in the filename.
2. **Seed 7702 is the most favourable of the three for chunk attention** (random-search ASR
   .0747 vs .0952 and .1291). Reporting the three-seed mean ± SD rather than the single-seed
   value is the honest correction, and it is what Section 9 supplies.
3. **Chunk mean is worse on clean data as well as under attack**, so its near-zero robust
   recall reflects both weaker clean detection and near-total evasion, not evasion alone.

**Limitations**

4. Clean AUPRC is not obtainable from this pipeline — the attacked population is all-positive.
   Only clean detection at the operating point is available here.
5. The experiment uses the full eight-action space, which includes address and selector
   rewriting; those primitives carry weaker execution-preservation evidence elsewhere in the
   project. This replication deliberately preserved the original design rather than switching
   to the audit-supported subset.
6. Training is not bit-deterministic — `torch.use_deterministic_algorithms(False)` is part of
   the original recipe and was not modified. Between-seed variation therefore includes both
   seed effects and cuDNN non-determinism, which cannot be separated here.
7. Three seeds bound the between-seed variance only loosely; the SD values are estimates from
   n = 3.
8. The result is associational within the manipulated variable, as stated in Section 8.

**Blockers**

None. All three seeds completed, the frozen-artifact guard reported `OK: 144 files unchanged`
before and after, and no existing experiment output was overwritten.
