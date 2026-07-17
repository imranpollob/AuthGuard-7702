# AuthGuard-Fusion Contribution Decision

Candidate: `fusion_consistent`. Strongest baseline: `hist_ngram_xgb`.

Architecture performance outcome: **NOT SUPPORTED**.

This decision concerns a performance claim only. Multi-task interpretability and operational-tool claims require their separate output and runtime checks.

## Paired results

| Condition | Metric | Candidate | Baseline | Delta | 95% CI |
|---|---:|---:|---:|---:|---:|
| F200 | AUPRC | 0.6939 | 0.5513 | +0.1425 | [+0.0786, +0.2030] |
| F200 | FPR_05 | 0.0869 | 0.0438 | +0.0431 | [+0.0236, +0.0645] |
| F200 | Recall_05 | 0.5571 | 0.1733 | +0.3838 | [+0.2815, +0.4904] |
| M3F200 | AUPRC | 0.6993 | 0.5439 | +0.1554 | [+0.1006, +0.2153] |
| M3F200 | FPR_05 | 0.0811 | 0.0361 | +0.0451 | [+0.0255, +0.0660] |
| M3F200 | Recall_05 | 0.5818 | 0.2091 | +0.3728 | [+0.2772, +0.4821] |
| benign_general | FPR_05 | 0.0527 | 0.0376 | +0.0151 | [-0.0099, +0.0431] |
| cleanM0 | AUPRC | 0.8392 | 0.8339 | +0.0053 | [-0.0595, +0.0656] |
| cleanM0 | FPR_05 | 0.0670 | 0.0586 | +0.0084 | [-0.0225, +0.0506] |
| cleanM0 | Recall_05 | 0.7868 | 0.6272 | +0.1596 | [+0.0653, +0.2791] |

## Claim wording

Use `improves` only for rows with a positive, practically meaningful delta whose interval excludes zero. Otherwise use `is competitive with` or `we evaluate`, as appropriate.
