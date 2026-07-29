# Model Candidate Report — Revision v3 Phase 1

Four exploratory model-strengthening candidates, evaluated under the identical canonical
protocol used for `authguard_reference_v3` (chunk_size=256, max_chunks=64 — full uncapped
budget), with one common predefined training configuration (no test-driven or per-candidate
hyperparameter tuning; the second-configuration escape hatch in the audit brief was not
triggered — no candidate showed a validation-visible optimization failure). Full data:
`revision_v3/results/model_candidate_summary.csv`, `model_candidate_fold_seed.csv` (60 rows =
4 models × 5 folds × 3 seeds), `model_candidate_predictions.csv.gz`,
`model_candidate_bootstrap.csv` (each candidate vs. `authguard_reference_v3`, same
family-clustered paired bootstrap method as `CONTROLLED_ABLATION_REPORT.md`).

These are explicitly **not** architectural ablations — they exist to give the model a
legitimate chance to beat the plain sequence-only reference by combining views.

## 1. Descriptive results

| Model | AUPRC | Recall@5% FPR | Active params |
|---|---:|---:|---:|
| **authguard_reference_v3** (baseline for comparison) | 0.929 ± 0.015 | 0.843 ± 0.014 | 38,562 |
| authguard_multiscale (attention+mean+max concat) | 0.917 ± 0.011 | 0.856 ± 0.021 | 59,234 |
| authguard_sequence_dense (+ structural/histogram view) | 0.929 ± 0.011 | 0.841 ± 0.009 | 97,645 |
| authguard_sequence_ngram (+ hashed 4-gram view) | 0.870 ± 0.009 | 0.833 ± 0.024 | 130,276 |
| authguard_all_views (+ both) | 0.879 ± 0.002 | 0.828 ± 0.031 | 181,103 |

(Per-seed SDs in `model_candidate_summary.csv`.) By point estimate, `authguard_sequence_dense`
is essentially tied with the reference model; `authguard_multiscale` is close; the two
n-gram-containing candidates (`sequence_ngram`, `all_views`) score visibly lower.

## 2. Family-clustered paired bootstrap vs. authguard_reference_v3

| Candidate | ΔAUPRC [95% CI] | Excludes 0? | ΔRecall@5% [95% CI] | Excludes 0? |
|---|---:|:---:|---:|:---:|
| authguard_multiscale | −0.010 [−0.049, +0.029] | No | +0.009 [−0.025, +0.048] | No |
| authguard_sequence_dense | +0.012 [−0.014, +0.040] | No | −0.006 [−0.047, +0.040] | No |
| authguard_sequence_ngram | −0.029 [−0.066, +0.007] | No | −0.018 [−0.062, +0.025] | No |
| authguard_all_views | −0.035 [−0.079, +0.006] | No | −0.026 [−0.076, +0.022] | No |

**Every single comparison's confidence interval crosses zero.** None of the four exploratory
candidates is statistically distinguishable from the plain sequence-only reference model on
either metric — including in the negative direction: even the numerically weakest candidates
(`sequence_ngram`, `all_views`) are not *significantly* worse, given family-clustered sampling
variance.

## 3. Answers

- **Strongest clean model (by point estimate)**: `authguard_sequence_dense` (AUPRC 0.929,
  statistically tied with the reference). No candidate significantly beats the reference.
- **Most stable model**: judged by AUPRC dispersion across all 15 individual fold-seed runs
  (not just the 3 seed-level means, which averaging over folds can make deceptively smooth):
  `authguard_multiscale` has the tightest spread (fold-level SD 0.029, range 0.831–0.952) —
  less than half the reference model's fold-level SD (0.067, range 0.727–0.981). The
  n-gram-containing candidates are the least stable (`authguard_sequence_ngram` SD 0.115,
  range 0.619–0.982; `authguard_all_views` SD 0.092, range 0.659–0.965), consistent with the
  hashed 4-gram view adding capacity without adding signal on this benchmark. (The
  seed-level-mean SDs in `model_candidate_summary.csv` are a much noisier stability signal
  with only 3 data points each and should not be read as contradicting this — e.g.
  `authguard_all_views`'s 3 seed means happen to average out close together despite wide
  fold-to-fold swings within each seed.)
- **Simplest model**: `authguard_reference_v3` itself (38,562 active parameters) — every
  hybrid adds parameters (up to 4.7× more for `authguard_all_views`) without a supported gain.
- **Best low-FPR recall**: `authguard_multiscale` has the highest point estimate (0.856 vs.
  0.843) but the delta vs. reference is not significant (CI crosses zero) — cannot be claimed
  as a real improvement.
- **Do hybrid features provide a statistically supported gain?** **No.** Every comparison's
  CI includes zero. Adding structural, n-gram, or multiscale-pooling views to the sequence
  representation neither helps nor measurably hurts on this benchmark's clean primary task —
  the extra parameters (up to 181,103 active, vs. 38,562 for the plain reference) buy nothing
  measurable here.
- **Should the sequence-only model remain the paper's main model?** Yes, on the evidence in
  this report: it is the simplest model with no candidate showing a statistically supported
  clean-task advantage. (Matched-budget robustness results in `MATCHED_ROBUSTNESS_REPORT.md`
  are a separate consideration for the final decision — see
  `PHASE1_MODEL_DEFENSIBILITY_REPORT.md`'s decision table.)

## 4. Threats and caveats

- One common training configuration was used for all four candidates; a candidate-specific
  hyperparameter sweep (larger dropout for the higher-parameter hybrids, a lower learning rate
  for `authguard_all_views`, etc.) was explicitly out of scope for this pass and might change
  these point estimates — but per the audit brief, this was only to be attempted if validation
  results showed a clear optimization failure, which none did (all four candidates converged
  within the 30-epoch/patience-5 budget on every fold-seed).
- `authguard_multiscale`'s single-view gate has a structural dead-parameter issue (documented
  in `PARAMETER_ACCOUNTING_REPORT.md` §3) that does not affect its measured performance (the
  gate's output is a constant, not a source of error) but means its "59,299 total parameters"
  figure overstates its active capacity by 65 parameters — immaterial here, noted for
  completeness.
