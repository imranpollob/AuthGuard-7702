# AuthGuard-Fusion Contribution Decision

Candidate: `sequence_only`. Strongest baseline: `hist_ngram_xgb`.

Architecture performance outcome: **SUPPORTED**.

This decision concerns a performance claim only. Multi-task interpretability and operational-tool claims require their separate output and runtime checks.

## Paired results

| Condition | Metric | Candidate | Baseline | Delta | 95% CI |
|---|---:|---:|---:|---:|---:|
| F200 | AUPRC | 0.8828 | 0.5513 | +0.3314 | [+0.2561, +0.4089] |
| F200 | FPR_05 | 0.0212 | 0.0438 | -0.0225 | [-0.0372, -0.0090] |
| F200 | Recall_05 | 0.7538 | 0.1733 | +0.5805 | [+0.4678, +0.6794] |
| M3F200 | AUPRC | 0.8693 | 0.5439 | +0.3254 | [+0.2561, +0.4016] |
| M3F200 | FPR_05 | 0.0354 | 0.0361 | -0.0006 | [-0.0166, +0.0143] |
| M3F200 | Recall_05 | 0.7552 | 0.2091 | +0.5461 | [+0.4365, +0.6435] |
| benign_general | FPR_05 | 0.0853 | 0.0376 | +0.0477 | [-0.0202, +0.1501] |
| cleanM0 | AUPRC | 0.8910 | 0.8339 | +0.0571 | [+0.0023, +0.1179] |
| cleanM0 | FPR_05 | 0.0341 | 0.0586 | -0.0245 | [-0.0466, -0.0047] |
| cleanM0 | Recall_05 | 0.8391 | 0.6272 | +0.2118 | [+0.0952, +0.3390] |

## Claim wording

Use `improves` only for rows with a positive, practically meaningful delta whose interval excludes zero. Otherwise use `is competitive with` or `we evaluate`, as appropriate.
