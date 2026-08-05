# Phase 2 Report — Infrastructure and Model Finalization

Branch `tps-revision-v3`, built on top of the "phase 1" commit
(`b9b8282e3aec71b8e9fce68d67011c27d2f4e717`). Frozen-hash guard
(`revision_v2/experiments/common/frozen.py verify`) reports `OK: 144 frozen files verified
unchanged` before, during, and after this phase's work. No Phase 1 report or result file was
modified (verified by `revision_v3/tests/test_phase2_no_writes_to_frozen.py`, which hashes a
representative sample of Phase 1 outputs and asserts they are byte-identical at the end of the
test run). All Phase 2 outputs live under new directories/files, listed per-part below.

## 1. Corrected bootstrap results

**The problem**: Phase 1's bootstrap ran an independent percentile bootstrap per seed and
averaged the three resulting `(ci_low, ci_high)` pairs after the fact — not a valid confidence
interval, since percentile bounds don't average linearly.

**The fix**: `revision_v3/src/evaluation/bootstrap_v2.py`'s `seed_aware_paired_bootstrap_ci` —
one family multiset drawn per bootstrap replicate, reused across all 3 seeds; the paired delta
is computed per seed on that shared resample and the three are averaged into one
replicate-level number; the CI is the percentile of the resulting 10,000 replicate-level
numbers. Point estimates are unchanged (verified numerically identical to Phase 1's for every
comparison); only the CI computation changed.

All 14 Phase 1 paired comparisons were recomputed:
`revision_v3/results/phase2_corrected_bootstrap/{controlled_ablation,model_candidate,matched_robustness}_bootstrap_corrected.csv`.

## 2. Which Phase 1 significance conclusions changed

**4 of 14 flipped from "not significant" to "significant"** (none flipped the other way — the
corrected method's CIs are uniformly narrower):

1. `chunk_attention_16384` vs. `flat_cnn_16384` (clean AUPRC): now **significant**, flat CNN
   wins (Δ=−0.025, CI[−0.051,−0.003]).
2. `chunk_attention_16384` vs. `chunk_max_16384` (Recall@5%): now **significant**, attention
   wins (Δ=+0.037, CI[+0.012,+0.068]).
3. `authguard_sequence_ngram` vs. reference (clean AUPRC): now **significant**, ngram hybrid
   is worse (Δ=−0.029, CI[−0.054,−0.003]).
4. `authguard_all_views` vs. reference (clean AUPRC): now **significant**, the 3-view hybrid is
   worse (Δ=−0.035, CI[−0.064,−0.006]).

10 of 14 kept the same significance direction. Full detail:
`revision_v3/reports/CORRECTED_BOOTSTRAP_REPORT.md`.

## 3. Parameter-matched clean results

A Flat CNN narrowed to `embedding_dim=32, channels=60` gives **38,885 active parameters**
(+0.84% vs. the reference's 38,562 — within the required ±10%). Trained at 2,048/8,192/16,384
tokens. Clean comparison is **budget-dependent, not a uniform winner**: hierarchy
significantly wins at 2,048 tokens (Δ=+0.033 AUPRC, +0.112 Recall@5%, both CIs exclude zero);
the matched flat CNN significantly wins at 8,192 (Δ=−0.030 AUPRC, CI excludes zero); neither
wins significantly at 16,384. Crucially, **the original 4×-larger flat CNN's significant
16,384-budget advantage (item 1 above) disappears once parameters are matched** — evidence the
original advantage was substantially a capacity effect. Full detail:
`revision_v3/reports/PARAMETER_MATCHED_COMPARISON_REPORT.md`.

## 4. Parameter-matched robustness results

Reusing Phase 1's flooding implementation for direct comparability: the reference model's
Flood-200% advantage over flat CNN, which was significant at **every** budget against the
*original* (4×-larger) flat CNN in Phase 1, **only survives at 2,048 tokens** against the
parameter-matched flat CNN (8,192: Δ=+0.021, CI crosses zero; 16,384: Δ=+0.010, CI crosses
zero). This was the first strong signal that Phase 1's robustness story was partly a
parameter-capacity effect — later confirmed and extended by the final protocol (item 5).

## 5. Chunk-max robustness result

Under the **final, paper-grade** flooding protocol (executable-region-aware, multi-donor,
3 independent transformation seeds — see item 5 below), attention pooling does **not**
significantly outperform max pooling on Flood-200% AUPRC (Δ=+0.018, CI[−0.031,+0.067],
Question A of `FINAL_ROBUSTNESS_CONFIRMATION_REPORT.md`). Combined with item 3/4's finding
that the reference is also not significantly more robust than *either* flat CNN variant under
this protocol (Questions C), **none of the original architecture-vs-architecture robustness
claims survive the final protocol** — only the sequence+dense hybrid comparison does (next
item).

## 6. Sequence+dense robustness confirmation

**Confirmed, not just a lead.** `authguard_sequence_dense` significantly outperforms the
reference under the final flooding protocol: Δ=+0.052 AUPRC, 95% CI [+0.030, +0.077], excluding
zero (Question B). Magnitude is practically meaningful (~6% relative improvement over the
reference's 0.853 flood AUPRC). This model also has the lowest donor-selection variance of all
5 models tested (Question D: mean SD across 3 independent donor-selection seeds = 0.055, vs.
0.066–0.109 for the other four), meaning its robustness is also the most reproducible across
different specific flooding draws.

## 7. Final frozen model selection

**`authguard_sequence_dense` replaces `authguard_reference_v3` as the frozen final model.**
Applying the stated policy ("keep the reference unless another model shows a statistically
supported and practically meaningful advantage"): the original large flat CNN's only
significant advantage (clean AUPRC) does not survive parameter-matching and is disqualified;
`authguard_sequence_dense`'s robustness advantage does survive every control applied in this
phase and is additionally supported by better calibration (Brier 0.0753 vs. 0.0796), the
closest observed FPR to the nominal 5% target of all 5 candidates (0.053), and the tightest
clean-AUPRC dispersion across seeds (±0.004). Trade-off: 2.5× the reference's active parameters
(97,645 vs. 38,562). Full reasoning and decision table:
`revision_v3/reports/FINAL_MODEL_SELECTION.md`. Frozen configuration:
`revision_v3/configs/final_model.json`; provenance manifest with checkpoint SHA-256 hashes:
`revision_v3/results/final_model_manifest.json`.

**This selection has not been validated against any independent human label** (none exist) —
flagged explicitly as a re-examination point once Gold-Dev/Gold-Test labels exist.

## 8. Annotation application status

`revision_v3/annotation_app/` — minimal FastAPI + SQLite + server-rendered Jinja2 HTML, no
Node/React/Vue build system. Implements: blinded assignment (evidence packets structurally
cannot carry model scores or source labels — enforced at the packet-builder level, not just by
UI omission), save/resume (draft annotations), independent double-review, dynamic
third-reviewer adjudication on disagreement (Gold-Test) and dynamic second-review triggering
(Gold-Dev: 20% random pre-selection + automatic escalation on `LOW` confidence /
`INDETERMINATE` / `NOT_BYTECODE_SCREENABLE`), a progress dashboard, an audit log (every view
and submit action recorded), Cohen's/Fleiss' kappa agreement statistics
(`annotation_app/agreement.py`), and an exportable release schema with an explicit adjudication
rule (`annotation_app/export.py`).

**Verified end-to-end with real data and zero fabricated labels**: the app was seeded with the
actual 230 Phase 2 sample-set items (`revision_v3/human_eval/*.csv`), producing 400 real
assignments (40 pilot + 60 gold_dev + 300 gold_test). A synthetic disagreement was injected via
the FastAPI TestClient to prove the adjudicator auto-assignment and export-finalization logic
work correctly (`R1=SAFE`, `R2=UNSAFE` on a test item → `R3` auto-assigned as adjudicator,
correctly shown both prior labels, export correctly reports
`UNRESOLVED_DISAGREEMENT_NO_ADJUDICATION` until the adjudicator submits) — that test data was
then discarded. **The persisted `annotation_app/annotation.db` has 230 items, 400 assignments,
and 0 annotations** (verified in `test_phase2_no_writes_to_frozen.py`'s companion checks and
directly via `sqlite3` query) — no human annotation was performed, satisfying the stop
condition structurally, not just procedurally.

## 9. Evidence-packet status

`revision_v3/src/evidence/` — `packet_builder.py` (template-based, deterministic, no LLM),
`proxy_detection.py` (EIP-7702 designator, EIP-1967 slot constants, DELEGATECALL-pattern,
admin/ownership selector heuristics), `selectors_table.py` (standard OpenZeppelin-style
ownership/admin/init ABI signatures), `explorer_links.py`, `known_projects.py` (45-entry
lookup from the existing `fetch_benign_7702_delegates.py`, read-only). **Structurally
enforced blinding**: `build_evidence_packet` raises `ValueError` if given any of `label`,
`label_semantics`, `authguard_score`, `calibrated_score`, `raw_score`, or 6 other
forbidden-field names (`FORBIDDEN_FIELDS`, tested in `test_phase2_blinding.py`). Fields not
available offline (decompiled source, verified-source status, authorization/transaction
history) are explicitly marked `NOT_AVAILABLE_OFFLINE` with a reason — never fabricated or
silently omitted.

## 10. Pilot / Gold-Dev / Gold-Test sampling statistics

Sampling unit: unique exact runtime bytecode (`bytecode_sha256`), not address rows. Full
protocol: `revision_v3/human_eval/SAMPLING_PROTOCOL.md`.

| Set | Target | Achieved | Notes |
|---|---:|---:|---|
| Pilot | 20 | 20 | 7 positive, 7 unflagged, 6 known-disagreement; 7 chains; both reviewers on every item |
| Gold-Dev | 60 | 60 | 4 model-score strata + a documented 10-item backfill (see below); family-disjoint from Gold-Test |
| Gold-Test | 150 | 150 | 50 positive / 100 unflagged (population-proportional, **no model score used in selection**); 126 distinct families; all 7 chains represented; frozen and hashed |

**Honestly documented shortfall**: Gold-Dev's `positive_low_score` stratum (source-positive,
below-median model score — the model's "hardest misses") targeted 15 items but only 5 distinct
families exist for this stratum anywhere in the primary population (8 before Gold-Test's random
family exclusion). The shortfall of 10 was backfilled from `unflagged_high_score` and labeled
distinctly (`unflagged_high_score_backfill`) rather than silently absorbed — itself a
substantive finding: the model rarely produces confident low scores on true positives.

Gold-Test frozen hashes (`gold_test_hashes.json`): SHA-256 of the sorted bytecode-hash list,
SHA-256 of the sorted family-ID list, sampling seed (770220262), UTC timestamp — verified
reproducible by `test_phase2_human_eval_sampling.py`.

## 11. Temporal collector pilot results

Full infrastructure: `revision_v3/src/temporal/` (`rpc_client.py` with a binary-search
date→block resolver, `collector.py` with checkpointed sequential block scanning,
`enrich.py` with exact-hash and opcode-4-gram family matching against all 790 historical
families). **Real pilot, both required chains, at the actual start of the target window**
(block found via binary search, not estimated): 300 consecutive blocks each on Ethereum
(starting block 24,358,293, timestamp 2026-02-01 00:00:11 UTC) and Base (block 41,557,327,
2026-02-01 00:00:01 UTC).

| | Ethereum | Base |
|---|---:|---:|
| Type-0x4 (EIP-7702) transactions | 270 | 113 |
| Authorization entries | 276 | 113 |
| Unique delegates | 32 | 12 |
| Matches to an existing historical family | 14 | 7 |
| Previously unseen families | 18 | 5 |
| Throughput | 6.91 blocks/s | 1.40 blocks/s (rate-limited) |

**A real infrastructure finding, not a simulated one**: `base-rpc.publicnode.com`'s free tier
returned `"pruned history unavailable"` for this historical block range; `base.drpc.org` served
it correctly and was promoted to primary endpoint for Base. Checkpoint/resume was exercised
under real transient failures (2 rate-limit errors) across 3 separate invocations and recovered
correctly each time with no duplicate or skipped blocks. Full-window extrapolation from
measured throughput: Ethereum ~1.8 days, **Base ~53 days at this rate-limited throughput** —
Base is the binding constraint for any full collection, not Ethereum; full detail and
recommended next steps in `revision_v3/reports/TEMPORAL_COLLECTION_REPORT.md`. **No label of
any kind was attached to any of the 44 pilot delegates.**

## 12. Legitimate candidate-set statistics

`revision_v3/experiments/external_controls/build_legitimate_candidates.py` →
`revision_v3/external_controls/`. **8 documented projects, 45 chain-deployments, 30 unique
project-bytecode pairs** — below the brief's 20–50 target, honestly reported as such rather
than padded: no second source of *documented* legitimate EIP-7702 delegates exists in this
repository (the only other lead, `legitimate_registry_expansion_v1`, lives on an unmerged
branch and was already flagged by its own text as insufficient for anything beyond leakage-risk
screening). Confirms and extends the prior finding that 3 of 8 projects are not byte-identical
across every chain they deploy to.

## 13. Test results

**65 of 65 tests pass** (32 Phase 1 + 33 new Phase 2 tests), covering: corrected bootstrap
correctness (shared-family-multiset regression test), parameter-matching tolerance and
reference-architecture non-modification, Gold-Dev/Gold-Test family and exact-bytecode
isolation, frozen Gold-Test hash reproducibility, evidence-packet score/label blinding
(positive rejection test), legitimate-candidate provenance field completeness, temporal
deduplication (Jaccard similarity edge cases, address→single-bytecode consistency),
determinism (strict-mode verification + real two-run replay), and no-writes-to-Phase-1-frozen
(hash comparison + a live frozen-guard subprocess call). Command:
`python3 -m pytest revision_v3/tests -q` → `65 passed in ~88s`.

## 14. Deterministic replay result

`torch.use_deterministic_algorithms(True)` in **strict mode** (not `warn_only`) is now enabled
by `revision_v3/src/training/harness.py`, gated on `CUBLAS_WORKSPACE_CONFIG=:4096:8` being set
before the CUDA context initializes (the harness sets this via `os.environ.setdefault` before
`import torch`). **No operation in this codebase was found to lack a deterministic
implementation** — `NON_DETERMINISTIC_OPERATIONS_FOUND` is empty; strict mode was verified to
run without exception for every model architecture used in this project.

Replay test (`authguard_sequence_dense`, fold 0, seed 7702, full training run, twice): **the
two runs produced bit-for-bit identical test predictions (max absolute difference = 0.0)** —
strictly stronger than the "numerically equivalent" bar the brief asks for. This closes the
exact gap Phase 1's `REFERENCE_VALIDATION_REPORT.md` identified (two nominally-identical
Phase 1 runs differed by up to 0.026 on Recall@5%, once nearly failing the reference-validation
gate) — with strict mode, that class of run-to-run variance is eliminated entirely, not just
reduced.

## 15. Remaining human tasks

1. **Reviewer time**: 400 real assignments are seeded and ready (`annotation_app`); actual
   human annotation has not started (explicitly out of scope for this phase).
2. **Gold-Dev / Gold-Test evaluation**: `evaluate_against_human_labels.py` is written and
   unit-tested on synthetic data (`test_human_label_evaluation_code.py`) but has never been run
   on real data — it will raise deliberately if pointed at an empty release export.
3. **Temporal collection decision**: whether to proceed with a multi-day, rate-limit-budgeted
   full collection given the measured Base throughput constraint (~53 days at current
   throughput) — requires a human decision on RPC budget/credentials or accepting reduced
   sampling density on Base specifically.
4. **Legitimate candidate expansion decision**: whether to invest in systematic verified-source
   registry scanning to grow the 8-project candidate set, given no second source was found in
   this repository.
5. **Final model selection re-examination**: once Gold-Dev/Gold-Test labels exist, re-run the
   comparison in `FINAL_MODEL_SELECTION.md`'s spirit against human labels — this phase's
   selection is provisional on source-analyzer-label evidence only, by design.

## 16. Exact commands to continue to Phase 3

```bash
python3 revision_v2/experiments/common/frozen.py verify   # before

# resume/expand the temporal collection (budget-aware; Base needs a rate-limit strategy)
python3 revision_v3/src/temporal/collector.py  # (invoke scan_block_range per chain/run_id)

# once real reviewers are available:
#   1. decide the reviewer roster and set PRIMARY_REVIEWER_PAIR / SECOND_REVIEWER_POOL / ADJUDICATOR_POOL
#   2. seed (already done for this phase's 230 items; re-run if the manifest changes):
python3 revision_v3/annotation_app/seed_from_packets.py <manifest.csv>
#   3. serve the app:
cd revision_v3/annotation_app && uvicorn app:app --port 8420
#   4. after annotation: export and evaluate
python3 revision_v3/annotation_app/export.py gold_test
python3 revision_v3/experiments/human_label_evaluation/evaluate_against_human_labels.py \
    revision_v3/annotation_app/release_gold_test.json gold_test

python3 -m pytest revision_v3/tests -q                     # after
python3 revision_v2/experiments/common/frozen.py verify    # after
```

## Stop condition compliance

No human annotation was begun (0 rows in `annotations` table). No Gold-Dev label was used
anywhere (none exist). No PU-learning or label-noise-aware training was started. No Gold-Test
label was opened (none exist; the export/evaluation scripts raise deliberately on empty
input). No manuscript file was touched. All infrastructure, sampling manifests,
model-finalization experiments, and collection reports listed above are complete.
