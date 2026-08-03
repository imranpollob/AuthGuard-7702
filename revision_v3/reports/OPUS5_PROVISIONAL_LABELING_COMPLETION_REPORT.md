# Opus 5 Provisional Labeling — Completion Report

**LABEL_SOURCE=LLM_PROVISIONAL_OPUS5 · STATIC_ANALYZER_EVIDENCE=VISIBLE ·
STATUS=PROVISIONAL_PENDING_HUMAN_REVIEW**

**PROVISIONAL — OPUS 5 LABELS WITH STATIC-ANALYZER EVIDENCE.** These are not human labels,
expert labels, gold labels, ground truth, or independently verified labels. They replace
nothing: the previous provisional labels, the source-rule labels, and the (still empty)
human-final labels all remain separate.

---

## 1. Model and session information

| | |
|---|---|
| Labeling model | Claude Opus 5 (`claude-opus-5`) |
| Date | 2026-08-01 |
| Branch | `tps-revision-v3` |
| Items labeled | 230 (Pilot 20, Gold-Dev 60, Gold-Test 150) |
| Static-analyzer evidence | **visible** (verdict + per-address rule facts) |
| AuthGuard item-level score/prediction | **withheld** (enforced structurally and tested) |
| Method | evidence dossiers → documented decision framework → per-item review, with every departure recorded in `overrides.py` |

**How the labeling was actually done, stated plainly.** Each item's evidence was assembled
into a dossier and rendered as a readable brief. The reasoning applied to those briefs is
written out as an explicit decision procedure
(`revision_v3/experiments/opus5_labeling/opus5_label.py`) so that the same judgement is applied
identically to all 230 items and every label is auditable against the evidence that produced
it. All 20 Pilot items were then reviewed individually against their briefs; Gold-Dev and
Gold-Test were reviewed by pattern class, with at least one representative of every distinct
(guard classification × unguarded-operation shape × coverage status) combination inspected.
Three corrections found that way were general enough to fold back into the framework rather
than record as one-off overrides (§10); five item-specific departures are recorded as
overrides with written justifications. This is a language model's judgement expressed as an
explicit rule set plus review — not 230 independently composed essays, and it is described
that way deliberately.

## 2. Context files reviewed before labeling

Recorded in full in `OPUS5_LABELING_CONTEXT_SUMMARY.md` §8. The materially consequential
readings were:

- **`USENIX EIP-7702 artifact/eoa_detect/decompile/analyze.dl`** and its shipped
  `detect_result.jsonl` — establishing exactly what `source_label` means (§4).
- **`revision_v2/audit/DATASET_AUDIT_REPORT.md`** — the source-detector circularity finding,
  and the statement that the negatives are rule-silent with *no benignity verification of any
  kind*.
- **`revision_v2/results/gigahorse/feasibility.md`** — the analyzer pipeline was never
  re-executed in this environment; all analyzer facts come from shipped intermediate outputs.
- **`revision_v3/experiments/excel_review/evidence_pipeline.py`** — the previous guard tracer,
  whose method explains the previous pass's 87% UNSAFE rate.
- The v3 manuscript draft, reviewer guide, labeling protocol, sampling protocol, pilot evidence
  report, legitimate-control and temporal reports, and the previous completion report.

## 3. Evidence supplied per item

Contract identity (chain, address, runtime hash and size, family, chains sharing the exact
bytecode, documented-project match where one exists with its documentation URL and provenance
grade); source and code evidence (live Sourcify/Blockscout verification status, resolved
selectors, embedded address constants, extracted strings, storage layout, live storage reads);
proxy/implementation evidence (DELEGATECALL presence and resolved targets, storage-held
implementation pointers); guard evidence from a **new CFG guard-dominance analysis**
(`evm_cfg.py`) with per-function status, the semantics of each guard and the value it compares
against, and the shape of every unauthenticated sensitive operation; a **static opcode census**
used as a soundness backstop; on-chain state from the previous pass's live collection; and the
previous provisional review as context to reassess.

**Why the guard analysis was rebuilt.** The previous tracer scanned the contiguous byte window
between dispatch offsets for `CALLER|ORIGIN … EQ … JUMPI`. It cannot follow a jump, so it could
not see guards in shared internal helpers (what a Solidity `modifier` compiles to), signature
checks, or storage-based permission checks, and it never established that the sensitive opcode
was reachable at all. Its `OPEN` meant "no pattern in this window", not "no access control".
The replacement disassembles, builds a CFG, resolves dynamic jumps with a bounded symbolic
stack, tracks value provenance, and reports a sensitive operation as unauthenticated only if it
**survives cutting traversal at every authorization-tainted branch** — a demonstrated path
rather than an absent pattern.

## 4. Static-analyzer information supplied

The `source_label` in every manifest comes from the USENIX `eoa_detect` Gigahorse/Soufflé
pipeline. Verified against the shipped facts: 793 addresses, 866 tuples, and **every tuple's
enclosing function is `receive()` (765) or `fallback()` (101)**. The operative rule is a single
interprocedural reachability test —

> an external `CALL`/`DELEGATECALL` is reachable from `receive()` or `fallback()`

— **with no authorization predicate anywhere in it**. Each item's dossier carried the verdict,
the per-address firing tuples (enclosing function, call statement, inferred callee signature),
an explicit statement that the rule does not model authorization, and a **local re-derivation
of the rule's own question** (seed a non-matching selector, follow the receive/fallback path,
report both whether an external call is reachable and whether it is reachable without passing a
caller guard).

Result of that re-derivation across all 230 items: **CONFIRMED 203, PARTIALLY_CONFIRMED 12,
CONTRADICTED 15**.

## 5. Items labeled

| set | items | fully analysed | coverage gap recorded | manual overrides |
|---|---|---|---|---|
| Pilot | 20 | 20 | yes, per item | 5 |
| Gold-Dev | 60 | 60 | yes, per item | 0 |
| Gold-Test | 150 | 150 | yes, per item | 0 |

Gold-Test was **not** used for anything other than one-shot evaluation: no threshold, model,
loss, or cascade policy was chosen using it (tested).

## 6. Label distributions

| set | SAFE | UNSAFE | UNCERTAIN | (previous pass) |
|---|---|---|---|---|
| Pilot | 2 | 13 | 5 | 9 / 6 / 5 |
| Gold-Dev | 10 | 39 | 11 | 5 / 42 / 13 |
| Gold-Test | 20 | 108 | 22 | 7 / 131 / 12 |
| **all** | **32** | **160** | **38** | 21 / 179 / 30 |

## 7. Confidence distributions

| set | HIGH | MEDIUM | LOW |
|---|---|---|---|
| Pilot | 3 | 13 | 4 |
| Gold-Dev | 22 | 25 | 13 |
| Gold-Test | 37 | 68 | 45 |
| **all** | **62** | **106** | **62** |

LOW is assigned wherever the traversal hit an exploration cap, underflowed its stack model, or
left a sensitive opcode unreached — i.e. confidence tracks the analysis's own coverage.

## 8. Source-rule agreement (descriptive only — see §15)

| Opus 5 label | source rule = positive | source rule = unflagged |
|---|---|---|
| SAFE | 4 | 28 |
| UNSAFE | 71 | 89 |
| UNCERTAIN | 6 | 32 |

71/81 source-positive items are UNSAFE. The more informative number is the other one: **89 of
the 160 UNSAFE labels are on items the source rule never flagged**, so these labels are not a
restatement of the rule. That is consistent with the dataset audit's own finding that the
negatives are rule-silent rather than verified benign.

## 9. Previous-LLM agreement

Exact 3-class agreement **147/230 (63.9%)**; 83 items changed.

| previous \ Opus 5 | SAFE | UNSAFE | UNCERTAIN |
|---|---|---|---|
| SAFE | 7 | 13 | 1 |
| UNSAFE | 22 | 130 | 27 |
| UNCERTAIN | 3 | 17 | 10 |

Full per-item listing in `OPUS5_LABEL_COMPARISON_REPORT.md` §4.

## 10. Changed-label analysis

| cause | items |
|---|---|
| guard newly visible to CFG analysis (missed by the linear-window tracer) | 29 |
| linear-window tracer's `OPEN` reinterpreted as incomplete evidence | 21 |
| opcode-census soundness rule (no caller-based access control can exist) | 11 |
| EIP-7702 reinterpretation of a hardcoded-caller guard | 10 |
| memory-provenance limitation acknowledged (capability, not exploit) | 5 |
| re-derived control-flow evidence | 4 |
| manual review override | 3 |

Three corrections were general enough to change the framework rather than individual labels:

1. **Argument provenance from a function whose stack model was padded is untrustworthy** and
   can no longer support a concrete-exploit claim.
2. **A runtime containing no `CALLER` and no `ORIGIN` opcode cannot contain caller-based access
   control** — a claim that holds regardless of traversal completeness, so it resolves
   coverage-gap items soundly instead of defaulting them to UNCERTAIN.
3. **A hardcoded-address check on a callback-shaped entry point is the protocol's prescribed
   pattern**, not third-party access. Found from a real false positive: a Uniswap v4
   `unlockCallback` restricted to the PoolManager.

**The single most consequential judgement in this pass** is that `require(msg.sender ==
0xHARDCODED)` in an EIP-7702 delegate is *not* protection for the authorizer. The literal was
fixed when the delegate was deployed, so it cannot be the authorizing EOA: it names a fixed
third party with exclusive privileged access to the account's assets. This is correct for a
delegate and wrong for an ordinary contract, and it is why several items the previous pass read
as SAFE (`withdrawAnyToken(address)` gated to a fixed address, `rescueETH()` gated to a fixed
address, `forward(address,bytes)` behind a "RestrictedRouter: unauthorized" check) are now
UNSAFE. It is stated prominently because a human reviewer who disagrees with it should overturn
a large block of labels at once.

## 11. Class-imbalance analysis

Full audit in `OPUS5_LABEL_QUALITY_REPORT.md`. Headline results:

- **Every UNSAFE support class is concrete.** `SOURCE_RULE_ONLY_SUPPORT` and
  `INCOMPLETE_GUARD_EVIDENCE` cannot reach the UNSAFE branch of the decision cascade at all;
  **0 of 160** UNSAFE labels rest on weak support (tested).
- **The guard picture changed materially**: the old tracer reported `OPEN_FOUND` for 50/60
  Gold-Dev and 140/150 Gold-Test; the CFG analysis finds a genuinely unauthenticated path in
  far fewer, and finds guard-dominated behaviour in many the old tracer called open.
- **Per-family UNSAFE rates track per-item rates**, so the imbalance is not a duplicated-
  bytecode artefact.
- **The population is enriched for this hazard by construction.** The sampling frame's positive
  class is *defined* as delegates with an external call reachable from `receive()`/`fallback()`,
  and many of these contracts are bare executor/forwarder designs whose entire purpose is to let
  some party direct calls from the account — which, as a 7702 delegate, is the hazard itself.

## 12. Uncertain items

38/230 (16.5%). Reasons: `DECOMPILATION_AMBIGUITY` (analysis provably incomplete — a sensitive
opcode the traversal never reached, an exploration cap, or a padded stack) and
`INSUFFICIENT_EVIDENCE` (no unauthenticated path demonstrated and no positive authorization
control confirmed). UNCERTAIN is preserved as a first-class label everywhere and excluded from
binary metrics with the exclusion rate reported alongside (tested).

## 13. Provisional model results (Opus 5 labels)

**Gold-Dev** (49 binary, 11 UNCERTAIN excluded = 18.3% coverage):

| model | AUPRC | AUROC | recall | FPR |
|---|---|---|---|---|
| flat_cnn_16384 | 0.943 | 0.815 | 0.410 | 0.100 |
| flat_cnn_matched_16384 | 0.932 | 0.759 | 0.410 | 0.100 |
| authguard_sequence_dense | 0.920 | 0.726 | 0.410 | 0.100 |
| authguard_reference_v3 | 0.919 | 0.723 | 0.410 | 0.100 |
| source static rule | — | — | 0.410 | precision 0.941 |

**Notable**: AUROC rises from 0.610 under the previous labels to 0.726–0.815 here, and the
four models no longer collapse onto an identical confusion matrix. The re-labeled targets are
measurably more separable by bytecode-only models than the previous pass's targets were.

**Retraining** (10 methods, Gold-Dev only, family-grouped 3-fold × 3 seeds):
`soft_label_confidence` won on the stability-adjusted criterion (mean 0.929, std 0.050);
`source_plus_provisional_weighting` 0.928, `plain_finetune` 0.927, baseline 0.889.

**Two real bugs were found and fixed in the selection stage during this rerun**, both of which
would have invalidated Part 11's requirement that selection use only Gold-Dev Opus 5 labels:

1. the winning method was a **hardcoded constant carried from the previous pass**, so a rerun
   would have reported a selection it never actually made — now derived from this label
   source's own results;
2. the final training loop applied confidence-weighted BCE **regardless of which method won**,
   so a different winner would have been reported but not trained — now branches on the
   selected method.

**Gold-Test** (128 binary, 22 UNCERTAIN excluded = 14.7%), one shot, no tuning after:

| model | AUPRC [95% CI] | recall | FPR |
|---|---|---|---|
| flat_cnn_16384 | 0.926 [0.864, 0.972] | 0.435 | 0.200 |
| flat_cnn_matched_16384 | 0.916 [0.849, 0.967] | 0.435 | 0.200 |
| authguard_sequence_dense | 0.915 [0.850, 0.965] | 0.426 | 0.200 |
| authguard_reference_v3 | 0.911 [0.842, 0.963] | 0.435 | 0.200 |
| provisional_final_model | 0.909 [0.833, 0.970] | 0.972 | 0.950 |
| source static rule | — | 0.426 | precision 0.939 |

All confidence intervals overlap; the AUPRC ranking is not statistically distinguishable at
this sample size.

**Cascade** (band selected on Gold-Dev only, frozen, evaluated once): AuthGuard-first with
static-rule escalation escalates 21.9% of Gold-Test and recovers the rule's FPR (0.150 vs.
AuthGuard-alone 0.200) at the same recall.

**Legitimate controls** — closing a gap the previous pass recorded as an open follow-up: all 30
documented deployments scored at the frozen operating threshold, reported per provenance
category: **0/22 VERIFIED_LEGITIMATE_CONTROL flagged, 0/8 CANDIDATE_LEGITIMATE_CONTROL
flagged**. (A first attempt at this produced a spurious 30/30 by applying a sigmoid to scores
that were already calibrated probabilities; the error was caught by checking against how the
baseline script computes them, and is noted here because the corrected number is favourable and
should not be taken on trust.)

## 14. Threshold results

The provisional final model again shows the failure the previous pass surfaced: competitive
AUPRC (0.909) with a **degenerate operating threshold** — recall 0.972 at FPR 0.950, i.e. it
predicts almost everything UNSAFE. Two of three seeds calibrated to `threshold_5pct ≈ 0.000` on
a ~10-item internal split. This reproduces under a different label source and a different
selected loss, which strengthens rather than weakens the previous pass's conclusion: **with ~49
calibration items, a good ranking metric does not buy a usable operating point.** The frozen
Phase 1/2 thresholds, by contrast, transfer sensibly (FPR 0.100 on Gold-Dev, 0.200 on
Gold-Test).

## 15. Static-comparison limitation (binding)

Because these labels were produced **with** the source static analyzer's verdict and its
per-address rule facts visible:

- the source analyzer **contributed evidence to the provisional reference decision**;
- static-rule agreement metrics computed against these labels are **descriptive**, not an
  independent evaluation of the analyzer;
- **independent comparison requires the later human-final labels**;
- **final paper claims must be regenerated using `human_final_label`.**

This paragraph is repeated in `OPUS5_LABEL_QUALITY_REPORT.md` §7 and is asserted by a test.

## 16. Files generated

**Labels and reviews** — `revision_v3/results/llm_provisional_opus5/`:
`{pilot,gold_dev,gold_test}_labels_opus5.csv`, `{...}_reviews_opus5.json`,
`{...}_labels.json` (pipeline-compatible projection), `dossiers/{...}_dossiers.json`.

**Pipeline outputs** (same directory): `gold_dev_baseline/`, `retraining/`,
`provisional_final_model_manifest.json`, `provisional_final_model_checkpoints/`, `gold_test/`,
`cascade/`, `legitimate_controls/control_evaluation.json`, `temporal/`,
`workbook_update_manifest.json`.

**Config**: `revision_v3/configs/provisional_final_model_llm_provisional_opus5.json` (the
previous `provisional_final_model.json` and the Phase 2 `final_model.json` are untouched).

**Assets**: `revision_v3/manuscript_assets/provisional_llm_provisional_opus5/` — 6 tables and
4 figures, each carrying "PROVISIONAL — OPUS 5 LABELS WITH STATIC-ANALYZER EVIDENCE".

**Reports**: `OPUS5_LABELING_CONTEXT_SUMMARY.md`, `OPUS5_LABEL_COMPARISON_REPORT.md`,
`OPUS5_LABEL_QUALITY_REPORT.md`, this file.

**Code**: `revision_v3/experiments/opus5_labeling/` — `evm_cfg.py` (CFG + symbolic stack),
`build_dossiers.py`, `render_briefs.py`, `opus5_label.py` (the decision framework),
`overrides.py` (the audit trail), `run_opus5_labeling.py`, `analyze_labels.py`,
`run_controls_and_temporal.py`, `update_review_workbooks.py`.

**Workbooks**: the three review workbooks gained 9 columns (Opus 5 label, confidence,
rationale; static-analyzer verdict and a plain explanation of what it does and does not mean; a
words-first code summary; guard-tracer result; project/on-chain evidence; unresolved
questions). All human columns are blank and the updater refuses to run against a workbook where
any human column is filled; a timestamped backup was written before each modification.
Reviewers are never required to read raw bytecode.

## 17. Tests

`revision_v3/tests/test_opus5_labeling.py` — **55 new tests**, covering: full output schema;
`human_final_*` never populated; no Opus 5 label copied into a human field; four label sources
kept as distinct fields; valid labels/confidences; banner present in every JSON and CSV;
reports watermarked; the static-comparison limitation actually stated; UNCERTAIN preserved;
binary evaluation excludes UNCERTAIN and reports coverage; no UNSAFE on weak support; every
SAFE/UNSAFE cites concrete evidence; no AuthGuard output anywhere in dossiers or labels; the
dossier builder never reads model columns; static-analyzer evidence deliberately present; model
selection never references Gold-Test; cascade band recorded as Gold-Dev-derived; Gold-Dev /
Gold-Test family disjointness; all four sampling manifests MD5-unchanged; previous provisional
results not overwritten; output-directory separation; Phase 2 and previous provisional configs
not replaced; coverage gaps recorded; no SAFE claim while sensitive opcodes went unreached;
every override carries a written justification and is marked in the output; the one-command
rerun supports the new source; `human_final` still refuses to fabricate; pipeline scripts
default to the previous label source; workbooks gained the columns and kept human columns blank.

Two of these tests **failed on first run and caught real defects** — an UNSAFE label whose
evidence text was never populated for the unrestricted-initializer path, and an incorrect key
name for the cascade band. Both were fixed.

**Full suite: 171/171 passed.**

## 18. Frozen-guard result

`revision_v2/experiments/common/frozen.py verify` → **OK, 144/144 frozen files unchanged.**

## 19. Git status

23 changed paths; 12 tracked-file modifications:

- 5 `experiments/llm_provisional/*.py` — label-source parametrization (defaulting to
  `llm_provisional`, so previous behaviour is reproduced byte-for-byte when unset), plus the two
  selection-stage bug fixes in §13.
- 2 `experiments/reporting/*.py` — same parametrization for tables and figures.
- 3 `human_eval/*_Code_Review.xlsx` — the added Opus 5 columns (§16), backups written.
- `run_reference_pipeline.py` — `llm_provisional_opus5` branch added.
- `results/human_final/run_manifest.json` — re-run of the blocked human-final check.

The rest are new files. **Nothing was committed.**

## 20. Remaining work requiring human labels

- **Final label validity.** These labels are provisional and were produced with analyzer
  evidence visible; they are input to human review, not a substitute for it.
- **Independent static-analyzer comparison** (§15) — blocked by construction until
  `human_final_label` exists.
- **Final model selection.** The current selection is explicitly a PROVISIONAL FINAL MODEL, and
  its threshold is degenerate (§14).
- **LLM-vs-human agreement.** `run_llm_vs_human_agreement.py` still writes
  `PENDING_HUMAN_LABELS`. It should be extended to compare **three** label sets (source rule,
  previous provisional, Opus 5) against the human labels, so the effect of showing the analyzer
  can be measured rather than assumed.
- **Temporal re-labeling.** The previous pass's temporal evidence directories retain only
  derived artifacts, not raw runtime bytecode, so the temporal items could not be re-labeled
  under this framework without re-fetching from chain. They remain at the previous pass's
  labels and **must not be mixed with the Opus 5 label set** — recorded as
  `NOT_REGENERATED_NO_LOCAL_BYTECODE` in `temporal/temporal_labels_opus5.json`.
- **`source_rule` pipeline mode** is still not parametrized for evaluation (unchanged from the
  previous pass, documented rather than silently reused).
- **Manuscript** remains unfinalized and must not be finalized on provisional metrics.

---

## Compliance with the stated final rules

All available supporting security evidence was used. Opus 5 was **not** blinded from the source
static-analyzer verdict — that verdict and its per-address facts were supplied for every item,
and assessed as CONFIRMED / PARTIALLY_CONFIRMED / CONTRADICTED / UNRESOLVED rather than adopted.
Opus 5 was **not** shown any AuthGuard item-level prediction or score (structurally omitted from
the dossier builder; asserted by tests). No `human_final_label` was populated anywhere. No
sampling manifest was modified (MD5-verified). No model, threshold, loss, or cascade policy was
tuned using Gold-Test. No previous provisional result, config, or asset directory was
overwritten — every Opus 5 output lives under its own namespace. These labels are **not** human
ground truth and are labeled as such in every file that carries them. Nothing was committed.
