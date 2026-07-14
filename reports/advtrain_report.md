# Adversarial-Training Robustness — REPORT

Protocol frozen 2026-07-14T21:20:34Z (`reports/advtrain_protocol.md`, sha256 in `reports/advtrain_protocol.sha256`). All numbers emitted from frozen JSON by `pipeline/adv_report.py`. Leakage assertions (source/family/bytecode-hash disjoint train/val/test; mutant family inheritance) passed for all 5 folds (`reports/advtrain_leakage_assertions.txt`).

**Terminology.** structure-preserving / attack-capability-preserving mutations (opcode-skeleton + control-flow identity verified, NOT full EVM semantic equivalence). M3 = held-out mutation condition; +200% = held-out mutation severity. The flooding axis is defined on the M0 base (pure dead-code append) so the held-out M3 selector-rewrite never leaks into the seen flooding conditions.

## Training composition & weighting (T1.3/T1.4)
Symmetric augmentation over 6 seen conditions {M0,M1,M2,F25,F50,F100} applied to both classes. Per fold (train-fit): 487 malicious + 983 benign SOURCE contracts, each contributing 6 instances at weight 1/6 → **effective weighted class totals = 487 malicious / 983 benign per fold** (source-balanced; contracts with more variants get no extra weight). No explicit class weighting (identical to AuthGuard-M0). Thresholds: max-F1 on clean-M0 validation families only, frozen per fold/model (`reports/advtrain_thresholds.csv`).

## T3 — Clean M0 held-out performance
| model | AUPRC | AUROC | precision | recall | F1 | benign FPR |
|---|---:|---:|---:|---:|---:|---:|
| opcode-histogram RF | 0.759 | 0.884 | 0.668 | 0.654 | 0.630 | 0.172 |
| opcode-histogram XGBoost | 0.772 | 0.891 | 0.668 | 0.660 | 0.626 | 0.176 |
| opcode-histogram XGBoost-aug | 0.758 | 0.890 | 0.660 | 0.725 | 0.652 | 0.209 |
| AuthGuard-M0 | 0.830 | 0.920 | 0.693 | 0.797 | 0.716 | 0.192 |
| AuthGuard-aug | 0.849 | 0.931 | 0.720 | 0.761 | 0.711 | 0.164 |

**Clean cost (paired):** AuthGuard AUPRC 0.830→0.849 (**+0.019**); recall 0.803→0.772 (Δ-0.032, 95% CI [-0.053, -0.009]); benign FPR 0.189→0.158. No material clean degradation — a small significant recall dip offset by higher AUPRC and lower benign FPR.

## T4 — Seen augmentation conditions
Malicious recall / benign FPR (AuthGuard):
| condition | AG-M0 recall | AG-aug recall | AG-M0 benign FPR | AG-aug benign FPR |
|---|---:|---:|---:|---:|
| M1 | 0.812 | 0.784 | 0.221 | 0.169 |
| M2 | 0.787 | 0.801 | 0.276 | 0.196 |
| F25 | 0.772 | 0.808 | 0.268 | 0.200 |
| F50 | 0.754 | 0.811 | 0.283 | 0.229 |
| F100 | 0.715 | 0.808 | 0.302 | 0.241 |

Augmentation improves recall and lowers benign FPR across seen conditions (see `figures/fig_advtrain_seen.png`).

## T5 — Held-out mutation conditions and severities
| model | M3 recall | M3 AUPRC | M3 benign FPR | +200% recall | +200% AUPRC | +200% benign FPR |
|---|---:|---:|---:|---:|---:|---:|
| AuthGuard-M0 | 0.787 | 0.754 | 0.276 | 0.624 | 0.596 | 0.314 |
| AuthGuard-aug | 0.801 | 0.814 | 0.196 | 0.790 | 0.750 | 0.275 |
| opcode-histogram XGBoost | 0.696 | 0.710 | 0.230 | 0.606 | 0.562 | 0.352 |
| opcode-histogram XGBoost-aug | 0.772 | 0.727 | 0.233 | 0.701 | 0.688 | 0.324 |

**M3 paired (AuthGuard-aug − M0):** recall 0.794→0.808 (Δ+0.014, 95% CI [-0.009, 0.037]); benign FPR 0.27→0.189 (-0.081).

**F200 paired (AuthGuard-aug − M0):** recall 0.636→0.797 (Δ+0.161, 95% CI [0.131, 0.193]); benign FPR 0.313→0.266 (-0.046).

See `figures/fig_advtrain_heldout.png`. AuthGuard-aug beats opcode-histogram XGBoost-aug at +200% (recall 0.790 vs 0.701), so the gain is not merely padding exposure — the representation contributes.

## T6 — Shortcut / integrity analysis
Benign flag rate vs flooding severity (a padding shortcut would make the AUG model's benign FPR rise ABOVE M0's):
| model | M0 | F25 | F50 | F100 | +200% |
|---|---:|---:|---:|---:|---:|
| AuthGuard-M0 | 0.189 | 0.264 | 0.279 | 0.299 | 0.313 |
| AuthGuard-aug | 0.158 | 0.193 | 0.221 | 0.232 | 0.266 |

**AuthGuard-aug benign FPR is LOWER than AuthGuard-M0 at every severity** → the model did NOT learn 'padding ⇒ malicious'; it became more padding-invariant for BOTH classes. However, benign FPR still rises with padding for the aug model (0.158→0.266), so a residual padding sensitivity remains — robustness is improved, not eliminated. Score distributions: `figures/fig_advtrain_scoredist.png`.

## T7 — Contract-level change analysis (AuthGuard-M0 vs AuthGuard-aug)
| condition | both | M0-only | aug-only | neither | benign +FP(aug) | benign fixed(aug) | singleton recall M0→aug | family-macro recall M0→aug |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| M0 | 585 | 52 | 27 | 129 | 30 | 82 | 0.841→0.823 | 0.851→0.841 |
| M3 | 595 | 35 | 46 | 117 | 43 | 178 | 0.85→0.876 | 0.854→0.875 |
| F200 | 478 | 26 | 154 | 135 | 113 | 190 | 0.655→0.85 | 0.674→0.844 |

At +200%, augmentation newly detects 154 malicious (vs 26 lost) AND net-reduces benign FP by 77; singleton-family recall rises 0.655→0.850 and family-macro 0.674→0.844, so the recovery generalizes across the family distribution rather than to a few large families.

## T9 — Verdict

### PARTIALLY RECOVERS

Mutation-augmented training delivers a **statistically significant, family-generalizing improvement on the held-out +200% severity** (AuthGuard recall 0.624→0.790, Δ+0.161, 95% CI [0.131, 0.193]; AUPRC 0.596→0.750) and improves the held-out M3 condition on AUPRC and benign FPR (recall change not significant), **without a clean-data cost** (clean AUPRC 0.830→0.849, benign FPR 0.192→0.164) and **without a padding shortcut** (aug benign FPR below M0 at every severity). It is **not** RECOVERS-AND-GENERALIZES because absolute benign false positives on flooded benign remain **substantial** (aug +200% benign FPR 0.275) and rise with padding, and +200% discrimination (AUPRC 0.750) stays below clean (AUPRC 0.849): robustness is improved, not achieved.

**Cited numbers:** clean AUPRC delta **+0.019**; held-out M3 recall 0.787→0.801 / AUPRC 0.754→0.814; held-out +200% recall 0.624→0.790 / AUPRC 0.596→0.750; benign +200% FPR 0.275 (aug) vs 0.314 (M0); vs opcode-histogram XGBoost-aug at +200% recall 0.790 (AuthGuard-aug) vs 0.701.

**Scope of evidence.** Supports (a) robustness to the trained augmentation recipe (seen conditions) and (b) extrapolation to a held-out flooding SEVERITY (+200%) and, for AUPRC/FPR, a held-out CONDITION (M3). Does NOT support robustness to arbitrary adversarial transformations. **Not tested (by leakage-safe design):** the paper's worst-case M3-combined-with-heavy-flood — the flooding axis is pure-M0 to keep M3 held out, so the original 0.14 collapse condition is out of scope here; evaluating the M3×+200% combination is future work.

## Reproducibility
```
export PYTHONHASHSEED=0
python3 pipeline/adv_run.py        # train + evaluate (leakage-asserted)
python3 pipeline/adv_analysis.py   # T6/T7/T8
python3 pipeline/adv_figures.py    # figures
python3 pipeline/adv_report.py     # this report
```
Env: Python 3.13, numpy/pandas/scikit-learn/xgboost(libomp)/matplotlib/pycryptodome. Reused unchanged: `family_assignment_frozen.csv`, `pipeline/ag_common.py`, `pipeline/ag_features.py`, `pipeline/04_mutations.py`, AuthGuard-M0 hyperparameters.

### Deliverables
`reports/advtrain_protocol.md`(+`.sha256`), `reports/advtrain_report.md`, `advtrain_results.json`, `paired_results.csv`, `reports/advtrain_training_composition.csv`, `reports/advtrain_thresholds.csv`, `reports/advtrain_leakage_assertions.txt`, `reports/advtrain_analysis.json`, `reports/advtrain_contract_delta.csv`, and figures `fig_advtrain_{clean,seen,heldout,scoredist}.png`.
