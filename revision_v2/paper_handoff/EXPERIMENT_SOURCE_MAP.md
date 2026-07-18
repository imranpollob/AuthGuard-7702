# AuthGuard-7702 Revision v2 — Experiment Source Map

This map is the provenance contract for the rewrite. Paths are repository-relative. `revision_v2/experiments/…` is treated as the canonical completed-output location; mirrored `revision_v2/results/…` files are not independently averaged or combined.

| Paper item | Canonical source | Selection / fields | Aggregation and guardrail |
|---|---|---|---|
| Dataset populations and primary counts | `revision_v2/audit/dataset_statistics_revision_v2.json` | `total_rows`, `populations`, `primary.*` | Report audited populations separately; exclude 90 uncertain inputs |
| Label semantics | `revision_v2/audit/LABEL_CLAIM_CONTRACT.md` | Claim contract | Use source-flagged/source-unflagged terminology |
| Official clean seven-model results | `revision_v2/experiments/baseline_v2/baseline_summary.csv` | All seven rows; AUPRC/AUROC/Brier/Recall/FPR mean and SD columns | Sole authority for clean headline results; mean ± SD across three seed-level means |
| Clean fold/seed traceability | `revision_v2/experiments/baseline_v2/baseline_fold_seed_results.csv` | Seeds 7702/7703/7704 × five folds | Do not pool all predictions into a replacement headline estimator |
| Clean predictions for paired inference | `revision_v2/experiments/baseline_v2/baseline_predictions.csv.gz` | `authguard_seq`, `flat_cnn`, `hist_ngram_xgb` | Used by completed statistical analysis; do not rerun |
| Model parameters/state size/forward timing | `revision_v2/experiments/baseline_v2/baseline_model_complexity.csv` | `authguard_seq` row | 181,877 params; raw model state 737,548 bytes; forward mean/median/p95 |
| Robustness descriptive results | `revision_v2/experiments/robustness_operational_v2/robustness_summary.csv` | Models `authguard_seq`, `flat_cnn`, `hist_ngram_xgb`; conditions M0, F200, M3+F200 | Use F200/M3+F200 for robust headlines; use M0 only as matched degradation reference |
| Robustness fold/seed traceability | `revision_v2/experiments/robustness_operational_v2/robustness_fold_seed_results.csv` | Three seeds × five folds × three conditions | Fold→seed aggregation, then mean ± SD across seeds |
| Robustness predictions | `revision_v2/experiments/robustness_operational_v2/robustness_predictions.csv.gz` | Matched model/row/condition records | Completed paired inference source; no new analysis |
| Donor isolation | `revision_v2/experiments/robustness_operational_v2/donor_isolation_audit.json` | Audit verdict and donor provenance | Required support for transformed-data leakage statement |
| Final paired CIs | `revision_v2/experiments/statistical_analysis_v2/paired_bootstrap_results.csv` | `primary_confirmatory`, `supporting_robustness`, `supporting_clean_to_transformed` rows; AUPRC and Recall@5% | 10,000 family-clustered paired percentile replicates; report Δ and 95% CI, not p-values |
| Statistical protocol | `revision_v2/experiments/statistical_analysis_v2/statistical_analysis_config.json` and `STATISTICAL_ANALYSIS_REPORT.md` | bootstrap seed, cluster key, estimands, comparison roles | Preserve comparison roles and clean/M0 separation |
| External benign control | `revision_v2/experiments/robustness_operational_v2/external_benign_control_results.csv` | `seed=mean_across_seed_means` row | n=797 separate control; values are means across seed means ± SD across seed means |
| Qualitative controls | `revision_v2/experiments/robustness_operational_v2/qualitative_control_results.csv` | `seed=aggregate`, `fold=all` rows | n=5, 15-CV-model averages; runtime-artifact score is illustrative only |
| Full pipeline/load latency | `revision_v2/experiments/robustness_operational_v2/operational_latency_results.csv` | `full_local_screening_pipeline`, `model_load` rows | Report calls and environment; do not include excluded external scopes |
| Runtime artifact identity/environment | `revision_v2/experiments/robustness_operational_v2/operational_metadata.json` | artifact role, bytes, params, CPU/software, included/excluded scope | Use 742,625 bytes for full checkpoint; state explicitly that it is fold-specific |
| Final completion status | `revision_v2/experiments/robustness_operational_v2/FINALIZATION_STATUS.json` | completion/verification fields | Provenance check only, not a result table |

## Exact paper-number rules

1. `baseline_v2` AuthGuard-Seq clean = **0.924447943 AUPRC** and **0.832667663 Recall@5%**. Round to 0.924 and 0.833.
2. Robustness-run M0 AuthGuard-Seq = **0.932392906 AUPRC** and **0.850669671 Recall@5%**. It may appear only in a matched-degradation context.
3. Operational checkpoint size = **742,625 bytes**. Baseline model-state serialization = **737,548 bytes**. They measure different serialization scopes.
4. Full-pipeline latency = **5.183 ms mean, 4.121 ms median, 14.547 ms p95, 21.429 ms p99**, 1,500 calls.
5. Forward-only latency = **1.009 ms mean, 0.950 ms median, 1.585 ms p95**, 195 timed calls after exclusions/warm-up as recorded in the completed output.
6. External FPR = **0.015 / 0.065 / 0.169**, not the old manuscript values.

## Figure-data derivation

- `FINAL_FIGURE_DATA/main_model_comparison.csv` is a rounded projection of `baseline_summary.csv`, joined to `baseline_model_complexity.csv` by model name.
- `FINAL_FIGURE_DATA/robustness_comparison.csv` is a rounded projection of `robustness_summary.csv`; the `clean_role` column prevents plotting M0 as the official clean headline.
- `FINAL_FIGURE_DATA/operational_latency.csv` projects `operational_latency_results.csv`; its forward-reference row uses the raw baseline state size to retain the scope distinction.

The figure CSVs are plotting inputs, not additional results. If a plotted label conflicts with the canonical source, the canonical source wins.
