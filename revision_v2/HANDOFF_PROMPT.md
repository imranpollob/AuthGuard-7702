# AuthGuard-7702 Revision v2 — Session Handoff Prompt

Copy everything below the line into a new Claude Code session on the new machine, from the
repository root (the repo must be cloned with the `revision-v2` branch checked out).

---

You are a senior ML research engineer, blockchain-security researcher, and reproducibility
auditor continuing an **already-approved, in-progress** revision program for the AuthGuard-7702
research repository and its IEEE ICTAI manuscript. A previous session completed most of the
work; the machine was shut down mid-run. **Do not re-plan and do not re-litigate approved
decisions — resume execution from the recorded state.**

---

# BIG PICTURE — what this project is and where it must land

## The end goal

Produce an **AI tool that is novel enough and performant enough to be accepted at IEEE ICTAI**
(International Conference on Tools with Artificial Intelligence), backed by evidence that
survives a hostile reviewer. Two things must both be true at submission:

1. **Novelty** — there is a defensible AI/technical contribution, not just "we ran XGBoost on a
   new dataset."
2. **Performance + validity** — the numbers are real, the protocol is defensible, and every
   claim is bounded by the evidence that supports it.

ICTAI is a *tools* venue: a well-engineered, rigorously evaluated tool with a clear technical
insight can be accepted, but a standard classifier on a single-source dataset will not be.

## The research problem

EIP-7702 lets an externally owned account (EOA) delegate execution to contract code. Authorizing
a **malicious delegate** can drain the account. The defensive decision happens **before
authorization**, when the delegate may have no transaction history, no reputation, and no
verified source — but its **runtime bytecode is available**. So: *can bytecode-only screening
give a useful pre-authorization risk signal?*

AuthGuard-7702 = decompiler-free bytecode risk scoring (773-dim features → XGBoost), positioned
as a **fast complementary screening stage** ahead of heavyweight declarative analyzers
(Gigahorse/Datalog), never as a replacement for them.

## The evidence base (all frozen)

- Task-aligned corpus: **727 artifact-derived positives** (USENIX EIP-7702 artifact) vs
  **1,553 rule-silent weak negatives**; plus 797 `benign_general` and 5 `benign_AA` controls.
- Frozen bytecode-similarity **families** (MinHash @0.85) and 5 stored outer folds.
- Protocol groups: **G-DET** (detection), **G-MUT** (mutation tiers M0–M3), **G-VOL** (dead-code
  flooding sweep), **G-ADV** (source-balanced augmentation).
- Headline: family-grouped **AUPRC 0.881** vs **0.975** under a random split (i.e. random
  evaluation is materially optimistic — a core methodological finding of the paper).

## The honest problem this revision exists to solve

A hostile-reviewer audit (`reports/ictai_reviewer_assessment.md`, pre-existing) scored
**AI novelty 2/5** and flagged near-fatal concerns. Ten major reviewer issues were mapped in
`revision_v2/planning/reviewer_issue_map.md`:

1. source-derived labels + insufficient independent validation (only **1** truly novel confirmed
   positive → INSUFFICIENT DATA)
2. conflicting identical-bytecode labels (23 exact-hash groups)
3. G-DET threshold-selection ambiguity → **confirmed valid**: v1 selected thresholds on
   **in-sample fitting predictions**
4. limited semantic validity of transformations (checker was syntactic only)
5. insufficient baselines and feature ablations
6. family-threshold and family-weighting sensitivity
7. possible flooding **donor leakage** → **confirmed valid**: one fixed donor fed both training
   and test variants
8. unsupported deployment/robustness claims ("production-ready", "seamless", "proves")
9. missing secondary-control results
10. incomplete reproducibility

**The strategic tension you are resolving:** the evaluation framework is strong, but the *AI
novelty* is thin. Phase 4 was designed as the decision-gated attempt to create real novelty
(dual-view representation → Gate A; selective escalation → Gate B). **Gate A has now FAILED**
(see the critical finding below), which makes the novelty question the single most important
open item in the project. Do not manufacture novelty to fill the gap — establish what the
evidence actually supports.

## The approved contribution structure (evidence-decided, in priority order)

1. **Task-aligned, dependence-aware EIP-7702 evaluation** — task alignment, frozen families,
   corrected threshold-transfer protocol, donor isolation. *(Supported today.)*
2. **Lightweight bytecode classification vs the strongest evaluated bytecode baselines.**
   *(Supported today: AG − opcode_xgb Δ0.091, CI [0.042, 0.147].)*
3. **Either** Gate A dual-view robustness **or** Gate B selective escalation — *whichever the
   evidence supports.* Gate A has failed. If Gate B also fails, **do not fabricate a novelty
   claim**: center the paper on (1) + (2) + the corrected robustness analysis + the
   representation finding under investigation, and report the failed experiments honestly in
   the internal reports.

## The 6-phase program (as approved; use for orientation)

| Phase | Scope | Status now |
|---|---|---|
| **0** | Workspace, frozen-artifact guard, protocols, shared harness | ✅ complete |
| **1** | **Claim & protocol integrity**: (A) claim corrections, (B) G-DET/G-MUT/G-VOL threshold correction + FPR, (C) flooding donor audit + isolation + regeneration, (D) family-clustered uncertainty | A/B/D ✅; **C partially — G-ADV v2 must be rerun** |
| **2** | **Minimum construct-validity package**: (A) conflicting-bytecode analysis, (B) manual label-audit support (no fabricated labels), (C) small execution-validation framework, (D) secondary controls | ✅ complete |
| **3** | **Strong baselines, ablations, sensitivity**: (A) stronger baselines, (B) feature ablations, (C) family sensitivity, (D) weighting sensitivity | C/D ✅; **A/B must be rerun** |
| **4** | **Decision-gated technical novelty** (time-boxed): Gate A terminal-aware dual-view; Gate B selective escalation | **Gate A ✅ FAILED**; **Gate B not started** |
| **5** | **Reference-analyzer decision fork** (Gigahorse/Datalog reproduction vs blocker report) | ✅ **Option B (blocked)** |
| **6** | **Reproducibility, operational analysis, manuscript integration**: (A) anonymous artifact, (B) operational analysis, (C) final manuscript framing | B ✅; **A/C pending** |

## Boundaries the manuscript must always retain

Artifact-derived labels; rule-silent weak negatives; limited independent validation;
context-dependent identical bytecode; checker-constrained transformations; unevaluated wallet
integration; no production-readiness evidence; **no speed/superiority claim vs the full
Gigahorse/Datalog pipeline** (it was never executed).

---

## Ground rules (unchanged, still binding)

1. **Frozen evidence is immutable.** Never modify: `capability_dataset.csv`,
   `family_assignment_frozen.csv`, `pipeline/**`, `results/**`, `reports/**`,
   `paper_build/**` (including `data_hygiene/`, `statistics/`, `runtime/`, `overleaf/`,
   `tables/`, `figures/`, `sections/`), `advtrain_results.json`, `paired_results.csv`.
   All new work goes under `revision_v2/` on the `revision-v2` branch.
2. **Run the frozen guard before and after every phase:**
   `python3 revision_v2/experiments/common/frozen.py verify` → must print
   `OK: 144 frozen files verified unchanged`. Any modification is a **HARD STOP**.
3. **Protocols are frozen and hashed** in `revision_v2/protocols/` (`protocols.sha256`).
   Gate A/B success criteria were fixed *before* results were seen — honor them exactly. Do not
   loosen a criterion to make a method pass.
4. **Report honestly.** Lower corrected metrics, a stronger baseline beating AuthGuard, failed
   gates, shrunken augmentation gains — all are acceptable outcomes to record, not to fix away.
   Do not delete failed results.
5. **No fabricated human judgments.** The label-audit package is built; human labels are pending.
6. Machine-readable outputs (JSON/CSV) + `manifest.json` (input/output SHA-256, versions, seeds)
   for every experiment. Every manuscript number must trace to a machine-readable source.

## Orientation — read these first

- `revision_v2/planning/` — the six approved planning documents (repository audit, protocol
  reconstruction, reviewer issue map, experiment matrix, risk register, master execution plan).
- `revision_v2/protocols/` — frozen threshold v2, donor isolation v1.1, Gate A/B criteria,
  uncertainty protocol.
- `revision_v2/reports/phase_0_report.md`, `phase_2_report.md` — completed phase reports.
- `revision_v2/audits/claim_corrections.md` — the approved manuscript claim-correction list (C1–C8).
- `revision_v2/experiments/common/harness.py` — the shared harness (corrected threshold protocol,
  per-row score persistence, FPR metrics, manifest writer). Validated to reproduce frozen v1
  per-fold AUPRCs exactly (`revision_v2/audits/harness_validation.json`).

Git state: branch `revision-v2`, last commit `3a46bf3` ("Phases 1-5 (partial)"). All completed
work is committed.

## What is DONE (do not redo — results are on disk)

| Phase | Status | Key results |
|---|---|---|
| 0 — workspace/guard/harness | ✅ | 144-file frozen ledger; harness reproduces v1 AUPRCs exactly (max diff 0.0) |
| 1A — claim audit | ✅ | `revision_v2/audits/claim_corrections.md` (C1–C8 with replacement wording) |
| 1B — G-DET v2 | ✅ | `results/gdet_v2/` — AuthGuard AUPRC **0.881±0.028** (unchanged, threshold-free), F1 0.782, P 0.794, R 0.808, **FPR 0.101**; random-split 0.975 (gap 0.094). v1→v2: corrected OOF thresholds are *lower* than v1 in-sample → recall ↑ (0.576→0.808), precision ↓ (0.869→0.794). **v1 was conservative, NOT inflated.** (`v1_v2_reconciliation.json`) |
| 1B — G-MUT/G-VOL v2 | ✅ | `results/gmut_v2/`, `results/gvol_v2/` — donor-isolated (`iso`) + `v1donor` arms. AuthGuard G-MUT recall M0 0.808→M3 0.770 (FPR ~0.10–0.13). G-VOL iso: AuthGuard 0.816→**0.379** at +200%; opcode_xgb 0.809→0.423. **The v1 single-donor design was confounded in both directions** (v1donor arm: opcode_xgb *rises* to 0.826 under flooding — donor-signature artifact). Preservation 2280/2280 at M1/M2/M3. |
| 1D — uncertainty | ✅ | `results/uncertainty/gdet_bootstrap.json` — AuthGuard AUPRC 0.867, CI [0.804, 0.922]; **AG − opcode_xgb Δ0.091, CI [0.042, 0.147] (excludes 0)**; **random − family Δ0.107, CI [0.051, 0.171] (excludes 0)** |
| 2A — conflicts | ✅ | `results/conflicts/` — 23 groups categorized: 11 context-dependent, 9 likely label-inconsistency, 2 external-dependency, 1 unresolved. Known-conflict escalation = 0% escalation on retained corpus (all quarantined), 100% coverage of known conflicts. Pre→post quarantine: 0.856→0.881 (quarantine did not inflate). |
| 2B — adjudication package | ✅ | `revision_v2/artifact/label_audit/` — 170 items, 7 strata, 3 blinded forms, guidelines, `agreement.py` (returns `pending_human_labels`) |
| 2C — execution validation | ✅ | `results/exec_validation/` — anvil `setCode` + `debug_traceCall`, 10 malicious delegates. **M1 10/10 fully preserved; F200 10/10 fully preserved (padding proven non-executing); M2 10/10 control-flow preserved; M3 diverges only at renamed sensitive selectors (intended reroute).** |
| 2D — secondary controls | ✅ | `results/secondary_controls/` — AuthGuard benign_general FPR **0.119** (95/797, alerts/1000=119, p95 0.097) at the aggressive max-F1 threshold; opcode_rf 0.034; opcode_xgb 0.221. benign_AA (n=5) all ≈0.00, unflagged (case observations only). |
| 3C — family sensitivity | ✅ | `results/family_sensitivity/` — AG AUPRC **0.814 / 0.878 / 0.913** at thresholds 0.75/0.85/0.90; gaps 0.161/0.098/0.062; AG > opcode_xgb at every threshold (conclusions stable, not knife-edge). Recomputed-after-alignment families: **ARI 0.998** vs frozen, AUPRC 0.874. |
| 3D — weighting | ✅ | `results/weighting/` — AuthGuard advantage stable: obs 0.867 / inverse-family 0.838 / one-vote-per-bytecode 0.844 (vs opcode_xgb 0.776/0.753/0.744); macro-recall 0.855, macro-FPR 0.114 |
| 4 Gate A | ✅ (verdict **FAIL**) | `results/gateA/gateA_results.json` + `gateA_verdict.json` — see the critical finding below |
| 5 — reference analyzer | ✅ (**Option B, blocked**) | `results/gigahorse/feasibility.md` — no Docker/Soufflé; artifact ships client rules but NOT the Gigahorse `clientlib/*.dl` the `analyze.dl` `#include`s. Limited agreement from shipped facts only (727/727 malicious have rule facts = circularity, not validation). No speed claim anywhere. |
| 6B — operational | ✅ | `results/operational/operational.json` — PR/ROC curves, threshold table, alerts/1000, hypothetical prevalence 0.1/1/5%, calibration: raw ECE 0.134 → **Platt 0.098** → isotonic 0.120 (raw scores are ranking scores, not calibrated probabilities) |

## 🔴 CRITICAL FINDING TO RESOLVE FIRST — Gate A failed because the *trivial* baseline won

Gate A (conservative terminal-aware dual-view) verdict = **FAIL**, failing only criterion 5
("must beat the trivial first-STOP heuristic"). The numbers:

| representation | clean family AUPRC | F200 recall | M3+F200 recall | benign_general FPR |
|---|---|---|---|---|
| full-view (AuthGuard, 773) | 0.881 | 0.351 | 0.378 | 0.078 |
| dual-view (1812) | 0.946 | 0.747 | 0.768 | 0.024 |
| **first-STOP heuristic (773)** | **0.969** | **0.972** | **0.972** | — |

The trivial "ignore everything after the first STOP" baseline **beats AuthGuard's full-view
representation on clean data (0.969 vs 0.881) and is nearly immune to flooding** (0.972 recall
at +200%). Flooding immunity is expected by construction (padding is appended after a STOP, so
truncation deletes it). The **clean-data superiority is the surprise and may be an artifact.**

Diagnostic already run: the first-STOP region *length* is itself strongly class-dependent —
malicious median **188 B** (range 32–1154), benign_cleared median **84 B** (range 2–16382);
2.8% of benign_cleared have a near-empty (<20 B) region vs 0% of malicious.

**Your first task is to determine whether the first-STOP result is a genuine representational
finding or a corpus/length shortcut.** Required work:
1. Run the first-STOP representation **with the `no_length` and `no_length_metadata` ablations**
   (drop `code_bytes`, `n_ops`, and metadata-ish features). If AUPRC collapses toward ~0.88 or
   below, the 0.969 is a length shortcut on a homogeneous artifact-derived positive corpus →
   report as a **dataset-artifact finding** (strengthens the paper's honesty section, and
   directly addresses reviewer issue 5's shortcut question).
2. Check the degenerate cases: contracts whose first-STOP region is near-empty or the whole
   body; confirm featurization of tiny regions isn't manufacturing separability.
3. Test whether first-STOP survives the **family-sensitivity thresholds** and the
   **paired family-clustered bootstrap** vs AuthGuard (does its advantage's CI exclude 0?).
4. Whatever the outcome, record it honestly. If first-STOP genuinely dominates, the manuscript's
   representation design and contribution framing must change (a trivial terminal truncation
   would then be the strongest bytecode representation tested) — that is a legitimate and
   publishable result. Gate A's dual-view stays out of the paper either way (it failed).

### Why this decides the ICTAI novelty question

This is not a side quest — it determines what the paper *is*. Three branches, all acceptable:

- **(a) Shortcut confirmed** (first-STOP collapses without length/metadata features): the paper
  gains a genuine **dataset-artifact / shortcut-learning finding** — "a trivial truncation
  appears to beat a 773-feature model, but only by exploiting a length regularity of an
  artifact-derived positive corpus." That is a real methodological contribution for a
  tools/evaluation paper and directly answers reviewer issue 5. Contribution structure = (1) +
  (2) + shortcut finding.
- **(b) Genuine finding** (first-STOP survives ablation + bootstrap): terminal-region truncation
  is the strongest bytecode representation tested *and* is inherently flooding-robust. Then the
  **representation insight becomes the technical contribution** (an EIP-7702-relevant,
  empirically grounded one), replacing the failed dual-view. AuthGuard's full-view design must
  be reframed accordingly — do not hide that a simpler method won.
- **(c) Mixed** (partial survival): report the decomposition (how much is length, how much is
  structure) and let Gate B decide whether escalation adds a second contribution.

In every branch: **do not weaken Gate A's frozen criteria to resurrect the dual-view**, and do
not claim novelty the ablations do not support. A rigorous negative result plus a corrected,
donor-isolated, threshold-valid evaluation framework is a defensible ICTAI submission; an
overclaimed novelty is not.

## What is INCOMPLETE (resume here)

1. **G-ADV v2 — died at fold 1 of 5.** Script: `revision_v2/experiments/gadv_v2/run_gadv_v2.py`.
   Partial log (`revision_v2/results/gadv_v2_run.log`) showed, donor-isolated:
   `fold 1: AG-M0/aug F200 recall 0.329→0.390; compound M3+F200 0.260→0.377`.
   **Preliminary signal: under donor isolation the augmentation gain is far smaller than the
   v1 donor-confounded 0.484→0.727.** Partial outputs were removed; **rerun from scratch**.
   Must produce: `val_threshold` (primary) and `inner_oof` (sensitivity) threshold arms; the
   compound **M3+F200** condition; donor provenance ledger; leakage assertions.
2. **Phase 3A/3B baselines + ablations — died mid-TF-IDF.** Script:
   `revision_v2/experiments/baselines/run_baselines_ablations.py`. **Rerun from scratch.**
   Covers: hash-XGB, TF-IDF+LR, TF-IDF+LinearSVC (calibrated), 5 seeds, plus the 10-way
   ablation matrix (struct-only, hist-only, ngram-only, hist+struct, hist+ngram, full-773,
   no-selectors, no-length, no-metadata, no-length-metadata). **Add first-STOP variants per the
   critical finding above.**
3. **Phase 4 Gate B — not started.** Script exists and is import-clean:
   `revision_v2/experiments/gateB/run_gateB.py` (signals: conflict history, trailing ratio,
   margin, cross-seed disagreement, kNN outlier; target escalation ≤15%; compares against a
   low-confidence-abstention baseline; criteria in `protocols/gateB_success_criteria.md`).
   Run it, then write the verdict.
4. **Phase 6A artifact manifest** — script ready:
   `revision_v2/experiments/artifact/build_artifact_manifest.py` (run after all results exist).
5. **Phase 6C manuscript integration** — table generator ready:
   `revision_v2/experiments/manuscript/generate_tables.py`. Apply `claim_corrections.md` C1–C8.
   **Do not touch `paper_build/overleaf/main.tex`** — write the revised manuscript under
   `revision_v2/manuscript/`.
6. **All phase reports**: `phase_1_report.md`, `phase_3_report.md`, `phase_4_report.md`,
   `phase_5_report.md`, `phase_6_report.md` + per-phase `_changed_files.txt`, `_commands.sh`,
   `_results_manifest.csv`, `_failures.md`. (Phase 0 and 2 reports exist.)
7. **Final deliverables**: `final_revision_report.md`, `final_reviewer_issue_resolution.md`
   (reassess all 10 concerns), `final_claim_to_evidence.md`, `final_number_audit.md`,
   `final_reproducibility_audit.md`, `final_anonymity_audit.md`,
   `final_submission_readiness.md` + a hostile ICTAI reviewer re-review with a readiness label.

## Performance guidance for the new machine (important — read before optimizing)

**A GPU will help far less than you might expect.** The measured bottlenecks on the old machine
were: `gdet_v2` 4944 s, `gmutvol_v2` 2308 s, `family_sensitivity` 802 s, `gateA` 523 s,
`gadv_v2` ~364 s/fold. The dominant costs are **single-threaded Python bytecode featurization**
(`pipeline/ag_features.py` disassembly + n-gram hashing), **scikit-learn** RF/LogReg/TF-IDF, and
many small **XGBoost** fits (the corrected protocol refits 5× inner-OOF + 1× final, per fold,
per seed). None of the featurization or sklearn work is GPU-accelerable.

What actually helps, in order:
1. **More CPU cores + RAM.** Raise `n_jobs` in `revision_v2/experiments/common/harness.py`
   (`XGB_HP["n_jobs"]=4`) and in RF constructors to the core count. Run the independent
   experiment scripts **sequentially** on a many-core box rather than 4-way concurrently — the
   old run had 4 jobs contending at ~90–200% CPU each, which is what made everything crawl.
2. **Parallelize featurization** across processes if you touch it — but note
   `ag_features.featurize` is frozen-adjacent (imported read-only). Do not modify frozen files;
   wrap/parallelize at the call site inside `revision_v2/` only.
3. **XGBoost GPU (optional):** you may set `device="cuda"`/`tree_method="hist"` in
   `harness.XGB_HP` **only if** you first re-run
   `python3 revision_v2/experiments/common/validate_harness.py` and it still reproduces the
   frozen v1 per-fold AUPRCs within 1e-6. GPU histogram construction can change floating-point
   results; **if validation fails, revert to CPU** — protocol fidelity outweighs speed.
   Record any such change in the phase report and manifest.
4. Seeds: the approved plan requires ≥5 seeds for stochastic learners. Keep them.

## Recommended execution order

1. Frozen-guard verify → confirm 144 OK.
2. Re-run `validate_harness.py` on the new machine (and after any XGB device change).
3. **G-ADV v2** (longest pole; donor-isolated + compound M3+F200).
4. **Baselines + ablations**, including the first-STOP shortcut investigation (§ critical finding).
5. **Gate B** + verdict.
6. Phase reports 1, 3, 4, 5; artifact manifest; operational refresh if inputs changed.
7. Manuscript integration (`revision_v2/manuscript/`) + table regeneration.
8. Final audits + hostile review + readiness label.

## Final response format (when all feasible work is done)

Report: phases completed; experiments completed; experiments failed; changed files; generated
artifacts; corrected primary results; strongest baseline; ablation conclusions;
family-sensitivity conclusions; donor-isolation conclusions; compound-transformation
conclusions; Gate A verdict; Gate B verdict; reference-analyzer verdict; construct-validity
findings; reproducibility status; remaining human tasks; residual reviewer concerns;
recommended paper contribution structure; and one readiness label from:
`READY FOR MANUSCRIPT REVIEW` / `NEEDS HUMAN ADJUDICATION BEFORE MANUSCRIPT FREEZE` /
`NEEDS MAJOR SCIENTIFIC REVISION` / `NOT SUBMISSION-READY`.

Note: given the Gate A finding, the contribution structure most likely supported by current
evidence is (1) task-aligned, dependence-aware EIP-7702 evaluation + corrected threshold and
donor-isolation protocols, and (2) an empirical representation finding about terminal-region
truncation and flooding robustness — **pending** the shortcut investigation. Do not assert a
novelty claim that the evidence does not support.
