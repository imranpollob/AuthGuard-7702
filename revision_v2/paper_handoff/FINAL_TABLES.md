# AuthGuard-7702 Revision v2 — Final IEEE Table Set

Values are rounded for print. The unrounded values and provenance are in `FINAL_RESULTS_MANIFEST.md` and `EXPERIMENT_SOURCE_MAP.md`.

## Table I — Audited benchmark populations

| Population | n | Positive | Negative | Families | Paper role |
|---|---:|---:|---:|---:|---|
| Primary evaluation | 2,190 | 727 | 1,463 | 790 | Clean, robust, and paired evaluation |
| External benign control | 797 | — | 797 | — | Separate population-shift control |
| Qualitative control | 5 | — | 5 | — | Descriptive legitimate examples |
| Excluded uncertain input | 90 | — | — | — | Excluded from all evaluation |

**Caption note:** The full audited corpus contains 3,082 rows. Primary labels are source-analyzer flags, not independently verified maliciousness.

**Merge candidate:** Keep standalone; this is the shortest way to expose the population separation reviewers need.

## Table II — Official clean seven-model comparison

| Model | AUPRC ↑ | AUROC ↑ | Brier ↓ | R@5% ↑ |
|---|---:|---:|---:|---:|
| **AuthGuard-Seq** | **.924±.014** | **.963±.011** | **.072±.012** | **.833±.016** |
| Flat CNN | .885±.010 | .937±.007 | .099±.004 | .712±.024 |
| Hist.+4-gram XGB | .833±.004 | .907±.002 | .127±.003 | .615±.015 |
| n-gram only | .810±.007 | .880±.020 | .125±.001 | .654±.029 |
| BiGRU | .679±.098 | .815±.069 | .163±.027 | .379±.113 |
| Dense only | .637±.018 | .780±.022 | .182±.009 | .331±.023 |
| Transformer | .563±.031 | .730±.019 | .208±.013 | .239±.054 |

**Caption note:** Three-seed mean ± SD of seed-level means over five family-disjoint folds; thresholds selected on validation data. AuthGuard-Seq achieved test FPR .052±.007 at the nominal 5% operating point.

**Merge candidate:** Do not merge in the main paper; this is the principal descriptive result.

## Table III — Family-clustered paired differences

| Condition | Comparator | ΔAUPRC [95% CI] | ΔR@5% [95% CI] |
|---|---|---:|---:|
| Clean | Flat CNN | +.039 [.009,.073] | +.121 [.050,.190] |
| Clean | XGBoost | +.091 [.045,.140] | +.217 [.124,.314] |
| F200 | Flat CNN | +.385 [.302,.472] | +.556 [.463,.655] |
| F200 | XGBoost | +.344 [.286,.397] | +.521 [.442,.607] |
| M3+F200 | Flat CNN | +.387 [.309,.468] | +.561 [.471,.659] |
| M3+F200 | XGBoost | +.355 [.296,.409] | +.543 [.467,.629] |

**Caption note:** AuthGuard-Seq minus comparator; paired family-clustered percentile bootstrap, 10,000 replicates. All shown intervals exclude zero.

**Merge candidate:** If space is tight, merge with Table IV as a two-panel robustness/inference table. Preserve the two clean rows in Panel A.

## Table IV — Robustness performance and matched degradation

**Panel A: transformed-input performance**

| Model | F200 AUPRC / R@5% | M3+F200 AUPRC / R@5% |
|---|---:|---:|
| **AuthGuard-Seq** | **.920±.007 / .747±.024** | **.912±.005 / .745±.023** |
| Flat CNN | .535±.013 / .191±.010 | .525±.011 / .185±.013 |
| XGBoost | .576±.003 / .226±.014 | .557±.007 / .202±.014 |

**Panel B: AuthGuard-Seq transformed minus matched M0**

| Change | ΔAUPRC [95% CI] | ΔR@5% [95% CI] |
|---|---:|---:|
| F200 − M0 | −.013 [−.030,−.002] | −.104 [−.155,−.067] |
| M3+F200 − M0 | −.020 [−.037,−.009] | −.105 [−.158,−.067] |

**Caption note:** M0 is the paired robustness-run clean reference only; official clean results remain in Table II. F200 has bounded execution-fingerprint support, while M3+F200 is representation stress without guaranteed behavior preservation.

**Merge candidate:** Preferred merge with Table III for an eight-page version: Table III becomes Panel A (clean inference), and this table supplies Panels B–C (robust performance and degradation).

## Table V — External-control and operational evidence

**Panel A: external benign control (n=797)**

| Nominal operating point | External FPR |
|---|---:|
| 1% | .015±.004 |
| 5% | .065±.012 |
| 10% | .169±.021 |

**Panel B: local CPU timing**

| Scope | Calls | Median | p95 | p99 |
|---|---:|---:|---:|---:|
| Full screening | 1,500 | 4.121 ms | 14.547 ms | 21.429 ms |
| Model load | 10 | 7.690 ms | 9.716 ms | 10.574 ms |
| Forward only | 195 | .950 ms | 1.585 ms | — |

**Caption note:** Full screening excludes RPC, blockchain node, wallet UI, and external services. The timing checkpoint has 181,877 parameters and is 742,625 bytes; it is a fold-specific CV artifact, not a final deployment model.

**Merge candidate:** This is already a space-saving merge. Move the n=5 qualitative-control examples to prose, appendix, or artifact; do not squeeze them into the main table as inferential evidence.

## Recommended eight-page allocation

- Main text: Tables I, II, merged III+IV, and V.
- Appendix/artifact: expanded Recall@1%/10%, achieved FPRs, all qualitative-control rows, and unrounded values.
- If one more table must be removed, compress Table I into the Dataset paragraph; never remove the population separation or label boundary.
