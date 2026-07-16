# Reviewer Issue Map — validity, affected artifacts, required work

Legend: Solvability ∈ {fully, partially, not-currently}. "Affected experiments" name the
protocol groups whose numbers or interpretation change. Manuscript refs are to
`paper_build/overleaf/main.tex`.

---

## Issue 1 — Source-derived labels and insufficient independent validation

- **Valid?** YES. All 727 positives derive from one USENIX rule pipeline; weak negatives are
  rule-silent from the same population. Independent funnel (`pipeline/ind_01…06`,
  `reports/funnel.json`) yielded exactly **1** truly novel confirmed positive → verdict
  INSUFFICIENT DATA (already stated in the paper, §Validity).
- **Affected files:** `capability_dataset.csv`, `task_aligned_dataset_v1.csv`,
  `pipeline/ind_*`, `reports/independent_*`, manuscript abstract/§5/§6.
- **Affected experiments:** interpretation of every protocol (labels define the task); no
  numeric change.
- **Scientific risk:** HIGH — "detection" claims may be read as rule-mimicry
  (`reports/ictai_reviewer_assessment.md` O1 calls it near-fatal for a detection framing).
- **Solvability:** PARTIALLY. Cannot mint independent ground truth from the repo. Can (a)
  build the manual label-audit package (Phase 2B) for later human adjudication, (b) sharpen
  the existing mitigation (M3 removes the name-rule footprint yet recall persists), (c) frame
  the task explicitly as "artifact-aligned screening" throughout.
- **Required implementation:** stratified sampling + anonymized review forms + evidence
  packets + agreement scripts (Phase 2B). No model changes.
- **Required human input:** ≥2 independent human reviewers for adjudication; final labels.
- **Expected manuscript change:** framing already mostly honest; strengthen §Dataset
  provenance wording; add label-audit protocol description once human labels exist (or state
  package prepared, adjudication pending).

## Issue 2 — Conflicting identical-bytecode labels

- **Valid?** YES, and partially handled. 23 exact-hash groups (103 rows) are quarantined
  outcome-blind (`task_alignment.py`; `conflicting_bytecodes.csv`), but the per-group
  `evidence_assessment` is only a 2-way coarse category; no deployment/initialization/
  dependency evidence was collected; no abstention rule exists.
- **Affected files:** `paper_build/data_hygiene/conflicting_bytecodes.csv`,
  `task_alignment.py`, manuscript §Dataset.
- **Affected experiments:** none numerically (quarantine is the frozen primary); the
  before-quarantine sensitivity is exactly the original-cohort frozen results
  (`original_vs_task_aligned.md` provides the reconciliation table already).
- **Scientific risk:** MEDIUM — reviewers may ask what the conflicts *are* and whether
  bytecode-only screening is even well-posed for them.
- **Solvability:** FULLY for the analysis (Phase 2A: per-group evidence packets, 5-way
  categorization, machine-readable report, abstention/escalation rule evaluation);
  chain metadata collection needs read-only RPC/explorer access (optional).
- **Required implementation:** `revision_v2/experiments/conflict_analysis/` — group-level
  collector + categorizer + abstention-rule evaluator (flag known-conflict hashes → escalate).
- **Required human input:** none mandatory; explorer API keys optional.
- **Expected manuscript change:** short subsection + table characterizing the 23 groups;
  motivates Gate B (bytecode-insufficient cases) — this is the natural bridge to the
  selective-escalation contribution.

## Issue 3 — G-DET threshold-selection ambiguity

- **Valid?** YES — CONFIRMED by trace (see `current_protocol_reconstruction.md`): G-DET,
  G-MUT, G-VOL, and frozen independent-set thresholds use **in-sample fitting predictions**;
  G-ADV uses a family-disjoint validation fold.
- **Affected files:** `pipeline/03_detection.py` (best_f1_threshold usage),
  `04_mutations.py`, `ind_06_detectors.py`, `task_aligned_rerun.py`; results:
  all `*_detection_results.json` F1/P/R, all `*_mutation_curve/volume.json`,
  `reports/frozen_thresholds.json`; manuscript G-DET/G-MUT tables.
- **Affected experiments:** G-DET thresholded metrics, all G-MUT/G-VOL recalls, benign
  controls at frozen thresholds. **Not** AUPRC/AUROC (headline safe), **not** G-ADV.
- **Scientific risk:** HIGH for protocol credibility; MEDIUM for numbers (direction unknown —
  do not presume inflation).
- **Solvability:** FULLY (Phase 1B): inner family-grouped OOF threshold selection within
  outer-train → freeze → single test evaluation; add FPR; rerun G-DET/G-MUT/G-VOL as v2
  outputs; keep v1 frozen; report deltas.
- **Required implementation:** new `revision_v2/experiments/gdet_v2/` runner (per-row score
  persistence included, feeding Phase 1D).
- **Required human input:** none.
- **Expected manuscript change:** protocol §5.3 rewritten (threshold-transfer validity);
  updated thresholded columns; FPR column added; note that ranking metrics unchanged.

## Issue 4 — Limited semantic validity of transformations

- **Valid?** YES as a scope limitation; the checker verifies only pre-metadata opcode-token
  identity (`verify_preservation`). The manuscript already avoids "semantics-preserving" and
  says the checker "does not prove EVM execution equivalence" (main.tex:102).
- **Affected files:** `04_mutations.py`, manuscript §4/§5 wording; no result files.
- **Affected experiments:** interpretation of G-MUT/G-VOL/G-ADV.
- **Scientific risk:** MEDIUM.
- **Solvability:** PARTIALLY. No execution harness exists in the repo (no deployable
  contracts, exploit scripts, EVM tests, or traces — audited §16.5). A bounded
  execution-validation framework (Phase 2C) can be built with foundry/anvil fork tests for
  ~5–10 representative contracts, comparing original vs transformed on execution success,
  external calls/targets, storage writes, transfers, return values, traces. Full behavioral
  equivalence remains out of scope by design.
- **Required implementation:** `revision_v2/experiments/exec_validation/` (new harness;
  needs foundry or py-evm; feasibility gate — if tooling can't run offline against the
  malicious delegates' entry points, deliver the minimum-implementation report instead).
- **Required human input:** decision on installing foundry/anvil; possibly archive-node RPC.
- **Expected manuscript change:** either "execution-validated on N contracts under tested
  transactions" (bounded) or an explicit statement that validation is syntactic only.

## Issue 5 — Insufficient baselines and feature ablations

- **Valid?** YES. Current baselines lack any tuned text-style model (TF-IDF n-gram LR/SVM,
  hashed-n-gram-only XGB); no ablation isolates which of the 773 features drives the gain
  (structural vs n-gram vs selectors vs code_bytes/metadata shortcuts).
- **Affected files:** `03_detection.py` method registry; new code only.
- **Affected experiments:** G-DET v2 (baselines and ablations run under identical stored folds
  and the corrected threshold protocol).
- **Scientific risk:** MEDIUM-HIGH — a strong simple baseline matching 0.881 would demote the
  model contribution (the risk register covers this; the evaluation-framework contribution
  survives).
- **Solvability:** FULLY (Phase 3A/3B), CPU-cheap at n=2,280. Repeated seeds (≥5) for
  stochastic models. No inadequately tuned deep model will be added.
- **Required human input:** none.
- **Expected manuscript change:** expanded baseline table; ablation table; possibly revised
  claim from "AuthGuard outperforms evaluated bytecode baselines" to whatever survives.

## Issue 6 — Family-threshold and family-weighting sensitivity

- **Valid?** YES. Only family *counts* at 0.75/0.85/0.90 are reported
  (`results/family_structure.json`); no G-DET rerun under alternative thresholds; all metrics
  are observation-pooled (large families dominate); no per-family or duplicate-collapsed view.
- **Affected files:** `family_assignment_frozen.csv` (already has 075/090 columns — grouping
  variants need NO reclustering), `01_freeze_families.py` (recomputed-family sensitivity
  needs a v2 variant run on the task-aligned corpus), new analysis code.
- **Affected experiments:** G-DET v2 sensitivity arms; diagnostics (family-size distributions,
  cross-class counts, chaining diagnostics).
- **Scientific risk:** MEDIUM — if conclusions flip at 0.75/0.90, the frozen 0.85 choice looks
  knife-edge (family counts are smooth, but performance sensitivity is untested).
- **Solvability:** FULLY (Phase 3C/3D). Frozen families stay primary; recomputed families are
  a labeled sensitivity analysis only.
- **Required human input:** none.
- **Expected manuscript change:** sensitivity paragraph + appendix-style table; weighting
  results (inverse-family-size, one-vote-per-exact-bytecode, family-macro recall/FPR,
  family-clustered pooled metrics; NO averaging of tiny per-family AUPRCs).

## Issue 7 — Possible flooding donor leakage

- **Valid?** YES for G-ADV augmented models — confirmed by trace: one fixed benign_general
  donor supplies padding bytes to BOTH training-augmentation variants and held-out test
  variants in every fold (`04_mutations._load_deadcode_source`); only chunk offsets differ.
  No donor provenance is recorded. For G-MUT/G-VOL (M0-trained models) it is an external-
  validity caveat (single donor), not train/test leakage.
- **Affected files:** `04_mutations.py:128-155`, `adv_run.py:50-57`, all `*advtrain*` and
  `*paired_results*` outputs, `family_clustered_bootstrap.*`, `figures/advtrain_heldout.pdf`,
  `tables/gadv_results.tex`, manuscript RQ4 and abstract sentence on augmentation.
- **Affected experiments:** **G-ADV in full (marked for regeneration)**; G-MUT M2 / G-VOL get a
  donor-diversity robustness arm rather than regeneration.
- **Scientific risk:** HIGH — the F200 recovery (0.484→0.727) is a headline claim; if it
  shrinks under donor isolation the augmentation contribution weakens (fallback: report the
  corrected number; the framework contribution stands).
- **Solvability:** FULLY (Phase 1C): partition-isolated donor pools (train variants ←
  train-family benign donors; val ← val; test ← test), multi-donor sampling, full provenance
  ledger (recipient source/family/partition, donor source/family/partition, byte-range hash,
  seed, condition), assertions on both sides.
- **Required human input:** none. Decision: donors drawn from benign_cleared (in-population)
  vs benign_general (current source) — recommend benign_general partitioned by family AND
  excluded from any population the fold evaluates, with benign_cleared-donor arm as check.
- **Expected manuscript change:** RQ4 numbers replaced by donor-isolated results + provenance
  description; adds credibility even if the effect shrinks.

## Issue 8 — Unsupported deployment and robustness claims

- **Valid?** YES. Confirmed instances in `paper_build/overleaf/main.tex`:
  - abstract (line 21): "robust, **production-ready** pre-authorization warning signal";
  - contributions (line 47): "sub-10ms latency, **enabling real-time screening integration**";
  - RQ5 (line 400): "**proves** … **seamlessly integrated** … **without degrading the user
    experience**";
  - conclusion (line 432): "establishes a **robust, highly efficient** AI-driven pipeline …
    setting a methodological benchmark";
  - abstract: "**significantly** recovers detection performance" (pre-donor-audit; CI exists
    for F200 only, and those numbers are now marked for regeneration).
  Counterweight: §Related/§Discussion already correctly disclaim speedup vs Gigahorse, wallet
  integration, and compound flooding.
- **Affected files:** manuscript only (+ sections/*.tex copies).
- **Scientific risk:** HIGH (easy reject trigger), trivially fixable.
- **Solvability:** FULLY (Phase 1A list now; apply edits in Phase 6C after numbers stabilize).
- **Required human input:** none.
- **Expected manuscript change:** replace with supported positioning (low local scoring cost
  on tested platform; improvement under specified held-out conditions; complementary
  screening; superiority over evaluated bytecode baselines).

## Issue 9 — Missing secondary-control results

- **Valid?** PARTIALLY. The secondary task (adds benign_general) IS evaluated
  (AUPRC 0.871). Per-class FPR at frozen thresholds exists only for the ORIGINAL cohort
  (`reports/independent_detection.json`: AuthGuard flags 10/800 = 1.3% of benign_general;
  benign_AA 1/8) with in-sample-trained thresholds; nothing for task-aligned 797/5; no score
  distributions, p95, alerts/1,000, or top-scoring cases in the paper.
- **Affected files:** `ind_06_detectors.py` (pattern to reuse), new
  `revision_v2/experiments/secondary_controls/`.
- **Affected experiments:** new control evaluations at corrected frozen thresholds (Phase 2D);
  benign_AA (n=5) reported as case observations only.
- **Scientific risk:** LOW-MEDIUM; cheap credibility gain.
- **Solvability:** FULLY.
- **Required human input:** none.
- **Expected manuscript change:** small table (FPR, median/p95 score, alerts per 1,000,
  highest-scoring cases) + operational analysis tie-in (Phase 6B).

## Issue 10 — Incomplete reproducibility

- **Valid?** PARTIALLY. Strengths already present: determinism (seeded blake2b throughout,
  PYTHONHASHSEED-invariant), frozen protocol + artifact SHA-256 ledger
  (`task_aligned_result_provenance.md`), leakage-assertion logs, machine-readable results.
  Gaps: no requirements lockfile; no test suite; `capability_dataset.csv` construction not
  scripted in-repo; paper tables hand-materialized; donor provenance absent; LFS-dependent
  large files; no packaged anonymous artifact.
- **Affected files:** new artifact tree (Phase 6A); `requirements.txt` / env export; table
  generator scripts.
- **Scientific risk:** MEDIUM (artifact-evaluation credibility).
- **Solvability:** FULLY, except third-party data redistribution (USENIX-artifact-derived
  bytecodes; licensing must be checked — fallback: deterministic reconstruction instructions
  + hashes).
- **Required human input:** licensing decision on redistributing bytecode corpus; artifact
  hosting choice.
- **Expected manuscript change:** availability statement; artifact appendix.

---

## Priority ordering by scientific risk × effort

1. Issue 3 (threshold correction) and Issue 7 (donor isolation) — both invalidate/repair
   *protocol* credibility and gate every downstream number → Phase 1.
2. Issue 8 (claims) — zero-cost list now, edits after numbers stabilize.
3. Issues 5, 6 (baselines/ablations/sensitivity) — Phase 3, cheap, high review value.
4. Issues 2, 9 (conflict analysis, secondary controls) — Phase 2, bounded.
5. Issue 1 (labels) and 4 (semantic validity) — partially solvable; human/harness dependent.
6. Issue 10 — Phase 6 packaging.
