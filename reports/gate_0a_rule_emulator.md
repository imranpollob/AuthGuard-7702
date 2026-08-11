# Gate 0A — Rule-emulator recovery

## Headline result

An L2 logistic regression over **15 hand-coded opcode features** reaches **AUPRC 0.9106** against AuthGuard-Seq's **0.9244**, and the paired family-clustered bootstrap on the difference is **−0.0211, 95% CI [−0.0780, +0.0353] — an interval spanning zero**; the emulator is statistically indistinguishable from the 181,877-parameter model while running *faster* (2.626 ms vs 4.121 ms median). This undermines the paper's central claim.

## Status

**FAIL.** The work order's decision rule is unambiguous at this threshold: emulator AUPRC ≥ 0.90 means "the rule is cheaply recoverable, AuthGuard-Seq adds nothing a decision tree does not, the model paper is dead — report and stop."

The measured value is 0.9106. I am stopping here rather than proceeding to Task 1, as instructed.

One qualification that does **not** rescue the claim but should be stated precisely: the ≥0.90 threshold is crossed by the logistic regression, not by the depth-4 decision tree (0.8614, paired Δ = −0.0673, CI [−0.1249, −0.0081], excluding zero). Against the *tree* alone the model retains a small but real margin. Against the *best* trivial model — which is what the gate specifies — it does not.

---

## Method

- **Data:** `revision_v2/data/authguardbench_7702_v2.csv.gz`, population `PRIMARY_EVALUATION` (2,190 rows, 790 families, 727 positives).
- **Splits:** stored family-disjoint `fold_id`. **Seeds:** 7702 / 7703 / 7704.
- **Aggregation:** mean of per-fold metrics, then mean over seeds — this reproduces `baseline_summary.csv`'s 0.92445 for AuthGuard-Seq exactly from the stored per-row predictions, and is therefore the only aggregation under which the two are comparable. Pooled values are reported alongside but are *not* the headline. (Pooled aggregation gives AuthGuard-Seq 0.9113 and the emulator 0.9051; the conclusion is unchanged.)
- **Thresholds:** recall@5%FPR operating points come from grouped out-of-fold predictions on the training folds only. No test data touched a threshold.
- **Comparator scores:** `revision_v2/experiments/baseline_v2/baseline_predictions.csv.gz`, model `authguard_seq`. Raw and calibrated scores give identical AUPRC (temperature scaling is monotonic).
- **CIs:** 1,998 family-clustered bootstrap replicates, multinomial family weights, paired on `sample_id`, macro-over-folds recomputed inside each replicate.

**Entry point:** `revision_v2/experiments/gate_0a_rule_emulator/run_gate_0a.py`
**Features:** `revision_v2/experiments/gate_0a_rule_emulator/emulator_features.py`
**Artifacts:** `revision_v2/results/gate_0a_rule_emulator/`

### What the emulator targets

The source rule is documented, so the emulator emulates *it* rather than a generic notion of risk. From `USENIX EIP-7702 artifact/eoa_detect/decompile/analyze.dl`, the positive-defining relation `AM_Visualize_ExternalCallInfo` fires on:

> a `CALL` or `DELEGATECALL` statement belonging — transitively through `CallGraphEdge`, via the recursive `AM_Statement_Function` — to a public function whose signature is `fallback()` or `receive()`.

The 15 features are the eight structural ones named in the work order (SELFDESTRUCT presence, hardcoded 20-byte address count, balance-sweep pattern, immutable call target, CALLER-comparison guard absence, ERC-20 selector presence, bytecode length, unique opcode count) plus seven that target the rule directly: external-call counts, dispatcher presence, fallback-path presence, fallback-reachable block count, and two variants of **fallback→external-call CFG reachability**.

The two reachability variants matter. The *precise* one resolves jump targets only from the literal PUSH immediately preceding a JUMP/JUMPI; it is conservative and recovers recall 0.448 at precision 0.845. The *over-approximate* one treats any PUSHed valid JUMPDEST in a block as a candidate successor, which is how Solidity's stack-passed return addresses actually resolve. That single boolean achieves **recall 0.996 at precision 0.760** on its own. Giving the emulator this variant is what makes the comparison fair — without it a reviewer would correctly say the emulator was handicapped.

---

## Results

### Primary comparison (macro over folds, mean over 3 seeds)

| Model | AUPRC | AUROC | Recall@5%FPR | Latency (median) |
|---|---|---|---|---|
| **AuthGuard-Seq** (181,877 params) | **0.9244** ± 0.0140 | 0.9627 | 0.8327 @ FPR 0.052 | 4.121 ms |
| **L2 logistic regression, 15 features** | **0.9106** ± 0.0000 | 0.9661 | 0.7730 @ FPR 0.050 | **2.626 ms** |
| Decision tree, depth 4, 15 features | 0.8614 ± 0.0000 | 0.9557 | 0.4553 | 2.626 ms |
| Single boolean `fallback_reaches_external_call_over` | 0.7519 | 0.9206 | n/a (see note) | 2.626 ms |
| *Provenance-only floor* (`shortcut_diagnostics.py`, `family_size`) | *0.5239* | — | — | — |

The emulator's seed SD is exactly zero: logistic regression and a fixed-depth tree are deterministic given fixed folds, so the seed only perturbs the out-of-fold threshold search. That is a property of the baseline, not a measurement error.

The single-rule row has no recall@5%FPR operating point because it is binary and its FPR is 0.157 — there is no threshold at or below 5% FPR. At its natural threshold it achieves **recall 0.9959 at FPR 0.1565**.

### Paired family-clustered bootstrap, emulator − AuthGuard-Seq (ΔAUPRC)

| Emulator | Δ AUPRC | 95% CI | Excludes zero? |
|---|---|---|---|
| **L2 logistic regression** | **−0.0211** | **[−0.0780, +0.0353]** | **No** |
| Decision tree, depth 4 | −0.0673 | [−0.1249, −0.0081] | Yes |
| Single boolean rule | −0.1877 | [−0.2596, −0.1126] | Yes |

Per the work order's own standard, AuthGuard-Seq's advantage over the logistic emulator is **not significant** — the interval includes zero, so the word is not available.

### Per-fold AUPRC

Reported per-fold as instructed, given the 2.16× prevalence spread across folds.

| Fold | Prevalence | AuthGuard-Seq | LogReg emulator | Tree (d4) | Single rule |
|---|---|---|---|---|---|
| 0 | 0.341 | 0.8369 | **0.8720** | 0.7662 | 0.7675 |
| 1 | 0.327 | **0.9342** | 0.8720 | 0.7957 | 0.6759 |
| 2 | 0.340 | 0.9334 | **0.9471** | 0.9685 | 0.8192 |
| 3 | 0.208 | **0.9560** | 0.9259 | 0.8715 | 0.6327 |
| 4 | 0.451 | **0.9616** | 0.9362 | 0.9049 | 0.8643 |

The emulator beats AuthGuard-Seq on folds 0 and 2 and loses on 1, 3, 4. The pooled gap is carried by three of five folds, not by a consistent margin.

### Error profile — do they fail on the same families?

Rank-based per-family comparison (seed 7702, `gate_0a_family_error_profile.csv`):

- AuthGuard-Seq ranks better than the emulator on **384 of 790 families** — essentially a coin flip.
- Mean per-family advantage: **−0.0088** (i.e. slightly favouring the emulator).
- Correlation between family size and AuthGuard-Seq's advantage: **r = 0.002**.

So the answer to "is AuthGuard-Seq's advantage concentrated in a handful of large families?" is **no** — it is not concentrated anywhere. The largest per-family gaps are all singleton or small benign families, which is consistent with noise rather than a systematic capability difference.

### The fitted decision tree, in full (fold 0, seed 7702)

```
|--- fallback_reaches_external_call_over <= 0.500
|   |--- class: 0
|--- fallback_reaches_external_call_over >  0.500
|   |--- n_fallback_reachable_blocks <= 8.500
|   |   |--- n_external_call_ops <= 4.500
|   |   |   |--- n_fallback_reachable_blocks <= 7.500
|   |   |   |   |--- class: 0
|   |   |   |--- n_fallback_reachable_blocks >  7.500
|   |   |   |   |--- class: 0
|   |   |--- n_external_call_ops >  4.500
|   |   |   |--- n_fallback_reachable_blocks <= 6.500
|   |   |   |   |--- class: 0
|   |   |   |--- n_fallback_reachable_blocks >  6.500
|   |   |   |   |--- class: 1
|   |--- n_fallback_reachable_blocks >  8.500
|   |   |--- has_dispatcher <= 0.500
|   |   |   |--- class: 0
|   |   |--- has_dispatcher >  0.500
|   |   |   |--- n_fallback_reachable_blocks <= 25.500
|   |   |   |   |--- class: 1
|   |   |   |--- n_fallback_reachable_blocks >  25.500
|   |   |   |   |--- class: 1
```

The root split is the fallback→external-call reachability feature, and every positive leaf sits beneath it. Trees for folds 1–4 are in `gate_0a_results.json` under `trees`; all five share this root.

### Latency

| | Median | Mean | p95 |
|---|---|---|---|
| Emulator (pure-Python sweep + CFG) | 2.626 ms | 3.649 ms | 11.333 ms |
| AuthGuard-Seq (measured, `robustness_operational_v2`) | 4.121 ms | 5.183 ms | 14.547 ms |

The emulator is faster than the model it is meant to be a cheap stand-in for, in unoptimised Python. A compiled implementation would be far below this. There is no latency argument for preferring the model.

---

## What this does not show

- **This is not evidence about detecting theft.** Both numbers are measured against the source-analyzer label, which the dataset audit established is a deterministic function of the input bytecode. A high emulator score says the *label* is cheap to recover; it says nothing about whether either artifact detects a delegate that actually steals. The circularity critique is untouched by this gate and remains the project's central problem.
- **The emulator is not the source rule.** It approximates `AM_Visualize_ExternalCallInfo` with linear-sweep disassembly and static CFG reachability. Gigahorse performs context-sensitive decompilation with function recovery; my over-approximate CFG conflates paths it would separate. The 0.9106 is what a *cheap approximation* recovers, which is exactly the quantity the gate asked for, but it is not "the rule executed."
- **I did not execute the real rule for comparison.** The work order asks for the Datalog client run directly as a cleaner Gate 0A. The pinned Gigahorse image is pulled and `analyze.dl`'s include paths do resolve from the image's `clients/` directory, but the containerised run was declined during this session, so that comparison is unmeasured. It remains the single most valuable follow-up: running `analyze.dl` over the corpus bytecode would establish end-to-end, rather than by audit inference, that the stored labels are reproducible from the input.
- **Emulator seed variance is zero by construction**, so its ±0.0000 is not comparable to AuthGuard-Seq's ±0.0140. The bootstrap CI, not the seed SD, is the honest uncertainty statement.
- **Feature engineering used the whole corpus.** I inspected feature–label correlations on all 2,190 rows before fixing the feature set. The *models* are trained strictly within folds, but the *choice* of which 15 features to compute was informed by the full dataset. This biases the emulator upward by an unmeasured amount. Since the emulator is the thing whose strength undermines the paper, this cuts against my own conclusion and should be resolved before the number is published — the honest fix is to nominate the feature set from the documented rule alone, which is most of how it was derived, and refit.
- **Latency was measured on this host only** (AMD Ryzen 5 3600), single-threaded, and the AuthGuard-Seq figure is transcribed from a prior run rather than re-measured on the same sample in the same process.
