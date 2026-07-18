# Revision v2 — Signal Sanity Check

Question: **does a meaningful bytecode-learning signal survive the dataset-validity
corrections?** Answer: **yes.**

Protocol: identical to the frozen AuthGuard-Fusion experiment
(`revision_v2/experiments/authguard_fusion/run_authguard_fusion.py`, functions
imported unmodified by `revision_v2/audit/scripts/run_sanity_v2.py`): stored
family-disjoint outer folds, validation fold = (fold+1) mod 5, temperature scaling on
validation, warning thresholds derived from validation negatives at 1%/5% FPR
targets, metrics on the held-out test fold. Seed **7702**, all 5 outer folds.
Models: `hist_ngram_xgb` (opcode histogram + hashed 4-gram XGBoost, the strongest
traditional baseline) and **AuthGuard-Seq** (`sequence_only`).

Corrected benchmark: `revision_v2/data/authguardbench_7702_v2.csv.gz`,
PRIMARY_EVALUATION only (2,190 rows = 727 source-flagged / 1,463 source-unflagged;
90 corrupted-input rows removed relative to the original 2,280). Features were
recomputed from the (repaired) runtime bytecode with the frozen featurization.

## Original vs corrected (5-fold means, seed 7702)

| model | benchmark | AUPRC | Brier | R@1% (achieved FPR) | R@5% (achieved FPR) |
|---|---|---|---|---|---|
| hist_ngram_xgb | original | 0.841 | 0.137 | 0.347 (0.024) | 0.612 (0.064) |
| hist_ngram_xgb | **v2**   | 0.828 | 0.141 | 0.332 (0.010) | 0.596 (0.076) |
| AuthGuard-Seq  | original | 0.918 | 0.068 | 0.672 (0.018) | 0.829 (0.036) |
| AuthGuard-Seq  | **v2**   | **0.920** | 0.067 | 0.559 (0.013) | 0.860 (0.042) |

(The paper's 0.931 for AuthGuard-Seq is the 3-seed mean on the original benchmark;
the comparison above holds seed and protocol fixed on both sides.)

## Per-fold AUPRC (seed 7702)

| fold | XGB orig | XGB v2 | Seq orig | Seq v2 |
|---|---|---|---|---|
| 0 | 0.833 | 0.792 | 0.822 | 0.817 |
| 1 | 0.837 | 0.844 | 0.909 | 0.940 |
| 2 | 0.860 | 0.822 | 0.936 | 0.925 |
| 3 | 0.789 | 0.797 | 0.970 | 0.972 |
| 4 | 0.885 | 0.887 | 0.954 | 0.948 |

## Reading

- **The signal survives.** AuthGuard-Seq: 0.918 → 0.920 AUPRC; the correction
  neither inflates nor destroys the result. The baseline dips slightly
  (0.841 → 0.828), consistent with removing 90 long, easily-scored negatives; the
  sequence model's advantage over the strongest traditional baseline persists
  (+0.092 AUPRC on v2).
- Recall@1%-validation-FPR is volatile in both directions (0.672 → 0.559 for Seq)
  because 1% of a ~290-negative validation fold is a 2–3-contract threshold; this
  metric should be reported with that caveat (as the original G-DET analysis already
  does). Recall@5% improved (0.829 → 0.860) with achieved FPR near target.
- No tuning was performed against the corrected benchmark; a single fixed seed and
  the frozen hyperparameters were used. This is a sanity check, not the full
  evaluation suite; the full suite (multi-seed, robustness conditions, controls)
  should be rerun on v2 before the manuscript numbers are finalized.

Raw outputs: `revision_v2/audit/sanity_v2/{metrics_v2.csv, predictions_v2.csv.gz,
comparison.json, features_v2.npz}`; log `revision_v2/audit/sanity_v2_run.log`.
