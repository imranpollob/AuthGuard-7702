# AuthGuard-7702 — Comprehensive Project Status

Compiled 2026-08-01 on branch `tps-revision-v3`. Every number below was read from a repository
artifact at compile time; sources are named inline so each can be re-checked.

---

## 1. What the project is

**The problem.** EIP-7702 lets an externally-owned account (EOA) sign an authorization that
installs a delegation designator `0xef0100 ‖ address` in its own code field. From then on,
calls to that EOA execute the delegate contract's code — but **in the EOA's own storage,
balance, and identity context**. Whatever the delegate's code can do, it does with the
authorizer's assets and permissions.

The security decision therefore happens *before* the signature, at a moment when the usual
defences are unavailable: a freshly deployed delegate has no transaction history, no victim
reports, no counterparty graph, no reputation, and often no verified source. The only thing
reliably available at that instant is the delegate's **runtime bytecode**.

**The system.** AuthGuard-7702 is a bytecode-only pre-authorization screening tool. Given
runtime bytecode (or an address + RPC endpoint, or an authorization object) it returns a risk
score, a policy-derived warning level, directly observed opcode evidence, and structured JSON.
Its core model is a compact hierarchical opcode-sequence network that chunks the full opcode
stream, encodes local patterns with dilated convolutions, and aggregates contract-wide evidence
with attention.

**The benchmark.** AuthGuardBench-7702 (`revision_v2/data/authguardbench_7702_v2.csv.gz`),
3,082 rows:

| population | rows |
|---|---:|
| `PRIMARY_EVALUATION` | 2,190 (727 positive / 1,463 negative, 790 families) |
| `EXTERNAL_BENIGN_CONTROL` | 797 |
| `EXCLUDED_UNCERTAIN_INPUT` | 90 |
| `QUALITATIVE_CONTROL` | 5 |

**Where the labels come from — the fact that shapes everything else.** The positive class is
inherited from the USENIX EIP-7702 study artifact's `eoa_detect` pipeline (Gigahorse + Soufflé
Datalog). Its operative rule, read directly from
`USENIX EIP-7702 artifact/eoa_detect/decompile/analyze.dl` and verified against the shipped
`detect_result.jsonl` (793 addresses, 866 tuples), is a single reachability test:

> an external `CALL`/`DELEGATECALL` is reachable from `receive()` or `fallback()`

— and **every one of the 866 shipped tuples has `receive()` (765) or `fallback()` (101) as its
enclosing function**. The rule contains no authorization predicate whatsoever. The negatives
are the *rule-silent* complement of the same observed-delegate pool; `revision_v2/audit/
DATASET_AUDIT_REPORT.md` states plainly that for them **"no benignity verification of any kind
exists."**

---

## 2. Lineage

| stage | what it was |
|---|---|
| v1 (`paper_build/`, `pipeline/`) | original submission: detection framing, in-sample threshold fitting, single flooding donor |
| **revision_v2** (`revision_v2/`) | dataset audit + protocol repairs + reframing; produced the manuscript now under review. **Frozen** — 144 files under hash guard, never modified since |
| **revision_v3** (`revision_v3/`) | independent from-scratch reimplementation and the reviewer-response programme. Treats v2's dataset, family IDs, and folds as immutable inputs |

Commit trail on `tps-revision-v3`: `project audit` → `phase 1` → `phase 2` → `phase 3A` →
`human audit docs prepared` → `provisional label` → `llm labeling added`.

---

## 3. What revision_v2 claimed

### 3.1 The three stated contributions
From `revision_v2/reports/final_contribution_decision.md` (2026-07-17):

1. **AuthGuard-7702 screening tool** — integration-ready, bytecode-only CLI/Python tool
   (`scan-bytecode`, `scan-address`, `scan-authorization`) emitting score, warning level,
   observed evidence, provenance, JSON.
2. **Hierarchical full-bytecode opcode-sequence modeling** — chunked opcode stream, dilated
   convolutions, attention aggregation. Notably, the originally proposed multi-view multi-task
   fusion architecture was **rejected**; the sequence-only model was selected on held-out
   validation AUPRC.
3. **AuthGuardBench-7702 and operational evaluation** — family and exact-duplicate controls,
   benign controls, matched-FPR policies, bounded transformations, per-row predictions, paired
   family-clustered uncertainty, local runtime measurements.

### 3.2 The headline numbers (manuscript abstract, `revision_v2/paper_extended/main.tex`)

- Mean family-disjoint AUPRC across three seeds: **0.931 clean**, **0.910** under 200%
  donor-isolated flooding, **0.910** under combined selector/address rewriting + flooding.
- Strongest histogram+n-gram XGBoost baseline: **0.828 / 0.577 / 0.563**.
- Primary-seed paired family-clustered analysis: clean AUPRC **+0.057 (95% CI 0.002–0.118)**;
  recall at the 5%-FPR policy **+0.212**.
- 0.743 MB model; full local pipeline in **4.334 ms** mean, **14.073 ms** p95, over 3,000 CPU
  calls.

### 3.3 What v2 deliberately did *not* claim
The novelty boundary was fixed as *"to our knowledge, the first EIP-7702-specific ML-based,
bytecode-only pre-authorization delegate-risk screener"* — not the first EIP-7702 detector, not
the first bytecode ML detector. v2 also removed the v1 overclaims it had itself catalogued
("production-ready", "enabling real-time screening integration", "proves … seamlessly
integrated … without degrading the user experience"), and it makes **no speedup claim against
Gigahorse**, because that pipeline was never executed here
(`revision_v2/results/gigahorse/feasibility.md`: Soufflé absent, no container runtime, the
`clientlib/*.dl` includes are not shipped).

### 3.4 The admission v2 made about itself
`revision_v2/audit/DATASET_AUDIT_REPORT.md` Part 2, headed *"Source-detector circularity (the
central finding)"*, concludes without hedging:

> **"yes — the model is learning to reproduce the source detector."** The positive label is a
> deterministic function of the runtime bytecode the model receives.

Its own independent-validation funnel yielded **exactly one** truly novel confirmed positive →
verdict INSUFFICIENT DATA. The chosen response was reframing (screening / analyzer surrogate)
plus evidence-strength metadata, not new ground truth — because none could be minted from the
repository.

### 3.5 ⚠ One concrete discrepancy found while compiling this report

The manuscript abstract states *"2,280 primary contracts from 819 bytecode families."* The
benchmark file gives `PRIMARY_EVALUATION` = **2,190 rows / 790 families**. The difference is
exactly the 90 rows marked `EXCLUDED_UNCERTAIN_INPUT` (2,190 + 90 = 2,280; 790 + 29 = 819).

So the abstract counts inside its "primary corpus" 90 rows that the benchmark excludes from
evaluation and that revision_v3 does not train or evaluate on. This is a wording/number fix for
the manuscript — either state 2,190/790, or say explicitly that 2,280 rows were assembled of
which 90 were excluded as uncertain. **Not yet corrected in any manuscript file.**

---

## 4. The reviewer critique that defined revision_v3

`revision_v2/planning/reviewer_issue_map.md` catalogues ten issues with validity assessments.
Six were judged HIGH scientific risk:

| # | Issue | Verdict | Risk |
|---|---|---|---|
| 1 | Source-derived labels, insufficient independent validation | YES | **HIGH** — "near-fatal for a detection framing" |
| 2 | Conflicting identical-bytecode labels (23 hash groups, 103 rows) | YES, partially handled | MEDIUM |
| 3 | Threshold selection used in-sample fitted predictions | YES, confirmed by trace | **HIGH** |
| 4 | Transformations verified only as opcode-token identity, not execution equivalence | YES (scope limit) | MEDIUM |
| 5 | Insufficient baselines and feature ablations | YES | MEDIUM-HIGH |
| 6 | Family-threshold / family-weighting sensitivity untested | YES | MEDIUM |
| 7 | Flooding-donor leakage (one fixed donor on both sides) | YES, confirmed by trace | **HIGH** |
| 8 | Unsupported deployment and robustness claims | YES | **HIGH**, trivially fixable |
| 9 | Missing secondary-control results | PARTIALLY | LOW-MEDIUM |
| 10 | Incomplete reproducibility (no lockfile, no tests, hand-made tables) | PARTIALLY | MEDIUM |

Issues 3, 7 and 8 were repaired within v2 itself (corrected thresholds, donor-isolated
flooding, manuscript wording). **Issue 1 — label validity — could not be repaired inside v2 at
all**, and it is the reason revision_v3 exists.

---

## 5. What revision_v3 has done

### Phase 1 — Model defensibility (commit `e0d9aae`)
Independent from-scratch reimplementation: own EVM disassembler, tokenizer, chunking, feature
extraction, model architectures, training harness, metrics, bootstrap, robustness. No code
copied from v2 or from the abandoned `revision-3` branch; v2 read-only. Enforced by
`tests/test_no_v2_writes.py` and the 144-file frozen-hash guard.

### Phase 2 — Infrastructure and model finalization (commit `ad109fa`)
- **Corrected bootstrap** — fixed a "combine confidence intervals after the fact" statistical
  bug; replaced with a seed-aware, paired, family-clustered bootstrap.
- **Parameter-matched comparison** — built `flat_cnn_matched_16384` (38,885 params) so the
  comparison against the 154,177-param original Flat CNN is not a capacity artefact.
- **Controlled ablation**, **parameter accounting**, **final robustness** (donor-isolated
  Flood-200%).
- **Final model selection** under a decision rule fixed *before* the table was read ("keep
  `authguard_reference_v3` unless another model shows a statistically supported and practically
  meaningful advantage"). Result: switched to **`authguard_sequence_dense`** — not on clean
  AUPRC (+0.012, CI crosses zero) but on **robustness: Flood AUPRC +0.052 [+0.030, +0.077]**,
  the one comparison whose CI excludes zero in its favour. Honest counterweight recorded in the
  same table: `flat_cnn_16384` beats the reference on clean AUPRC by 0.025 [0.051, 0.003].
- **Sampling for human review** (seed 770220262, unit = unique runtime bytecode):
  **Gold-Test 150** built first, population-proportional (50 positive / 100 unflagged), *never*
  using model score, then frozen with hashes; **Gold-Dev 60** built excluding Gold-Test's
  families, deliberately stratified by label × model score; **Pilot 20** excluding both.
  A shortfall was documented rather than hidden: only 5 `positive_low_score` items existed
  after exclusion against a target of 15, backfilled from another stratum under a distinct
  label.

### Phase 3A — Human-review preparation (commit `85368db`)
Reviewer guide written from scratch for contributors with no EIP-7702 background; simplified
Excel review workbooks; per-item code-evidence packages (live Sourcify/Blockscout verification,
`evmole` decompilation, 4byte selector resolution, on-chain proxy resolution); pilot evidence
hand-traced.

### Phase 3B — Full provisional pipeline (commits `7d96652`, `02ea144`)
Human review runs on its own timeline, so the entire downstream research pipeline was built and
exercised against **LLM-provisional labels**, so that real human labels can later be dropped in
with one command. Delivered: evidence enrichment for all 230 items; a labeling protocol;
Gold-Dev baseline; 10 retraining methods; provisional model selection; one-shot Gold-Test
evaluation; static-rule and cascade evaluation; temporal collection across 7 chains;
legitimate-control verification (30 deployments); deployment benchmarking incl. ONNX;
ML-vs-static positioning; tables/figures; a 9-file manuscript draft; a one-command rerun
script; a pending LLM-vs-human agreement pipeline; a 20-row reviewer-concern closure matrix.

**The most valuable output of that pass was a negative result**: the selected provisional model
ranked #1 by AUPRC (0.968) but had a **degenerate operating threshold** — recall 1.0 at FPR
0.857. A competitive ranking metric bought no usable operating point, and only end-to-end
evaluation exposed it.

### Phase 3C — Opus 5 relabeling with static-analyzer evidence (this session)
The previous provisional labels came out **87% UNSAFE** (Gold-Dev 5/42/13, Gold-Test
7/131/12), which is not a credible security distribution. This pass re-derived all 230 labels
with the static analyzer's verdict **visible** (it had been blinded before) and diagnosed the
imbalance.

**Root cause found.** The previous guard tracer was a *linear byte-window scan* — it looked for
`CALLER|ORIGIN … EQ … JUMPI` within 8 instructions in the contiguous bytes between dispatch
offsets. It cannot follow a single jump, so it structurally could not see guards in shared
internal helpers (what a Solidity `modifier` compiles to), signature checks, storage-based
permission checks, or whether the sensitive opcode was reachable at all. Its `OPEN` meant "no
pattern in this window" — and the labeler read that as "no access control". It returned
`OPEN_FOUND` for 50/60 Gold-Dev and 140/150 Gold-Test items.

**Replacement built.** A real disassembler + basic-block CFG + bounded symbolic-stack executor
that resolves dynamic jumps (so internal calls *and returns* are followed), tracks value
provenance (`calldata`/`caller`/`origin`/`address`/`sload`/`ecrecover`/`selfbalance`/const), and
applies a **guard-dominance test**: an operation is unauthenticated only if it stays reachable
when traversal is cut at every authorization-tainted branch. Plus a static opcode census used
as a soundness backstop, so an operation the analysis never reached is reported as a coverage
gap instead of silently counted as absent. Two of its own bugs were found by spot-checking and
fixed: compared constants were never captured (0 of 268 caller checks), and bare `ADDRESS()`
was being counted as authorization.

**Result:** 230 items → **32 SAFE / 160 UNSAFE / 38 UNCERTAIN** (was 21/179/30). 63.9% exact
agreement with the previous pass; 83 items changed. **0 of 160** UNSAFE labels rest on weak
support (structurally enforced, tested).

---

## 6. Current headline numbers (Opus 5 labels — PROVISIONAL)

**Gold-Dev** (49 binary, 11 UNCERTAIN excluded = 18.3%):

| model | AUPRC | AUROC | recall | FPR |
|---|---:|---:|---:|---:|
| flat_cnn_16384 | 0.943 | 0.815 | 0.410 | 0.100 |
| flat_cnn_matched_16384 | 0.932 | 0.759 | 0.410 | 0.100 |
| authguard_sequence_dense | 0.920 | 0.726 | 0.410 | 0.100 |
| authguard_reference_v3 | 0.919 | 0.723 | 0.410 | 0.100 |
| source static rule | — | — | 0.410 | precision 0.941 |

**Gold-Test** (128 binary, 22 UNCERTAIN excluded = 14.7%), one shot:

| model | AUPRC [95% CI] | recall | FPR |
|---|---|---:|---:|
| flat_cnn_16384 | 0.926 [0.864, 0.972] | 0.435 | 0.200 |
| authguard_sequence_dense | 0.915 [0.850, 0.965] | 0.426 | 0.200 |
| provisional_final_model | 0.909 [0.833, 0.970] | 0.972 | 0.950 |
| source static rule | — | 0.426 | precision 0.939 |

**Deployment** (`authguard_sequence_dense`, RTX 2080 SUPER + measured CPU): 97,646 params,
397,988-byte checkpoint, 2.83 ms median / 3.44 ms p99 CPU forward, 125.7 items/s. ONNX exports
with numerical parity 4.17e-7 but is *slower* on CPU (4.99 ms) than native PyTorch.

**Legitimate controls**: 0/22 VERIFIED and 0/8 CANDIDATE documented deployments flagged at the
frozen threshold.

### Four findings that matter more than the table

1. **AUROC rose from 0.610 to 0.726–0.815** on Gold-Dev under the corrected labels, and the
   four models no longer collapse onto an identical confusion matrix. The re-labeled targets
   are measurably more separable by bytecode-only models than the previous ones.
2. **The degenerate threshold reproduces** (recall 0.972 at FPR 0.950) under a different label
   source *and* a different selected loss. With ~49 calibration items, a good ranking metric
   does not buy a usable operating point. The frozen Phase 1/2 thresholds transfer fine.
3. **`flat_cnn_16384` leads on AUPRC in both sets** — but all CIs overlap, so the ranking is
   not statistically distinguishable at this sample size, and Phase 2's model choice rested on
   robustness rather than clean AUPRC anyway.
4. **89 of the 160 UNSAFE labels are on items the source rule never flagged.** These labels are
   not a restatement of the rule — consistent with the audit's finding that the negatives are
   rule-silent, not verified benign.

### The single most consequential judgement in the relabeling
`require(msg.sender == 0xHARDCODED)` in an EIP-7702 delegate is **not** protection for the
authorizer: that literal was fixed at delegate-deployment time, so it cannot be the authorizing
EOA. It names a fixed third party with exclusive privileged access to the account's assets —
the structure of a drainer. This is correct for a *delegate* and wrong for an ordinary
contract, and it is why several items the previous pass read as SAFE (`withdrawAnyToken(address)`
and `rescueETH()` gated to fixed addresses, `forward(address,bytes)` behind a
"RestrictedRouter: unauthorized" check) are now UNSAFE. **A reviewer who disagrees with this one
call should overturn a large block of labels at once**, which is why it is stated this
prominently.

---

## 7. Concern-closure status

From `REVIEWER_CONCERN_CLOSURE_MATRIX.md`: **11 RESOLVED, 3 PARTIALLY_RESOLVED, 6
BLOCKED_BY_HUMAN_LABELS** across 20 concerns.

**Resolved:** dataset provenance · duplicate leakage · family leakage · architecture novelty ·
component ablation · token-budget fairness · parameter-count fairness · bootstrap correctness ·
legitimate controls · ML-vs-static positioning · deployment feasibility · human-evidence
infrastructure · Gold-Test independence.

**Partially resolved:** robustness re-run against provisional labels (Phase 2's Flood-200%
still rests on source labels) · temporal generalization (collection genuinely incomplete) ·
reproducibility (`source_rule` evaluation path still not parametrized).

**Blocked on human labels — by design, never closed with provisional labels:** final label
validity · final human-reference performance · calibration conclusions · static-analyzer
comparison conclusions · final model selection · LLM-vs-human agreement.

---

## 8. The one thing that is still unresolved

Everything above is scaffolding around a single unclosed hole: **there is still no independent
ground truth.** The chain is:

> source labels are a Datalog reachability rule with no authorization predicate → the model
> learns to reproduce that rule (v2's own audit says so) → the provisional labels are a language
> model's judgement over automated evidence → **only human review closes it.**

And this pass added a constraint on itself: because the Opus 5 labels were produced *with* the
analyzer's verdict visible, **any static-rule agreement metric computed against them is
descriptive, not an independent evaluation.** That comparison requires the human labels. This
limitation is written into the quality report and asserted by a test so it cannot quietly
disappear from a later draft.

---

## 9. What is needed from people

1. **Complete the human review.** `Pilot_Code_Review.xlsx` (20), `Gold_Dev_Code_Review.xlsx`
   (60), `Gold_Test_Code_Review.xlsx` (150) — now carrying nine added columns (Opus 5 label,
   confidence, rationale; the static-analyzer verdict *plus a plain explanation of what it does
   and does not mean*; a words-first code summary; guard results; project/on-chain evidence;
   unresolved questions). Human columns are blank; reviewers never need to read raw bytecode.
2. **Adjudicate the hardcoded-caller judgement** (§6). It is the highest-leverage single
   decision in the label set.
3. **Decide the temporal scope.** Collection is genuinely incomplete: Ethereum reached ~2.5%
   of the 5-month target window before the jobs stopped; Base stalled on indexed-API
   reliability; BNB/Arbitrum/Optimism/Polygon have completed 1,500-block pilots. Either restart
   the checkpointed jobs or scope the temporal claim down to what exists.
4. **Fix the 2,280/819 vs 2,190/790 discrepancy** in the manuscript abstract (§3.5).

Then one command regenerates everything:
```bash
python3 revision_v3/run_reference_pipeline.py --label-source human_final
```
It currently exits `BLOCKED_NO_HUMAN_LABELS` and writes nothing — verified by a test that runs
it as a subprocess.

---

## 10. Health of the repository

- **Tests:** 171/171 passing (`revision_v3/tests/`), including 55 new label-integrity tests.
  Two of those 55 failed on first run and caught real defects — an UNSAFE label whose evidence
  text was never populated, and a wrong key name for the cascade band. Both fixed.
- **Frozen guard:** `revision_v2/experiments/common/frozen.py verify` → **OK, 144/144
  unchanged**. v2 has never been written to by v3 code.
- **Sampling manifests:** all four MD5-verified unchanged since Phase 2.
- **`human_final_label`:** empty for all 230 items, everywhere, enforced structurally and
  tested.
- **Label-source separation:** four sources (`source_rule`, `llm_provisional`,
  `llm_provisional_opus5`, `human_final`) each in their own results directory, config file, and
  asset directory. No pass can overwrite another's outputs.
- **Git:** 23 changed paths, 12 tracked modifications, **nothing committed**.

---

## 11. Honest read on where the paper stands

**Defensible today:** the evaluation framework (family-disjoint splits, corrected bootstrap,
parameter-matched baselines, donor-isolated robustness, matched-FPR policies); the deployment
measurements; the tool itself; the benchmark with its provenance fully documented *including*
the circularity; and the cascade/triage positioning — AuthGuard as a cheap first stage that
escalates to semantic analysis, not a replacement for it.

**Not defensible until human labels land:** any statement of the form "AuthGuard detects unsafe
delegates with X performance." Under the source labels that reads as rule-mimicry; under either
provisional label set it reads as agreement with a language model.

**The most publishable thing this project currently owns** may not be the detector at all. It
is the pair of methodological findings that a careful pipeline surfaced and a sloppy one would
have buried: that a *competitive AUPRC does not imply a usable operating threshold* when
calibration data is scarce, and that *an authorization check that looks protective in an
ordinary contract can be the exact opposite in a delegation context*. Both are reusable results
about how to evaluate this class of system, and neither depends on the label question being
settled.
