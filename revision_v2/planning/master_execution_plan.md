# Master Execution Plan — AuthGuard-7702 Revision v2

Dependency-aware plan for Phases 0–6. No step below has been executed; this document is the
approval gate. Effort estimates assume one engineer on the existing macOS/CPU environment.

## Global invariants (apply to every phase)

- Work happens on a dedicated branch `revision-v2`; all new outputs live under
  `revision_v2/{protocols,experiments,results,audits,reports,artifact,manuscript}`.
- Frozen v1 artifacts are never overwritten: `capability_dataset.csv`,
  `family_assignment_frozen.csv`, `results/*`, `advtrain_results.json`, `paired_results.csv`,
  `reports/*` (existing), everything under `paper_build/data_hygiene/` and
  `paper_build/statistics/`. A hash-guard script verifies the SHA-256 ledger
  (`task_aligned_result_provenance.md` + a new ledger for the remaining frozen files) before
  and after every experiment run.
- Every experiment writes machine-readable JSON/CSV + a `manifest.json` (command, seeds,
  config, package versions, input hashes, output hashes, wall time).
- Every phase ends with the five mandated report files under `revision_v2/reports/`
  (`phase_<N>_report.md`, `_changed_files.txt`, `_commands.sh`, `_results_manifest.csv`,
  `_failures.md`). Failed experiments are stored, never deleted.
- One threshold protocol for v2 (inner family-grouped OOF within outer-train), used uniformly;
  deviations (e.g., G-ADV val-fold arm for continuity) are explicitly labeled.

---

## Phase 0 — Workspace, guards, and shared harness (prerequisite for everything)

**Tasks**
1. Create branch `revision-v2`; add `revision_v2/` tree.
2. Freeze-hash ledger: script `revision_v2/experiments/common/verify_frozen.py` covering all
   frozen inputs/outputs (extends the existing provenance ledger to `results/*`,
   `advtrain_results.json`, `paired_results.csv`, `family_assignment_frozen.csv`,
   `capability_dataset.csv`).
3. Environment capture: `requirements.txt` + `pip freeze` snapshot + platform record.
4. Shared v2 harness `revision_v2/experiments/common/harness.py`: loads task-aligned v1 +
   stored folds, features via frozen `ag_features`, **persists per-row test scores for every
   method** (schema mirrors `task_aligned_paired_results.csv`), computes metrics incl. FPR,
   implements inner family-grouped OOF threshold selection (GroupKFold(4) over outer-train
   families → OOF scores → max-F1 → refit on full outer-train → freeze → single test pass).
5. Protocol documents frozen BEFORE any v2 result is read:
   `revision_v2/protocols/{threshold_protocol_v2.md, donor_isolation_protocol.md,
   gateA_success_criteria.md, gateB_success_criteria.md}` — each hashed (`.sha256`).

**New files:** as above. **Code likely touched:** none of the frozen pipeline (imported
read-only, as `task_aligned_rerun.py` already does via importlib).
**Tests:** harness unit checks — fold replay identity vs stored columns; feature-matrix hash
equality with `task_aligned_features_{dense,ngram}.npz`; threshold routine on synthetic data;
frozen-hash guard passes.
**Effort:** ~1.5 days. **Prerequisites:** approval of this plan.
**Go/no-go:** harness reproduces v1 AUPRCs exactly (same in-sample-threshold mode as a
back-compat check) before the corrected mode is trusted.
**Rollback:** delete branch; nothing frozen is touched by construction.
**Claims enabled:** none (infrastructure).

## Phase 1 — Claim and protocol integrity

**Order within phase:** 1A (audit, no deps) ∥ 1B → 1D; 1C after 1B harness exists.

### 1A Claim corrections (audit only now)
Produce `revision_v2/audits/claim_corrections.md`: every unsupported sentence (already
located: main.tex lines 21, 47, 400, 432; abstract "significantly recovers"; plus a sweep of
`sections/*.tex`) with approved replacement wording per the supported-positioning list.
Manuscript is NOT edited until Phase 6C. Effort: 0.5 day.

### 1B G-DET/G-MUT/G-VOL threshold correction (experiments P1B-*)
- Rerun G-DET (primary + secondary + random diagnostic), G-MUT, G-VOL under the corrected
  protocol; add FPR; persist per-row scores; 5 model seeds for stochastic models.
- Produce v1→v2 reconciliation table (thresholded metrics only; assert AUPRC/AUROC unchanged
  up to seed variance — they use the same fits).
- **Code:** new runners under `revision_v2/experiments/gdet_v2/`; no frozen file edited.
- **Tests:** thresholds differ from v1 (sanity); no test-row participates in threshold
  selection (assertion on index sets); family disjointness in inner folds.
- **Outputs:** `revision_v2/results/{gdet_v2,gmut_v2,gvol_v2}/*.json` + per-row CSVs.
- **Effort:** ~2 days incl. reconciliation. **Prereq:** Phase 0.
- **Go/no-go:** if v2 thresholded metrics deviate wildly (R1), pause and review before
  Phase 3 consumes the harness.
- **Claims enabled:** "thresholds selected on family-disjoint out-of-fold predictions and
  frozen before testing"; FPR-augmented G-DET table.

### 1C Flooding donor audit and G-ADV regeneration (P1C-*)
- Implement partition-isolated multi-donor pools + provenance ledger
  (`donor_ledger.csv`: recipient source/family/partition, donor source/family/partition,
  copied byte-range hash, transformation seed, condition) + two-sided assertions.
- Regenerate G-ADV (3 model seeds), including the **compound M3+F200** test condition;
  rerun the paired family-clustered bootstrap on v2 paired results.
- Donor-pool design decision (flagged for approval): primary pool = benign_general families
  partitioned by fold role and excluded from the evaluated population of that fold;
  check arm = benign_cleared-sourced donors.
- **Code:** `revision_v2/experiments/donor_pools/`, `gadv_v2/`; wraps
  `mut.mut_deadcode_append` with an injected donor source (frozen module untouched).
- **Tests:** donor/recipient partition assertions; ledger completeness (every flooded variant
  has a row); train/test RNG-domain separation preserved.
- **Outputs:** `revision_v2/results/gadv_v2/` (+ `compound/`), updated bootstrap JSON/MD.
- **Effort:** ~3 days. **Prereq:** Phase 0 (+1B harness for the unified-threshold arm).
- **Go/no-go (R2):** donor-isolated Δrecall(F200) CI excludes 0 → augmentation claim kept;
  else RQ4 is rewritten and v1 gain documented as donor-confounded in the internal report.
- **Claims enabled:** donor-isolated augmentation result; resolution of the compound
  M3+F200 open condition (either direction).

### 1D Primary uncertainty (P1D-BOOT-GDET)
Family-clustered bootstrap (10k, seeded) on pooled v2 per-row scores: AuthGuard AUPRC CI;
paired ΔAUPRC vs strongest bytecode baseline; random-vs-family gap CI. Preserve all rows of
sampled families (method identical to `family_clustered_bootstrap.py`).
**Effort:** 0.5 day. **Prereq:** 1B. **Claims enabled:** CI-backed headline and gap claims.

**Phase 1 exit criteria:** reports written; reconciliation tables complete; decision on R1/R2
recorded. **Rollback:** v2 results are additive; discard directory if protocol found faulty.

## Phase 2 — Minimum construct-validity package

Parallelizable after Phase 1B; 2C independent.

- **2A Conflict analysis (P2A-CONFLICT, P2A-ABSTAIN):** per-group dossiers for the 23 hashes
  (optionally enriched by read-only RPC/explorer), 5-way categorization, machine-readable
  report + summary table; before-quarantine sensitivity = frozen original-cohort results
  (already reconciled in `original_vs_task_aligned.md`) re-presented, after-quarantine =
  primary; abstention/escalation rule evaluated with frozen v2 thresholds. Quarantined rows
  are NOT restored. Effort ~2 days.
- **2B Manual label-audit support (P2B-AUDIT-PKG):** stratified seeded samples (random
  positives, random weak negatives, high-scoring FPs, low-scoring FNs from v2 per-row scores,
  conflict examples), anonymized review forms, evidence packets, guidelines, assignment
  files, kappa scripts. **No claim of performed adjudication.** Effort ~1.5 days.
- **2C Execution-validation framework (P2C-EXEC-VAL, gated):** 0.5-day feasibility spike
  (anvil/foundry fork replay on 2 contracts with known entry points from the USENIX
  artifact); if green, extend to 5–10 contracts comparing original vs transformed on
  execution success, external calls/targets, storage writes, transfers, return values,
  traces. Claims limited to tested executions. If blocked → minimum-implementation report.
  Effort 2–4 days, hard-capped.
- **2D Secondary controls (P2D-*):** benign_general 797 at frozen v2 thresholds (FPR, score
  distribution, median, p95, alerts/1,000, top cases); benign_AA 5 as case observations.
  Effort 0.5 day.

**Exit criteria:** conflict report + audit package delivered; 2C go/no-go decision recorded.
**Claims enabled:** characterized label conflicts; secondary-control FPR; (if 2C passes)
execution-validated transformation claims on N contracts.

## Phase 3 — Baselines, ablations, family and weighting sensitivity

All on the Phase 0/1B harness with identical stored folds and the corrected threshold
protocol; 5 seeds for stochastic models; paired family-clustered CIs vs AuthGuard.

- **3A Baselines (P3A-*):** TF-IDF n-gram LR; TF-IDF linear SVM; hashed-4gram XGB; re-seeded
  existing RF/XGB/selector/rule/hash baselines. Inner-CV hyperparameter selection only
  (never on test). No under-tuned deep model. Effort ~2 days.
- **3B Ablations (P3B-ABL-*):** struct-only; hist-only; ngram-only; hist+struct; hist+ngram;
  full 773; selector-free; length/metadata-free — attributes gains to structural
  interactions vs n-grams vs selectors vs length/compiler shortcuts. Effort ~1.5 days.
- **3C Family sensitivity (P3C-*):** grouping by frozen `family_id_075`/`family_id_090`
  columns (no reclustering needed); diagnostics (families, singletons, largest, size
  distribution, per-fold class distribution, cross-class counts, within-family similarity,
  chaining/transitive components); recomputed-families-after-alignment arm as a labeled
  sensitivity analysis (new file; frozen families remain primary). Effort ~2 days.
- **3D Weighting sensitivity (P3D-WEIGHT):** observation-weighted, inverse-family-size,
  one-vote-per-exact-bytecode, family-macro recall/FPR, family-clustered pooled metrics;
  pooled weighted AUPRC or family-bootstrap only (never averaged per-family AUPRC).
  Effort ~1 day.

**Exit criteria / gates:** R3 decision (does any baseline reach AuthGuard?) and R4 review
recorded before manuscript work. **Claims enabled:** "outperforms evaluated bytecode
baselines" (or its honest replacement); shortcut-controlled feature story; sensitivity
robustness statements.

## Phase 4 — Decision-gated technical novelty (time-boxed)

Success criteria for both gates are frozen in Phase 0 protocol docs before any result is read.

- **Gate A — Terminal-aware dual-view (P4A-FIRSTSTOP-HEUR then P4A-DUALVIEW):** first run the
  trivial first-STOP truncation heuristic (the bar). Then dual-view features (full 773 +
  conservative terminal-aware restricted view + trailing-byte volume + post-terminal ratio +
  view diffs + score disagreement). Evaluate on clean G-DET, G-MUT, G-VOL, pure F200,
  compound M3+F200, G-ADV, benign_general. Success: meaningful flooding improvement; clean
  AUPRC degradation ≤ ~0.01–0.02; no material benign FPR increase; fold consistency; beats
  the first-STOP heuristic. Terminology: "conservative terminal-aware dual-view
  representation"; no reachability/CFG-recovery claims. Time-box: 4 working days.
- **Gate B — Selective escalation (P4B-ESCALATE):** signals = conflict-hash history,
  trailing-byte ratio, view disagreement (if A ran), low margin, family/feature outlier
  score, transformation indicators; cutoffs frozen on train/val. Report auto-coverage,
  escalation %, non-escalated recall/FPR, error concentration, escalations/1,000 across
  clean, G-VOL, compound. Time-box: 3 working days.
- **Decision logic:** A passes → primary technical contribution. A fails but B concentrates
  errors strongly → B is secondary contribution. Both fail → contribution = task-alignment +
  evaluation framework; failures reported in internal phase report only.

**Prereq:** Phases 1B/1C harnesses. **Rollback:** results are additive; gates simply close.

## Phase 5 — Reference-analyzer decision fork (time-boxed 1–2 working days)

- **P5-GIGA-FEAS:** attempt Gigahorse+Soufflé via upstream Docker; wire USENIX client files.
  Log every step/blocker. HARD STOP at time-box.
- **Option A (feasible):** P5-GIGA-SUBSET on ~50–100 contracts: coverage, failures, agreement
  with AuthGuard-v2, disagreement categories, preprocessing/analysis time, hardware, input
  requirements. No universal speedup claim from a subset.
- **Option B (blocked):** feasibility report (blockers, attempted steps, dependency failures,
  remaining-work estimate) + manuscript recommendation. NOTE: the current manuscript already
  makes no speed claim (main.tex:75), so Option B requires wording review, not removal of a
  measured comparison. The artifact's shipped intermediate outputs (`detect_result.jsonl`)
  permit a limited label-agreement analysis without running the toolchain — include either way.
- This phase must not block Phases 3/4/6; it can run in parallel after Phase 1.

## Phase 6 — Reproducibility, operational analysis, manuscript integration

- **6A Artifact (P6A-ARTIFACT):** package per the brief's inventory (corpus if licensing
  permits, else deterministic reconstruction instructions + hashes); include donor
  provenance, sampling files, all v2 configs/scripts; verify by fresh-environment
  reproduction of headline tables. Effort ~2–3 days. Human input: licensing decision (R10).
- **6B Operational analysis (P6B-OPER):** PR and recall-FPR curves with family-bootstrap
  bands; workload at selected thresholds; alerts/1,000; prevalence scenarios 0.1%/1%/5%
  labeled hypothetical; no probability-of-maliciousness language without calibration.
  Effort ~0.5–1 day.
- **6C Manuscript integration (P6C-MANUSCRIPT):** apply the Phase 1A claim-correction list;
  regenerate every table from machine-readable v2 sources via new generator scripts
  (eliminates hand-typed numbers, R11); contribution structure per Phase 4 gates:
  (1) task-aligned dependence-aware EIP-7702 evaluation; (2) lightweight bytecode
  classification vs evaluated baselines (subject to R3); (3) Gate A dual-view OR Gate B
  escalation, whichever passed; explicit boundary statements retained (artifact-derived
  labels, weak negatives, limited independent validation, context-dependent bytecode,
  checker-constrained transformations, unevaluated wallet integration, no
  production-readiness evidence). Effort ~2 days. **Manuscript edits happen only here.**

**Exit criteria:** number audit + claim audit pass; artifact reproduces tables; final report.

---

## Recommended execution order and critical path

```
Phase 0 ─► 1A (parallel)
       └► 1B ─► 1D ─► 3A/3B/3C/3D ─► 4A ─► 4B ─┐
       └► 1C (after 0; unified-threshold arm after 1B) ┤
       └► 2A/2B/2D (after 1B), 2C spike (anytime)      ├─► 6B ─► 6C ─► 6A
       └► 5 (parallel, time-boxed, after 1B)  ─────────┘
```
Critical path: 0 → 1B → 1C → 3 → 4 → 6C. Phases 2C and 5 are gated side-tracks that must not
delay the path.

## Estimated total effort

| block | estimate |
|---|---|
| Phase 0 | 1.5 days |
| Phase 1 | 6 days |
| Phase 2 | 4–6.5 days (2C gated) |
| Phase 3 | 6.5 days |
| Phase 4 | ≤7 days (time-boxed) |
| Phase 5 | ≤2 days + 1 day if Option A |
| Phase 6 | 5–6 days |
| **Total** | **~30–36 working days**, compressible to ~4 calendar weeks with parallelization; minimum defensible submission (Phases 0–3 + 6) ≈ 19–21 days |

## Human-dependent tasks (cannot be completed by the coder alone)

1. Label adjudication by ≥2 independent human reviewers (Phase 2B outputs enable it).
2. Licensing decision for corpus redistribution (Phase 6A).
3. Approval of donor-pool design choice (Phase 1C) and of this plan's decision gates.
4. Optional: explorer/API keys for conflict-evidence enrichment (2A) and archive-node RPC (2C).
5. Final acceptance of contribution structure after Gates A/B resolve.
