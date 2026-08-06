# Coverage-Gating / Decision-Strategy Results

Run `v2`. Values read from `data/gold_dataset/experiments/v2_decision_strategies.json`;
per-contract scores in `v2_decision_scores.csv`.

All four strategies use **identical frozen scores** from the model selected on validation
(`C_pretrain_finetune`; validation AUPRC 0.289 vs 0.242 for A and 0.226 for B). Operating
threshold 0.789 = the 5%-FPR point on validation negatives. Test population: 51 rows, 44
decidable, 9 positive, 7 undecidable (U).

## Strategy comparison at matched defer rate

| Strategy | defer rate | warn precision | warn recall | positives w/o warning | U warned | U deferred |
|---|---:|---:|---:|---:|---:|---:|
| No deferral | 0.000 | **0.000** | 0.000 | 9 | 1 | 0 |
| Coverage-based | 0.137 | **0.000** | 0.000 | 9 | 0 | 7 |
| Score-margin | 0.137 | **0.000** | 0.000 | 9 | 0 | 2 |
| Random (mean of 200 draws) | 0.137 | **0.000** | 0.000 | 7.8 | 0.9 | 0.9 |

At this operating point the model issues 7 warnings under no deferral and **none of them is a
true positive**, so warning precision and recall are 0.000 for every strategy. All 9 positives
receive no warning. No deferral strategy can create discrimination that the underlying score does
not have; this table measures routing, not detection.

## What coverage gating does achieve

Coverage-based deferral is the only strategy that routes **all 7 undecidable (U) contracts** to a
human, because U is defined by PARTIAL analysis coverage and the gate keys on exactly that. It
thereby removes the single spurious warning that no-deferral issued on a contract whose analysis
was incomplete — a case where a warning would have asserted more than the evidence supported.
Score-margin deferral catches only 2 of the 7, and random deferral 0.9 on average.

So the mechanism works as designed as an *evidence router*: it withholds a verdict exactly where
the static analysis is incomplete. It is not, and on this data cannot be, evidence of detection
quality.

## Precision versus defer-rate curves

`paper_artifacts/figures/precision_vs_defer_rate.pdf` sweeps defer rates 0 → 0.8 for
score-margin, random, and coverage-then-margin policies. Warning precision remains 0.000 across
the whole sweep for every policy: because no true positive is ever ranked above the threshold,
removing cases from the active set cannot raise precision above zero. The curves are reported for
completeness and are flat by construction here.

## Population-wide deferral

| | |
|---|---:|
| Test rows deferred as U (coverage gate) | 7 / 51 (13.7%) |
| NOTSCREENABLE delegates, always deferred, never in the gold set | 8 |
| Population-wide U rate (all 752 screenable delegates) | 324 (43.1%) |

The population-wide U rate is the more consequential number: on the full collected population,
43% of delegates cannot be adjudicated from bytecode alone, dominated by contracts whose
DELEGATECALL callee is computed at runtime.
