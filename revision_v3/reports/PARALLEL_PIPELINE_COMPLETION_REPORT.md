# Parallel Pipeline Completion Report

**LABEL_SOURCE=LLM_PROVISIONAL for every metric below unless stated otherwise.
STATUS=PROVISIONAL_NOT_FOR_FINAL_CLAIMS.**

Branch `tps-revision-v3`. This report covers the full provisional-label pipeline built and
run in this pass, continuing from Phase 1/2 (frozen, untouched) and Phase 3A (Pilot code
review, untouched). Scope was explicitly confirmed with the user before starting: (1)
Gold-Dev/Gold-Test evidence enrichment would use an automated guard-tracer generalized from
Pilot's manual method, rather than re-doing 210 items by hand; (2) the 5-month/6-chain
temporal collection would be launched as real, checkpointed background jobs with actual
progress reported, not assumed to complete in one session.

## 1. Evidence-enrichment coverage

| Sample set | Items | Verified source | Guard-trace GUARDED_ALL | OPEN_FOUND | AMBIGUOUS |
|---|---|---|---|---|---|
| Pilot | 20 | 0 (hand-verified separately in Phase 3A) | — | — | — |
| Gold-Dev | 60 | 6 (10%) | 5 | 50 | 5 |
| Gold-Test | 150 | 18 (12%) | 7 | 140 | 3 |

A real bug in the automated guard-tracer (extracting the `0xffff...ff` bitmask instead of the
actual compared address) was found via spot-checking, fixed, and applied retroactively to
already-collected evidence via `refresh_guard_traces.py` without re-running the network-heavy
collection.

## 2. Provisional label distributions

| Sample set | SAFE | UNSAFE | UNCERTAIN |
|---|---|---|---|
| Pilot | 9 | 6 | 5 |
| Gold-Dev | 5 | 42 | 13 |
| Gold-Test | 7 | 131 | 12 |

## 3. Gold-Dev provisional results

`authguard_sequence_dense`: AUPRC 0.925, AUROC 0.610, recall 0.357, FPR 0.400 (n=47 binary,
13 UNCERTAIN excluded, 21.7% coverage). All 4 continuous models plus the source rule landed
on the identical confusion matrix at n=47 — flagged as a small-sample coincidence, not hidden.
Full detail: `LLM_PROVISIONAL_GOLD_DEV_BASELINE_REPORT.md`.

## 4. Provisional retraining results

10 methods, Gold-Dev only, family-grouped 3-fold × 3 seeds (6 valid runs/method after
degenerate single-class folds were skipped). `confidence_weighted` won on both mean AUPRC
(0.969) and stability (std 0.017). Full detail: `LLM_PROVISIONAL_RETRAINING_REPORT.md`.

## 5. Provisional model selection

`confidence_weighted` fine-tuning selected as the **PROVISIONAL FINAL MODEL** basis
(multi-criteria: mean AUPRC, stability, zero added complexity), frozen as 3 seed checkpoints
trained on all 47 binary Gold-Dev items. `configs/provisional_final_model.json` preserves
`configs/final_model.json` (Phase 2 frozen model) untouched alongside it. Full detail:
`PROVISIONAL_FINAL_MODEL_SELECTION.md`.

## 6. Gold-Test provisional results

Provisional final model: AUPRC 0.968 [0.915, 0.999], but a **degenerate operating threshold**
(recall 1.0, FPR 0.857 — predicts almost everything UNSAFE), surfaced only by evaluating
end-to-end rather than stopping at the rank metric. `authguard_sequence_dense`: AUPRC 0.963
[0.928, 0.991], recall 0.336, FPR 0.429 (n=138, 12 UNCERTAIN excluded, 8.0% coverage). All 5
models' CIs overlap. Full detail: `LLM_PROVISIONAL_GOLD_TEST_REPORT.md`.

## 7. Static-rule comparison

Source static rule: precision 0.978, recall 0.344, FPR 0.143 on Gold-Test — the best
precision/FPR trade-off of any method compared, sharing the ~0.34 recall ceiling every method
in this comparison shows.

## 8. Cascade evaluation

Escalation band selected on Gold-Dev only (score tercile), frozen, evaluated once on
Gold-Test: AuthGuard-first-with-rule-escalation resolves 63.0% of items locally while
matching the rule's FPR (0.143). Full detail: `LLM_PROVISIONAL_CASCADE_REPORT.md`.

## 9. Temporal collection and evaluation

**Real, partial, still-running at time of writing** (checkpointed, safe to resume):
- Ethereum: 26,500/1,068,475 blocks scanned (2.5%), 31,569 type-4 txs, 47,890 authorization
  entries, 0 RPC errors.
- Base: indexed-API approach built (Blockscout `advanced-filters` + `mainnet.base.org`
  fallback, a genuine infrastructure discovery this pass made — the free RPC endpoints
  already in the codebase could not serve 5-month-old Base history); currently stalled on
  endpoint reliability, 0 blocks collected in the full-window run despite working in
  isolated testing.
- BNB (complete, 1,501 blocks): 1,459 type-4 txs, 1,462 authorization entries.
- Arbitrum (complete, 1,501 blocks): 45 type-4 txs, 47 authorization entries.
- Optimism (complete, 1,501 blocks): 6 type-4 txs, 6 authorization entries.
- Polygon (complete, 1,501 blocks): 436 type-4 txs, 438 authorization entries.
- Gnosis (partial, 400/1,501 blocks at time of writing): 16 type-4 txs, 16 authorization
  entries.

Provisional evaluation on 39 real, enriched Ethereum+BNB delegates: 97% provisional-UNSAFE
(38/39), 0 exact historical duplicates, 27/39 (69%) previously-unseen families. AUPRC not
computable (single-class-dominated sample) — reported honestly rather than worked around.
Full detail: `TEMPORAL_COLLECTION_FINAL_STATUS.md`, `LLM_PROVISIONAL_TEMPORAL_REPORT.md`.

## 10. Legitimate-control verification

All 30 recorded deployments (8 documented projects) re-verified live: 30/30 runtime-hash
matches (bytecode unchanged since Phase 2), 22 VERIFIED_LEGITIMATE_CONTROL (live verified
source + documentation), 8 CANDIDATE_LEGITIMATE_CONTROL, 0 UNRESOLVED_CONTROL. Full detail:
`LEGITIMATE_CONTROL_VERIFICATION_REPORT.md`.

## 11. Deployment evaluation

`authguard_sequence_dense`: 97,646 params, 397,988-byte checkpoint, 2.83ms median / 3.44ms
p99 CPU forward latency, 125.7 items/sec throughput (RTX 2080 SUPER + measured CPU, this
machine only). ONNX export succeeded with numerical parity (max abs diff 4.17e-7) but was
slower than native PyTorch on CPU in this configuration. `authguard_reference_v3`'s ONNX
numerical-parity check hit a benchmark-script bug (tuple-output handling), reported honestly
rather than silently passed. Full detail: `DEPLOYMENT_EVALUATION_REPORT.md`.

## 12. ML-vs-static-analysis positioning

Defensible framing written and grounded in this pass's own measurements: semantic static
analysis is demonstrably usable pre-authorization (this project's own pipeline proves it),
but costs 4 external dependencies and seconds-to-tens-of-seconds per item vs. AuthGuard's
2.83ms/no-dependency triage; the cascade (item 8 above) demonstrates measured workload
reduction, not a replacement claim. Full detail: `ML_VS_STATIC_ANALYSIS_POSITIONING.md`.

## 13. Manuscript preparation status

New workspace `revision_v3/manuscript/` (9 files) drafted: title/abstract, introduction/
motivation/threat-model, dataset/label-source explanation, architecture/training, evaluation
methodology, provisional results, temporal/deployment, limitations/ethics/conclusion. Every
metric is inline-marked `[PROVISIONAL]`. Does not overwrite `revision_v2/manuscript/` (the
current submitted manuscript).

## 14. Reviewer-concern closure matrix

20/20 concerns addressed: 11 RESOLVED, 3 PARTIALLY_RESOLVED, 6 BLOCKED_BY_HUMAN_LABELS.
Final label validity, final human-reference performance, final model selection under human
labels, and LLM-human agreement were **not** marked resolved using provisional labels, per
explicit instruction. Full detail: `REVIEWER_CONCERN_CLOSURE_MATRIX.md`.

## 15. Tasks still blocked by human labels

- Final label validity and any "ground truth" performance claim.
- Final model selection (current selection is explicitly PROVISIONAL FINAL MODEL).
- LLM-vs-human agreement analysis (`LLM_VS_HUMAN_AGREEMENT_REPORT.md` is
  `PENDING_HUMAN_LABELS`, verified to write no fabricated analysis when run today).
- Calibration/robustness claims that depend on the label source.
- Manuscript finalization (explicitly forbidden until then).

## 16. Exact one-command human-label rerun

```bash
python3 revision_v3/run_reference_pipeline.py --label-source human_final
```
Currently exits with `BLOCKED_NO_HUMAN_LABELS` (verified by
`test_human_final_mode_does_not_fabricate_when_no_labels_exist`) because no workbook has any
non-blank `final_label` cell yet. Once human review completes and final labels are imported
into the `human_final_label` field (an importer analogous to Phase 3A's
`import_reviewer_workbook.py`, not yet built since no source data exists for it), this same
command runs the full chain. The `llm_provisional` path is fully exercised today; the
`source_rule` path's evaluation scripts are documented as not-yet-parametrized (a concrete,
scoped follow-up, not silently reused against the wrong label column).

## 17. Exact files humans must eventually provide

- Completed `final_label` / `final_reason` columns in `Pilot_Code_Review.xlsx`,
  `Gold_Dev_Code_Review.xlsx`, `Gold_Test_Code_Review.xlsx` (lead-author adjudicated, per
  contributor review + group discussion — the locked columns in each workbook).

## 18. Expected changes once human labels arrive

- Every Part 6-12 metric will be regenerated under `results/human_final/` (never overwriting
  `results/llm_provisional/`).
- The provisional model's degenerate-threshold problem (item 6) may or may not persist —
  worth specifically re-checking given it was caught only by full end-to-end evaluation.
- Model ranking may change; `LLM_VS_HUMAN_AGREEMENT_REPORT.md` will report exactly how much
  the label set moved and whether retraining is warranted (heuristic already coded: >15%
  label-change rate triggers a recommendation).
- Temporal 97%-UNSAFE finding (item 9) should be re-examined once broader collection and/or
  human labels exist — currently too provisional and too narrow a sample to generalize from.

## 19. Test and frozen-guard results

- `revision_v3/tests/`: **116/116 passed** (85 carried from Phase 1-3A + 31 new tests added
  this pass covering label-source separation, no-copying, Gold-Test independence, family
  isolation, uncertainty handling, watermarking, output-directory separation, blinding,
  schema/taxonomy consistency, manifest-unchanged, legitimate-control provenance, temporal
  dedup, one-command-rerun existence, and human-final non-fabrication).
- `revision_v2/experiments/common/frozen.py verify`: **OK, 144/144 frozen files unchanged.**

## 20. Git status

61 new/modified files (all new — no existing Phase 1/2/3A file was modified; verified by the
frozen guard and by MD5-checking every frozen manifest). Not committed — per instruction, no
automatic commit was made.

---

## Final stop-condition compliance

`human_final_label` was not populated anywhere (structurally enforced and tested). LLM labels
were not called human labels anywhere in any generated artifact (every output is watermarked
`LABEL_SOURCE=LLM_PROVISIONAL`). The frozen Gold-Test sample was not modified (MD5-verified
unchanged). No model was tuned using Gold-Test results (Part 7/8 selection manifest verified
to reference only Gold-Dev). Phase 1/2 results were not overwritten (frozen guard: 144/144
unchanged). No provisional result was overwritten by a later run (directory separation
enforced and tested). The manuscript was not submitted or finalized. Nothing was committed
automatically.
