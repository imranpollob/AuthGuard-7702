# Current Protocol Reconstruction — G-DET, G-MUT, G-VOL, G-ADV (traced from code)

All statements below are traced from the code paths that produced the paper numbers
(`paper_build/data_hygiene/task_aligned_rerun.py`, which imports `pipeline/03_detection.py`,
`pipeline/04_mutations.py`, `pipeline/adv_run.py` primitives). The original-cohort runs use the
same procedures on `capability_dataset.csv` with freshly computed (identical-fold) GroupKFold
splits. Global seed 7702 everywhere; single seed, single run per fold.

Shared infrastructure:
- Features: `ag_features.featurize` — 225 opcode-hist + 36 structural = 261 dense + 512 hashed
  4-grams = 773 dims. Identical featurizer for corpus rows and generated variants.
- Families: frozen `family_id` (MinHash 0.85) from `family_assignment_frozen.csv`; task-aligned
  v1 retains original family IDs without reclustering.
- Outer folds: stored `outer_fold_primary` / `outer_fold_secondary` columns (GroupKFold(5) on
  frozen families computed on the ORIGINAL population, replayed by `StoredFoldSplitter`).

---

## G-DET (detection under leave-family-out)

| element | traced value |
|---|---|
| fitting population | per outer fold: the 4 training folds of the task population (primary: malicious 727 ∪ benign_cleared 1,553 = 2,280 rows; secondary adds benign_general 797) |
| validation population | **none** — no inner split, no validation fold |
| test population | the held-out outer family fold (evaluated once) |
| family handling | families never straddle folds (stored assignments; asserted at build time) |
| threshold selection | **max-F1 on in-sample predictions of the fitted training rows** (`03_detection.py:157-178`: `fit(X_tr) → predict_proba(X_tr) → best_f1_threshold(ytr, s_tr)`); rules/blocklist use fixed 0.5 |
| refit | none needed (threshold chosen after the single fit) |
| seeds | 7702 (XGB/RF/LR random_state; KFold shuffle for the random diagnostic) |
| mutation conditions | none (clean M0 corpus) |
| donor pools | n/a |
| metrics | AUPRC (primary), AUROC, F1, Precision, Recall — **no FPR** |
| aggregation | mean ± population std (ddof=0) over the 5 folds; per-fold records stored |
| uncertainty | fold std only; **no family-clustered CI; per-row scores are not persisted** |
| output files | `paper_build/data_hygiene/task_aligned_detection_results.json` (original: `results/detection_results.json`) |

**Answer to the mandated question — G-DET thresholds use in-sample fitting predictions.**
They are NOT out-of-fold, NOT from a separate validation set. This holds for `opcode_rf`,
`opcode_xgb`, `selector_model`, and `authguard` in both the original and the task-aligned runs,
and also for G-MUT/G-VOL and the independent-set frozen thresholds
(`ind_06_detectors.py`). It does NOT hold for G-ADV (below).

Consequences (bounded): AUPRC/AUROC (the headline 0.881±0.028 and the random-vs-family gap)
are threshold-free and unaffected. F1/Precision/Recall in G-DET, and every recall in
G-MUT/G-VOL, depend on a threshold whose transfer validity is untested; with n_estimators=300
XGBoost fits train nearly perfectly, so in-sample max-F1 thresholds sit in a
degenerate near-separating score region — the direction of test-side bias is not knowable
without the corrected protocol. Do not presume inflation; describe as threshold-transfer
validity (per revision brief).

Key numbers reproduced from the frozen JSON (primary task, family-grouped):
AuthGuard AUPRC 0.881±0.028 (random split 0.975); opcode_xgb 0.784; opcode_rf 0.744;
selector 0.515; name-rule 0.344; struct-rule 0.328; blocklist 0.321.

---

## G-MUT (mutation stress test, retained detection)

| element | traced value |
|---|---|
| fitting population | per fold: train-fold rows, **original (M0) bytecode only** (primary task population) |
| validation population | none |
| test population | held-out **malicious** rows only, mutated per tier (M0, M1, M2, M3); negatives are not scored in G-MUT |
| family handling | mutants inherit the source row's family; split precedes mutation |
| threshold selection | in-sample train max-F1 per fold per model (same procedure as G-DET) |
| seeds | mutation RNG = blake2b(salt=7702) keyed by `{"meta"|"addr"|"dead"|"sel"}:address(:frac)`; no train/test domain prefix (not needed — only held-out rows are mutated) |
| mutation conditions | M0 original; M1 metadata rewrite; M2 = M1 + PUSH20 randomization + ~20% dead-code append; M3 = M2 + sensitive-selector PUSH4 rewrite. Cumulative. Preservation checker: pre-metadata opcode-token identity, 100% pass recorded |
| donor pools | dead-code donor = first `benign_general` row of the ORIGINAL dataset (single fixed donor; see G-ADV notes) |
| metrics | retained detection = recall at the frozen train threshold, per tier (must be read with G-DET precision; DECISIONS.md D8) |
| aggregation | mean ± std (ddof=0) over 5 folds |
| uncertainty | fold std only |
| output files | `task_aligned_mutation_curve.json`, `task_aligned_mutation_preservation.json` |

Task-aligned means: authguard M0 0.576 → M1 0.608 → M2 0.530 → M3 0.530; name rule
0.043 → 0 at M3; struct rule 1.000 flat; blocklist 0.

## G-VOL (compound dead-code volume sweep)

| element | traced value |
|---|---|
| fitting population | identical to G-MUT (train M0 only; opcode_xgb + authguard refit per fold) |
| test population | held-out malicious, transformed by **full M3 recipe then dead-code append** at frac ∈ {0, 0.25, 0.5, 1.0, 2.0} |
| threshold selection | in-sample train max-F1 (same as G-MUT) |
| donor pool | same single fixed benign_general donor; chunk offset seeded by `dead:address:frac` |
| metrics | recall at frozen threshold vs frac; rules reported for context |
| aggregation / uncertainty | mean ± std over folds; no CI |
| output files | `task_aligned_mutation_volume.json` |

Task-aligned means (authguard): 0.608 → 0.527 → 0.474 → 0.291 → **0.130** at +200%.
This is the **compound M3+F200 condition** the paper reports as unresolved: models here are
M0-trained (no augmentation); the augmented models of G-ADV were **never evaluated under the
compound recipe** (G-ADV's F200 is pure flooding on M0). Closing that gap = evaluate
AuthGuard-aug (with corrected donors) on M3+F200.

## G-ADV (source-balanced augmentation)

| element | traced value |
|---|---|
| fitting population | per fold: 3 train-fit folds. Non-aug models: M0 variants only. Aug models: SEEN = {M0, M1, M2, F25, F50, F100} for **both classes**, per-source weight 1/K (source-balanced) |
| validation population | outer fold (f+1) mod 5, **clean M0 only**, family-disjoint from train-fit and test |
| test population | outer fold f under ALL_TEST = {M0, M1, M2, F25, F50, F100, M3, F200}; HELD-OUT = {M3, F200} never seen in training |
| family handling | asserted zero source/family/hash overlap between train/val/test; variants inherit source family (`*_leakage_assertions.txt`) |
| threshold selection | **max-F1 on validation-fold clean-M0 scores** (out-of-family; defensible) |
| seeds | model seed 7702; variant RNG keyed `domain:address` with domain ∈ {train, test} → train and test random domains are separate **but draw chunks from the same donor bytes** |
| mutation conditions | F-conditions are pure flooding on M0 (no M1/M2/M3 first); M-conditions cumulative as in G-MUT |
| donor pools | **single fixed benign_general donor shared by train-side and test-side variants, all folds, all partitions; no recipient/donor provenance recorded** → the donor-isolation requirement of the revision brief is currently violated by construction |
| metrics | AUPRC, AUROC, precision, recall, F1, FPR, retained_vs_M0, per condition |
| aggregation | mean ± std (ddof=0) over 5 folds |
| uncertainty | paired family-clustered percentile bootstrap (10,000 reps, seeded blake2b) over frozen test families for AuthGuard-M0 vs AuthGuard-aug: Δrecall and ΔFPR at M0/M3/F200; ΔAUPRC at F200 only (`paper_build/statistics/family_clustered_bootstrap.{py,json,md}`); per-row scores persisted in `task_aligned_paired_results.csv` |
| output files | `task_aligned_advtrain_results.json`, `task_aligned_advtrain_thresholds.csv`, `task_aligned_advtrain_composition.csv`, `task_aligned_advtrain_leakage_assertions.txt`, `task_aligned_paired_results.csv` |

Task-aligned means: AuthGuard-M0 F200 recall 0.484 → AuthGuard-aug 0.727; clean-M0 AUPRC
0.819 → 0.863; FPR-M0 0.134 → 0.108. XGB-hist-aug F200 recall 0.756 at FPR 0.284.

### Donor-leakage verdict for the current G-ADV results

Formal donor isolation (train variants ← train-family donors, etc.) is **not implemented**.
The existing leakage assertions cover recipients (sources, families, exact hashes), not donor
bytes. Because the augmented models see F25–F100 variants padded with the same donor's bytes
that pad the F200 test variants, the measured augmentation gain may partly be donor-specific
adaptation (e.g., the 512-bin n-gram signature of that donor). **All G-ADV augmented-model
results are therefore marked "regenerate under donor isolation" per the revision brief.**
Non-augmented rows (AuthGuard-M0, XGB, RF) are not train-side exposed; their F-condition
results have an external-validity caveat (single donor), not a leakage defect. Same caveat
applies to G-MUT M2 and all of G-VOL.

---

## Cross-protocol inconsistency to resolve in v2

Threshold selection differs across protocols (in-sample train for G-DET/G-MUT/G-VOL vs
family-disjoint validation for G-ADV). The v2 protocol should adopt ONE defensible scheme —
recommended: inner family-grouped out-of-fold threshold selection within the outer-train
population (keeps all outer-train data for the final fit; § Phase 1B of the master plan) —
and apply it uniformly, reporting FPR everywhere. Original v1 outputs remain frozen for
reconciliation.
