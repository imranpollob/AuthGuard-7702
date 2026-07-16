# AuthGuard-7702 — Repository Audit (Revision v2, planning pass)

Date: 2026-07-16. Audit is read-only; no source, dataset, result, or manuscript file was
modified. All line references were verified against the working tree at commit `e553e7b`
(branch `main`).

---

## 1. Repository structure

```
/ (repo root)
├── capability_dataset.csv            # ORIGINAL corpus, 3,258 rows (FROZEN input)
├── family_assignment_frozen.csv      # frozen family_id @0.85 (+ 0.75/0.90 columns) (FROZEN)
├── benign_7702_bytecode.csv          # fetched benign 7702 delegate bytecodes (input aux)
├── independent_malicious.csv         # independent-set confirmed candidates
├── uncertain_candidates.csv / unverified_candidates.csv / network_query_log.csv
├── advtrain_results.json             # ORIGINAL-cohort G-ADV aggregates (FROZEN result)
├── paired_results.csv                # ORIGINAL-cohort G-ADV per-row scores (FROZEN result)
├── run_all.sh                        # reproduces ORIGINAL (superseded) pipeline A–F
├── DECISIONS.md / RESULTS_README.md / results_summary.md / recon_report.md / phase0_report.md
├── bracket_family_count.py           # legacy family counter (superseded by 01_freeze_families)
├── fetch_benign_7702_delegates.py    # benign-delegate fetch script (network)
├── pipeline/                         # all experiment code (see §2)
├── results/                          # ORIGINAL-cohort frozen outputs (see §12)
├── reports/                          # original G-ADV reports, independent-set reports, planning notes
├── paper_build/                      # CURRENT PRIMARY EVIDENCE + manuscript (see below)
│   ├── data_hygiene/                 # task-aligned v1 dataset, protocol, results (FROZEN v1)
│   ├── statistics/                   # family-clustered paired bootstrap (G-ADV CIs)
│   ├── runtime/                      # local scorer timing benchmark + results
│   ├── figures/ tables/ sections/    # generated PDFs, .tex tables, section sources
│   ├── overleaf/main.tex             # the ICTAI manuscript (single file) + references.bib
│   └── *.md                          # claim/number/consistency audits
├── USENIX EIP-7702 artifact/         # upstream label source + Gigahorse client files (read-only)
├── scamsonethereum-main/             # independent blacklist source (7,915 addresses)
├── PTXPhish-main/                    # auxiliary phishing dataset (unused in pipeline)
└── PhishingHook Zenodo artifact/     # auxiliary artifact (unused in pipeline)
```

Two evidence generations coexist:

| generation | dataset | outputs | status |
|---|---|---|---|
| original | `capability_dataset.csv` (793/1,657/800/8) | `results/*.json`, `advtrain_results.json`, `paired_results.csv`, `reports/advtrain_*` | frozen, superseded; kept for reconciliation |
| **task-aligned v1 (paper numbers)** | `paper_build/data_hygiene/task_aligned_dataset_v1.csv` (727/1,553/797/5) | `paper_build/data_hygiene/task_aligned_*` | **frozen primary evidence** |

## 2. Active training and evaluation entry points

| entry point | role | status |
|---|---|---|
| `run_all.sh` → `pipeline/01…07` | original end-to-end chain (families, features, G-DET, G-MUT/G-VOL, supporting, figures, summary) | superseded; do not rerun into frozen outputs |
| `pipeline/adv_run.py` (+`adv_analysis.py`, `adv_figures.py`, `adv_report.py`) | original-cohort G-ADV | superseded |
| `paper_build/data_hygiene/task_alignment.py` | builds task-aligned v1 dataset + designator/conflict audits + stored outer folds | **frozen v1 generator** |
| `paper_build/data_hygiene/task_aligned_rerun.py [det|mut|adv]` | reruns G-DET/G-MUT/G-VOL/G-ADV on v1, importing `03_detection.run_cv`, `04_mutations`, `adv_run` primitives via importlib | **produced the paper numbers** |
| `paper_build/statistics/family_clustered_bootstrap.py` | paired family-clustered bootstrap CIs for AuthGuard-M0 vs -aug (M0/M3/F200) | current |
| `paper_build/runtime/run_runtime_benchmark.py` | local scorer timing (Apple M1) | current |
| `pipeline/ind_01…ind_06` | independent-set funnel (blacklist → 7702 designators → 9 targets → 1 truly novel) | current, verdict INSUFFICIENT DATA |
| `paper_build/figures/generate_*.py` | 3 PDF figures from task-aligned JSON | current |

## 3. Dataset sources

- `capability_dataset.csv` (3,258 rows: malicious 793, benign_cleared 1,657, benign_general 800,
  benign_AA 8). Columns used: `address, chain, class, bytecode`; `cap_*` columns and `chain`
  are banned as features (DECISIONS.md D4). Positives derive from the USENIX
  `eoa_detect` artifact; `benign_cleared` = rule-silent weak negatives from the same population.
  **The construction script for this CSV is not in the repository** (described in
  `recon_report.md`); noted in §16 as a reproducibility gap.
- `paper_build/data_hygiene/task_aligned_dataset_v1.csv` (3,082 rows: 727/1,553/797/5) — derived
  by `task_alignment.py`: 76 `ef0100…` designator rows resolved (3 recovered+retained,
  29 excluded as cross-family exact duplicates, 44 excluded unresolved), then all 23
  cross-class exact-hash groups (103 rows) quarantined. Carries stored `outer_fold_primary`
  and `outer_fold_secondary` per row, plus per-row provenance columns.
- `USENIX EIP-7702 artifact/eoa_detect/decompile/AM_Detect_SensitiveSigName.jsonl` — seeds the
  sensitive-selector set (`ag_features.build_sensitive_selector_set`).
- Independent set: `scamsonethereum-main/{master_blacklist_set,all_across_hard}.txt` (7,915
  unique addresses), processed by `ind_01…ind_06` with read-only `eth_getCode`.
- `benign_7702_bytecode.csv` from `fetch_benign_7702_delegates.py` (delegate targets observed
  on-chain); feeds benign_AA/benign_7702 context.

## 4. Current task-alignment implementation

`paper_build/data_hygiene/task_alignment.py`:
- Designator handling (lines 128–190): for each `ef0100||target` row, recover the target's
  runtime from a same-chain dataset row, else read-only RPC (`designator_rpc_cache.json`);
  retain only if the recovered runtime's exact hash does not already exist in another family;
  else exclude. Full per-row audit in `designator_audit.csv`.
- Conflict quarantine (lines 200–233): every exact normalized-bytecode SHA-256 carrying >1
  class is quarantined in full → `conflicting_bytecodes.csv` (23 groups, 103 rows) with coarse
  `evidence_assessment` ∈ {unresolved_binary_label_conflict, contextual_negative_subset_overlap}.
- Fold preservation (lines 72–82, 236–239): outer fold identities are recomputed from the
  ORIGINAL population's GroupKFold(5) on frozen `family_id` and stored per retained row
  (`outer_fold_primary`, `outer_fold_secondary`). Families never straddle folds (asserted).
- Protocol frozen and hashed: `task_alignment_protocol.md` sha256
  `6368be0b…16083b`; artifact hashes in `task_aligned_result_provenance.md`.

## 5. Current family-construction implementation

`pipeline/01_freeze_families.py` + `pipeline/ag_common.py`:
- Deterministic linear-sweep disasm → opcode 4-grams → seeded blake2b MinHash (128 perms,
  xor-permutation) → union-find over pairs with signature-equality fraction ≥ threshold.
- Global (cross-class) clustering of all 3,258 rows (DECISIONS.md D1) so conflicting-label
  near-duplicates share one family.
- Frozen at threshold 0.85; 0.75 and 0.90 stored as columns `family_id_075/090` in
  `family_assignment_frozen.csv` (**already available — no reclustering needed for Phase 3C
  threshold sensitivity on the frozen clustering**). Family counts: 1120 / 1329 / 1511.
- Task-aligned rerun retains original `family_id` without reclustering (outcome-blind).

## 6. Current outer folds

- `GroupKFold(n_splits=5)` on frozen `family_id` over the task population, computed on the
  ORIGINAL population and stored per row in `task_aligned_dataset_v1.csv`
  (`outer_fold_primary` for malicious∪benign_cleared, `outer_fold_secondary` adding
  benign_general). `task_aligned_rerun.StoredFoldSplitter` replays them verbatim.
- Random diagnostic: `KFold(5, shuffle=True, random_state=7702)`.
- G-ADV role rotation: test = fold f, validation = fold (f+1) mod 5, train-fit = remaining 3.

## 7. Current threshold-selection implementation (traced, not guessed)

| protocol | code | procedure |
|---|---|---|
| G-DET (and its task-aligned rerun) | `pipeline/03_detection.py:75-88, 157-178` | fit model on outer-train rows; score the **same fitted training rows**; threshold = max-F1 on those **in-sample** scores; apply once to outer test. |
| G-MUT / G-VOL | `pipeline/04_mutations.py:202-207, 250-258` and `task_aligned_rerun.run_mut` | identical in-sample train max-F1 per fold. |
| G-ADV | `pipeline/adv_run.py:120-124, 186-192` | thresholds = max-F1 on **clean-M0 predictions of a family-disjoint validation fold** ((f+1) mod 5); train-fit uses only the other 3 folds. |
| Independent set frozen thresholds | `pipeline/ind_06_detectors.py:72-87` | models fit on the FULL original primary corpus; thresholds = max-F1 on **in-sample training** scores; frozen to `reports/frozen_thresholds.json` before scoring targets. |

Conclusion: **reviewer issue 3 is factually correct for G-DET, G-MUT, G-VOL, and the frozen
independent-set thresholds** (in-sample fitting predictions), and **incorrect for G-ADV**
(separate family-disjoint validation fold). Ranking metrics (AUPRC/AUROC) are unaffected;
thresholded metrics (F1/P/R, all G-MUT/G-VOL recalls) are affected. FPR is currently reported
only in G-ADV, not G-DET.

## 8. Mutation-generation implementation

`pipeline/04_mutations.py`:
- `mut_metadata` (M1): randomize CBOR metadata trailer bytes (or append synthetic trailer).
- `mut_addr_immediates` (M2a): randomize PUSH20 immediates in executable region.
- `mut_deadcode_append` (M2b/F*): append `STOP + donor-chunk` after everything; offsets unshifted.
- `mut_selector_rewrite` (M3): randomize PUSH4 immediates matching sensitive selectors.
- `make_mutant` composes tiers cumulatively (M2 includes +20% dead code).
- RNG: `det_rng(seed_material)` = blake2b(salt=7702) keyed by `"meta:"/"addr:"/"dead:"/"sel:" +
  address (+frac)`. In G-ADV, `make_variant` prefixes the seed with domain `train:`/`test:`
  (`adv_run.py:50-57`), separating train/test random domains. In G-MUT/G-VOL there is no domain
  prefix, but only held-out malicious are ever mutated, so no train-side variant exists.
- Preservation checker `verify_preservation`: pre-metadata opcode-token sequence identity
  (linear sweep). It is a **syntactic structure check**, not execution equivalence; the
  manuscript already words this correctly ("structure-preserving", "checker-defined").

## 9. Flooding donor-selection implementation

`pipeline/04_mutations.py:128-155` `_load_deadcode_source()`:
- Donor = **the first `benign_general` row of the ORIGINAL `capability_dataset.csv`**, executable
  region only, cached in a module global. One single donor contract for every flooded variant.
- Properties (verified by code trace):
  - the same donor bytes are used for **train-side augmentation variants (F25/F50/F100) and
    test-side variants (F25…F200) in G-ADV** — only the chunk offset differs (seeded per
    domain/address/frac);
  - the donor is fixed across folds and partitions; no recipient/donor provenance is recorded
    (only `mutation_seed` strings in `*_paired_results.csv`);
  - the donor contract belongs to `benign_general`, which is **outside the primary task
    population** (malicious vs benign_cleared) but **inside the secondary task and the
    `benign_general` control**, and its family is not partition-tracked;
  - the task-aligned rerun still loads the donor from the ORIGINAL dataset (module import),
    regardless of whether that row survived task alignment.
- Consequence: G-ADV augmentation gains under F200 could partly reflect adaptation to this
  specific donor's byte distribution rather than flooding in general (reviewer issue 7 —
  valid for G-ADV). For G-MUT/G-VOL, models are trained on M0 only, so there is no
  train-side exposure; the concern there is external validity (single-donor flooding), not
  train/test leakage.

## 10. Model implementations

- AuthGuard: `XGBClassifier(n_estimators=300, max_depth=6, lr=0.1, subsample=0.9,
  colsample_bytree=0.8, tree_method=hist, random_state=7702)` on the full 773-dim
  representation. Fallback `HistGradientBoostingClassifier` if xgboost unavailable
  (03_detection only).
- Hyperparameters are constant everywhere (`adv_run.XGB_HP`, `04_mutations.gb`,
  `03_detection.gb_clf`, `ind_06`, runtime benchmark); no HP search against test folds
  (estimator choice justified on validation folds, DECISIONS.md D9b).
- Single seed (7702), single run per fold — no repeated-seed variance estimates.

## 11. Baseline implementations

Current: `usenix_shipped_oracle` (label-as-detector; tautological on M0),
`usenix_name_rule` (sensitive-selector presence), `usenix_struct_rule` (call-opcode presence),
`blocklist` (exact-hash memorization of train malicious), `opcode_rf`, `opcode_xgb`
(225-dim histogram), `selector_model` (standardized logistic regression on 13 selector/structural
columns), `authguard`. G-ADV adds `opcode-histogram XGBoost-aug` and `AuthGuard-aug`.

Missing vs Phase 3A: opcode n-gram TF-IDF + LR, TF-IDF + linear SVM, hashed-n-gram-only XGB.
No feature-ablation grid exists.

## 12. Feature extraction

`pipeline/ag_features.py` (single source of truth for bulk + on-the-fly mutant featurization):
- dense = 225 opcode-histogram (frequency-normalized, PUSHn collapsed) + 36 structural/selector
  scalars = 261 columns; sparse = 512 hashed opcode-4-gram bins (blake2b seed 2, count/|grams|
  normalized) → **773 total** (matches paper).
- Structural block includes `code_bytes`, `n_ops`, counts and densities of jumps/calls/etc.,
  PUSH-size stats, `is_delegation_ptr`, `has_sensitive_selector`, `n_sensitive_selectors`, and
  7 `has_<generic-signature>` indicators (real keccak via pycryptodome).
- Banned: `chain`, `cap_*`, `family_id` (asserted out; DECISIONS.md D4).
- `feature_meta.json` / `task_aligned_feature_meta.json` freeze column order; the rerun asserts
  column identity with the frozen meta.

## 13. Runtime benchmark

`paper_build/runtime/run_runtime_benchmark.py` + `runtime_results.json` + `runtime_protocol.md`:
model trained on full task-aligned primary population; 300-contract seeded sample (sample-ID
hash recorded); 30 warmup calls; 3,000 timed single calls (mean 3.411 ms, p95 9.514 ms) and
10×300 batches (3.197 ms/contract); environment versions recorded; scope explicitly excludes
RPC/parsing/loading/wallet. Hardware string "Apple M1" is hard-coded (line 81) rather than
detected — acceptable but note for artifact.

## 14. Result-generation and manuscript-generation dependencies

- Paper tables: `paper_build/tables/*.tex` (dataset_composition, gdet_performance,
  gmut_robustness, gadv_results) — **hand-materialized** from the task-aligned JSONs
  (no generator script found for the .tex tables; number audits in `final_number_audit.md`
  substitute for automation). Figures have generator scripts (`paper_build/figures/generate_*.py`).
- Manuscript: `paper_build/overleaf/main.tex` (436 lines, single file) + `references.bib`;
  section sources in `paper_build/sections/*.tex` (pre-assembly copies).
- Traceability: `paper_build/result_provenance.md`, `data_hygiene/task_aligned_result_provenance.md`
  (SHA-256 per artifact), `claim_to_evidence.md`, `final_number_audit.md`.
- `results_summary.md` (original cohort) is auto-generated by `07_summary.py`.

## 15. Existing tests and assertions

There is **no test suite** (no pytest/unittest files). Runtime assertions embedded in code:
- `adv_run.py` / `task_aligned_rerun.run_adv`: source/family/hash overlap = 0 across
  train/val/test; mutant family inheritance; logged to `*_leakage_assertions.txt`.
- `task_alignment.py`: frozen family file row-alignment; family-to-single-fold assertion.
- `task_aligned_rerun.load_dataset`: feature-column identity with frozen meta.
- `02_features` / determinism checks documented in RESULTS_README (PYTHONHASHSEED invariance).
- Preservation verification: 793/793 (original) and task-aligned equivalents in
  `*_mutation_preservation.json`.

## 16. Missing or ambiguous components

1. **No per-row score persistence for G-DET/G-MUT/G-VOL** — only fold aggregates are stored.
   Family-clustered bootstrap CIs for G-DET (Phase 1D) require a rerun that emits per-row
   test scores (G-ADV already persists `task_aligned_paired_results.csv`).
2. **No FPR in G-DET metrics** (`metrics_at` lacks it).
3. **Dataset construction script for `capability_dataset.csv` absent** (provenance narrative
   only in `recon_report.md`); exact reconstruction from the USENIX artifact is not scripted.
4. **No requirements.txt / lockfile**; environment versions recorded only inside
   `runtime_results.json` and RESULTS_README prose.
5. **No execution harness**: no deployable contracts, exploit scripts, local EVM tests, or
   transaction traces anywhere in the repo (PTXPhish/PhishingHook/USENIX artifacts contain
   datasets and Datalog client files, not runnable exploits). Phase 2C must build from zero
   (e.g., foundry/anvil fork tests) or be descoped.
6. **Gigahorse toolchain absent**: the USENIX artifact ships client files
   (`analyze.dl`, `run_analysis.sh`, `main.py`, `env.yaml`) and intermediate outputs
   (`detect_result.jsonl`, `AM_*.jsonl`), but Gigahorse+Soufflé themselves must be installed
   (upstream repo/Docker). Feasibility gate in Phase 5.
7. **Donor provenance not recorded** for flooded variants (recipient/donor IDs, byte-range
   hashes) — required by Phase 1C.
8. **Hand-typed table values** in `paper_build/tables/*.tex` (audited but not generated).
9. **`frozen_thresholds.json` trained on the original cohort** (793/1,657), not task-aligned;
   the benign_general FPR control in `reports/independent_detection.json` therefore predates
   task alignment (n=800, AuthGuard 10/800 = 1.3% flagged) and uses in-sample thresholds.
10. Stray `__pycache__/` at repo root and modified `.DS_Store`; root `figures/` output dir is
    not present in the tree (original 06_figures outputs were not committed).
11. Git LFS configured (`.gitattributes`) for large CSVs — artifact packaging must account
    for LFS availability.
12. `benign_AA` is n=5 after task alignment (n=8 original) — case-observation only, as planned.
