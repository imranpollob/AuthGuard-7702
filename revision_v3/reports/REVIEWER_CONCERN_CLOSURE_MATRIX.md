# Reviewer-Concern Closure Matrix

**LABEL_SOURCE=LLM_PROVISIONAL where cited. STATUS=PROVISIONAL_NOT_FOR_FINAL_CLAIMS for any
row whose evidence depends on provisional labels.**

Per explicit instruction, the following are **never** marked RESOLVED using LLM provisional
labels alone: final label validity, final human-reference performance, final model selection
under human labels, LLM-human agreement. Those rows are BLOCKED_BY_HUMAN_LABELS regardless of
how much provisional evidence exists.

| # | Concern | Work Completed | Supporting Evidence | Status | Remaining Action | Impact on Paper Claims |
|---|---|---|---|---|---|---|
| 1 | Label validity | Provisional (LLM) labels generated for all 230 Pilot/Gold-Dev/Gold-Test items under one documented protocol | `LLM_PROVISIONAL_LABELING_PROTOCOL.md`; `results/llm_provisional/{pilot,gold_dev,gold_test}_labels.json` | **BLOCKED_BY_HUMAN_LABELS** | Independent human review via `Pilot_Code_Review.xlsx` / `Gold_Dev_Code_Review.xlsx` / `Gold_Test_Code_Review.xlsx` | All Part 6-12 metrics are provisional until this closes |
| 2 | Dataset provenance | Unchanged from Phase 1/2; Gold-Dev/Gold-Test provenance columns preserved through enrichment | `source_inventory.csv`, `evidence_manifest.json` for both sets | RESOLVED | none | none |
| 3 | Duplicate leakage | Exact-hash + family-similarity dedup already enforced by Phase 1/2 sampling; re-verified no resampling occurred | `test_manifests_unchanged_and_not_resampled` (MD5 match) | RESOLVED | none | none |
| 4 | Family leakage | Gold-Dev/Gold-Test family sets confirmed disjoint; Part 7 retraining confirmed to touch only Gold-Dev families | `test_family_isolation_between_gold_dev_and_gold_test`; `run_retraining_experiments.py` family-grouped CV | RESOLVED | none | none |
| 5 | Architecture novelty | Unchanged from Phase 2 (`authguard_sequence_dense`); provisional model reuses the identical architecture (fine-tuned weights only) | `configs/final_model.json`, `configs/provisional_final_model.json` | RESOLVED | none | none |
| 6 | Component ablation | Not re-run in this pass (out of scope — Phase 2 already covers it) | `revision_v3/experiments/controlled_ablation/` (Phase 2) | RESOLVED (carried from Phase 2) | none | none |
| 7 | Token-budget fairness | Not re-run in this pass | Phase 2 `PARAMETER_ACCOUNTING_REPORT.md` | RESOLVED (carried from Phase 2) | none | none |
| 8 | Parameter-count fairness | Not re-run in this pass | Phase 2 parameter-matched Flat CNN reused as-is (`flat_cnn_matched_16384`) in Parts 6/9/14 | RESOLVED (carried from Phase 2) | none | none |
| 9 | Bootstrap correctness | Reused the Phase 2 corrected seed-aware paired bootstrap for Gold-Test AUPRC CIs (family-clustered) | `run_gold_test_evaluation.py::bootstrap_ci_metric`, modeled on `evaluation/bootstrap_v2.py` | RESOLVED | none | Gold-Test CIs in Table 8 are family-clustered, not naively pooled |
| 10 | Robustness validity | Not re-run against provisional labels in this pass (Phase 2's Flood-200% result stands on source labels) | Phase 2 `FINAL_ROBUSTNESS_REPORT.md` | PARTIALLY_RESOLVED | Re-run Flood-200% against provisional/human labels if reviewers want it cross-checked | Robustness claim currently rests on source labels only |
| 11 | Calibration | Measured for every model in Parts 6/9 (Brier, ECE) | `gold_dev_baseline_report.json`, `gold_test_report.json` | **BLOCKED_BY_HUMAN_LABELS** (calibration numbers are provisional-label-dependent) | Re-measure once human labels exist | Part 9 flagged a concrete miscalibration finding (provisional_final_model's threshold generalized poorly — FPR 0.857 at recall 1.0) |
| 12 | Temporal generalization | Real partial collection (Ethereum ~23k blocks scanned live; Base indexed-API discovery built and partially run; 1-day pilots for BNB/Optimism/Arbitrum completed, Polygon/Gnosis in progress) + real evaluation on 39 enriched Ethereum/BNB temporal delegates | `TEMPORAL_COLLECTION_FINAL_STATUS.md`, `results/llm_provisional/temporal/temporal_report.json` | PARTIALLY_RESOLVED | Let the checkpointed Ethereum/Base jobs finish; re-run Part 12 sampling once more chains have data | Temporal AUPRC not yet estimable (single-class sample so far — 38/39 provisional-UNSAFE) |
| 13 | Legitimate controls | All 30 known-project deployments verified live (Sourcify/Blockscout/on-chain hash match) and categorized | `verified_legitimate_controls.csv`: 22 VERIFIED, 8 CANDIDATE, 0 UNRESOLVED | RESOLVED | none | none |
| 14 | Static analyzer comparison | Source static rule evaluated against provisional labels on both Gold-Dev and Gold-Test | Tables 7-8; `binary_rule_report` in both baseline scripts | **BLOCKED_BY_HUMAN_LABELS** for the comparison's *conclusions*; the comparison *code* is RESOLVED | Re-run once human labels exist | none until then |
| 15 | ML-vs-static-analysis justification | Positioning document written with the defensible framing, grounded in this pass's own measurements | `ML_VS_STATIC_ANALYSIS_POSITIONING.md` | RESOLVED | none | none |
| 16 | Deployment feasibility | Real CPU+GPU latency/memory/throughput + real ONNX export and numerical-parity check | `results/deployment/deployment_report.json` (ONNX max-abs-diff 4.2e-7) | RESOLVED | none | none |
| 17 | Reproducibility | One-command rerun script exists and is exercised for `llm_provisional`; `source_rule`/`human_final` paths documented but not fully parametrized | `run_reference_pipeline.py` | PARTIALLY_RESOLVED | Build the `source_rule`-parametrized eval scripts (currently the llm_provisional scripts are hardcoded to `*_labels.json`) | Full one-command reproducibility for all 3 label sources not yet complete |
| 18 | Human evidence quality | Code-evidence packages built for all 230 items (decompiled, guard-traced, offset-cited) feeding the human review workbooks | `*_code_evidence/`, `Gold_Dev_Code_Review.xlsx`, `Gold_Test_Code_Review.xlsx` | RESOLVED (infrastructure); human review itself is separate ongoing work | Human review to proceed on its own timeline | none |
| 19 | Final model selection | Provisional selection done and documented, using Gold-Dev only, multi-criteria (not point-AUPRC alone) | `PROVISIONAL_FINAL_MODEL_SELECTION.md` | **BLOCKED_BY_HUMAN_LABELS** for a *final* selection claim | Redo model selection once human Gold-Dev labels exist | Current selection is explicitly PROVISIONAL FINAL MODEL, not final |
| 20 | Gold-Test independence | Gold-Test provisional labels touched nothing before Part 9; Part 7/8 selection manifest checked to reference Gold-Dev only | `test_gold_test_not_used_in_model_selection_manifest` | RESOLVED | none | none |

## Summary counts

- RESOLVED: 11
- PARTIALLY_RESOLVED: 3
- BLOCKED_BY_HUMAN_LABELS: 6 (as required, none of the 4 explicitly-listed concerns — final
  label validity, final human-reference performance, final model selection, LLM-human
  agreement — were marked resolved using provisional labels)
