# AuthGuard-7702 — Project Audit for Next-Phase Planning

Audit date: **2026-07-29**. Read-only audit; no source, dataset, checkpoint, or manuscript
file was modified, deleted, renamed, retrained, or reformatted. Frozen-artifact guard
(`revision_v2/experiments/common/frozen.py verify`) was run before and after this audit and
printed `OK: 144 frozen files verified unchanged` both times. All claims below are traced to
files in the working tree (branch `main`) or to background research agents that read the
working tree read-only; uncertain or undeterminable items are marked explicitly rather than
guessed.

**How to read this document.** The repository already contains an enormous amount of prior
audit work (`revision_v2/audit/`, `revision_v2/planning/`, `revision_v2/paper_handoff/`) from
a completed "Revision v2" program that took the project from a first ICTAI submission draft to
a corrected, dependence-aware benchmark and a finalized set of experiments. That program is
**done** — its outputs are the canonical current evidence base. This document's job is
different: it inventories what exists, verifies key claims against the live files, and scopes
the **next** phase (human adjudication, temporal collection, legitimate controls, ablations,
deployment) that was explicitly out of scope for Revision v2.

---

## 1. Repository overview

### 1.1 Directory tree (important paths only)

```
/ (repo root)
├── PROJECT_AUDIT_FOR_TPS.md          # this report
├── project_inventory.json            # structured inventory (this audit)
├── dataset_census.csv                # per-row census, 3,082 rows (this audit)
│
├── capability_dataset.csv            # FROZEN v0 corpus, 3,258 rows (793/1,657/800/8)
├── family_assignment_frozen.csv      # FROZEN MinHash family_id @0.85 (+0.75/0.90 cols)
├── benign_7702_bytecode.csv          # curated legitimate 7702 delegate bytecodes (input)
├── independent_malicious.csv / uncertain_candidates.csv / unverified_candidates.csv
├── advtrain_results.json / paired_results.csv   # FROZEN original-cohort G-ADV results
├── run_all.sh                        # ORIGINAL (superseded) pipeline driver, phases A–F
├── pipeline/                         # ORIGINAL pipeline code (01–07, ind_01–06, adv_*)
├── results/ , reports/               # ORIGINAL-cohort frozen outputs + planning notes
├── paper_build/                      # FIRST ICTAI submission evidence (task-aligned v1)
│   ├── data_hygiene/                 # task_aligned_dataset_v1.csv + task_alignment.py (FROZEN)
│   ├── statistics/ runtime/ figures/ tables/ sections/ overleaf/main.tex
│
├── revision_v2/                      # CURRENT / CANONICAL evidence generation
│   ├── data/authguardbench_7702_v2.csv.gz     # canonical benchmark, 3,082 rows, 29 cols
│   ├── audit/                        # dataset-correction audit (Part 1–8, see §3)
│   ├── authguard7702/                # model package: model.py, features.py, cli.py, ...
│   ├── experiments/                  # every v2 experiment driver (baseline_v2, robustness_operational_v2, ...)
│   ├── results/                      # mirrored v2 outputs (not independently averaged — see EXPERIMENT_SOURCE_MAP.md)
│   ├── protocols/                    # frozen, hashed protocol docs (threshold, donor isolation, gate criteria)
│   ├── planning/                     # master_execution_plan.md, risk_register.md, reviewer_issue_map.md
│   ├── paper_handoff/                # FINAL_RESULTS_MANIFEST.md, EXPERIMENT_SOURCE_MAP.md, PAPER_REWRITE_HANDOFF.md
│   ├── paper_final/ manuscript/      # rebuild targets for the revised manuscript
│   ├── artifact/label_audit/         # 170-item blinded human-review package (0 labels collected)
│   ├── audits/                       # environment.json, pip_freeze.txt, frozen_ledger.json
│   └── .venv/                        # pandas/xgboost/sklearn env (NO torch)
│
├── USENIX EIP-7702 artifact/         # upstream label-defining artifact (read-only, third-party)
├── PhishingHook Zenodo artifact/     # upstream benign_general source (read-only, third-party)
├── PTXPhish-main/ , scamsonethereum-main/   # auxiliary third-party datasets, partially used
```

### 1.2 Two evidence generations (do not mix)

| Generation | Dataset | Status |
|---|---|---|
| Original cohort | `capability_dataset.csv` (793/1,657/800/8) | frozen, superseded, kept for reconciliation |
| Task-aligned v1 | `paper_build/data_hygiene/task_aligned_dataset_v1.csv` (727/1,553/797/5) | frozen, first ICTAI submission numbers, superseded |
| **Revision v2 (canonical)** | `revision_v2/data/authguardbench_7702_v2.csv.gz` (2,190 primary / 797 external / 5 qualitative / 90 excluded) | **current**, all "next phase" work should build on this |

### 1.3 Entry points

| Stage | Entry point | Status |
|---|---|---|
| Dataset construction | **No script for `capability_dataset.csv` exists in the repo** — narrative only in `recon_report.md`. Downstream: `paper_build/data_hygiene/task_alignment.py` → `revision_v2/audit/scripts/build_benchmark_v2.py` | reproducibility gap, documented |
| Bytecode retrieval | `USENIX EIP-7702 artifact/eoa_detect/get_code/` (upstream, not repo-owned); `fetch_benign_7702_delegates.py`; `pipeline/ind_01_inventory_getcode.py` (independent-set, read-only RPC) | used |
| Preprocessing / disassembly | `pipeline/ag_common.py` — deterministic linear-sweep EVM disassembler, opcode 4-grams, seeded blake2b MinHash | used, canonical |
| Label loading | `revision_v2/audit/scripts/explore_provenance.py` (joins to `detect_result.jsonl`); binding semantics in `revision_v2/audit/LABEL_CLAIM_CONTRACT.md` | used, canonical |
| Duplicate detection | `pipeline/01_freeze_families.py` + `ag_common.py` (exact-hash groups + union-find MinHash) | used, canonical |
| MinHash family construction | `pipeline/01_freeze_families.py` — 128-perm blake2b MinHash, union-find, frozen threshold 0.85 (0.75/0.90 stored as sensitivity columns) | used, canonical |
| Fold generation | `paper_build/data_hygiene/task_alignment.py` — `GroupKFold(5)` on frozen `family_id`, stored per row, replayed by `StoredFoldSplitter` | used, canonical |
| Model training | `revision_v2/experiments/baseline_v2/run_baseline_v2.py` (canonical, 7 models × 3 seeds × 5 folds); model class in `revision_v2/authguard7702/model.py` | used, canonical |
| Calibration | temperature scaling fit on validation-fold logits, inside `run_baseline_v2.py` / `run_authguard_fusion.py` | used, canonical |
| Threshold selection | inner family-grouped OOF max-F1 within outer-train (`revision_v2/experiments/common/harness.py`); nominal 1/5/10% FPR frozen on validation (`authguard7702/policy.py`) | used, canonical |
| Baseline training | `revision_v2/experiments/baseline_v2/run_baseline_v2.py` (Flat CNN, hist+n-gram XGBoost, n-gram-only, BiGRU, dense-only, Transformer) | used, canonical |
| Robustness evaluation | `revision_v2/experiments/robustness_operational_v2/run_robustness_operational_v2.py` | used, canonical |
| Latency evaluation | same driver → `operational_latency_results.csv`, `operational_metadata.json`. Older, superseded local variant: `paper_build/runtime/run_runtime_benchmark.py` (Apple M1, task-aligned-v1 era) | used, canonical (v2) |
| Table/result generation | `revision_v2/experiments/manuscript/generate_tables.py` + `integrate_manuscript.py` → `revision_v2/manuscript/`; frozen paper-handoff snapshot in `revision_v2/paper_handoff/FINAL_TABLES.md` | used, canonical |
| Statistics / bootstrap | `revision_v2/experiments/statistical_analysis_v2/run_statistical_analysis_v2.py` — family-clustered paired percentile bootstrap, 10,000 reps, seed 77022026 | used, canonical |

### 1.4 Completeness / duplication notes

- `pipeline/` (original) and `paper_build/data_hygiene/` (v1) are **frozen, superseded, but intact** — kept for audit reconciliation, not for new work.
- `revision_v2/experiments/long_context_ablation_v3/` and `revision_v2/experiments/multiscale_confirmation_v1/` contain **only stale `__pycache__` files on `main`** — their source (`run_long_context_ablation_v3.py`, `run_multiscale_confirmation_v1.py`) exists on branch `revision-3` (commit `a79a7ea`, based on `699ab37`), which is **not merged into `main`** (verified: `git merge-base --is-ancestor a79a7ea HEAD` → not an ancestor). This is the exact code needed for sequence-length/pooling ablations (§5.5) — it is not lost, just not on the branch currently checked out.
- No test suite exists anywhere in the repository (no pytest/unittest files); correctness relies on runtime assertions embedded in the pipeline code and the frozen-hash guard.

---

## 2. Current dataset census

Computed directly from `revision_v2/data/authguardbench_7702_v2.csv.gz` (3,082 rows, 29
columns) by a fresh script run during this audit (`dataset_census.csv` in the repo root is
the full per-row output; one row per benchmark observation). **Rows, addresses, exact unique
bytecodes, and MinHash families are four different denominators — do not interchange them.**

### 2.1 Headline counts

| Quantity | Value |
|---|---:|
| Total audited rows (all populations) | 3,082 |
| PRIMARY_EVALUATION rows | 2,190 |
| — source-flagged positives | 727 |
| — source-unflagged negatives | 1,463 |
| EXTERNAL_BENIGN_CONTROL rows | 797 |
| QUALITATIVE_CONTROL rows | 5 |
| EXCLUDED_UNCERTAIN_INPUT rows | 90 |
| Unique contract **addresses**, all rows | 2,822 |
| Unique contract **addresses**, primary only | 1,972 |
| Unique **exact** runtime bytecodes (bytecode_sha256), all rows | 2,537 |
| Unique exact bytecodes, primary only | 1,665 |
| Unique exact bytecodes among positives | 549 |
| Unique exact bytecodes among primary negatives | 1,116 |
| Exact-duplicate groups, primary (= unique bytecodes, by construction) | 1,665 |
| Exact-duplicate groups, all rows | 2,537 |
| MinHash similarity **families**, primary | 790 |
| Positive-containing families | 209 |
| Negative-only families | 581 |
| Mixed-label (cross-class similarity) families | 25 |
| Largest family size | 58 rows |
| Median family size | 1.0 row (most families are singletons; the mean is much higher — 16.7 rows/positive-row, 9.8 rows/negative-row per `population_comparability.json` — because a few large attacker-redeployment families dominate row count) |

**2,190 primary rows ≠ 1,972 addresses ≠ 1,665 unique bytecodes ≠ 790 families.** The gap
between rows and unique bytecodes (2,190 → 1,665) is redeployment (same bytecode, multiple
addresses/chains); the gap between unique bytecodes and families (1,665 → 790) is near-duplicate
clustering (MinHash ≥ 0.85 opcode-4-gram similarity).

### 2.2 Rows and labels per chain (primary population)

| Chain | Rows | Positives | Negatives |
|---|---:|---:|---:|
| ethereum | 643 | 232 | 411 |
| bnb | 558 | 163 | 395 |
| base | 483 | 140 | 343 |
| optimism | 212 | 99 | 113 |
| arbitrum | 149 | 52 | 97 |
| polygon | 99 | 29 | 70 |
| gnosis | 46 | 12 | 34 |

(`EXTERNAL_BENIGN_CONTROL`, 797 rows, is single-chain `ethereum(implied)` per
`population_comparability.json` — PhishingHook's dataset does not record chain explicitly.)

### 2.3 Rows and families per fold (primary population, stored `fold_id`)

| Fold | Rows | Positive rows | Negative rows | Positive families | Negative families |
|---|---:|---:|---:|---:|---:|
| 0 | 446 | 152 | 294 | 41 | 117 |
| 1 | 446 | 146 | 300 | 44 | 114 |
| 2 | 427 | 145 | 282 | 41 | 117 |
| 3 | 447 | 93 | 354 | 38 | 118 |
| 4 | 424 | 191 | 233 | 45 | 115 |

Fold prevalence ranges 0.208–0.450 (fold 3 lowest, fold 4 highest) — uneven, as already noted
in prior session state; this is a property of family-disjoint `GroupKFold` on a family-size
distribution with a long right tail, not an error.

### 2.4 Excluded and control rows

- **90 EXCLUDED_UNCERTAIN_INPUT** rows: 89 Excel-truncated (32,767-hex-char cap) `benign_cleared`
  bytecodes + 1 row whose stored "bytecode" was an HTTP-timeout error string. All 90 were
  repaired by prefix-verified `eth_getCode` refetch but excluded from primary because their
  source rule verdict was computed on corrupted/absent input.
- **797 EXTERNAL_BENIGN_CONTROL**: PhishingHook benign-labeled general Ethereum contracts, not
  EIP-7702 delegates — a population-shift control, never mixed into the primary confusion
  matrix (`chain` alone separates it from the primary population at AUPRC/AUROC = 1.000).
- **5 QUALITATIVE_CONTROL**: curated legitimate EIP-7702 delegate implementations (see §9).

---

## 3. Dataset provenance

The construction ledger (`revision_v2/audit/dataset_construction_ledger.csv`) and
`DATASET_AUDIT_REPORT.md` (dated 2026-07-18, produced by scripts under `revision_v2/audit/scripts/`)
already fully reconstruct this. Verified directly against the ledger during this audit:

| Step | Rows | Malicious | Benign_cleared | Benign_general | Benign_AA | Detail |
|---|---:|---:|---:|---:|---:|---|
| S0 original corpus | 3,258 | 793 | 1,657 | 800 | 8 | `capability_dataset.csv`: 793 rule-flagged + 1,657 rule-silent observed delegates + 800 PhishingHook benign + 8 curated AA |
| S1 frozen task alignment | 3,082 | 727 | 1,553 | 797 | 5 | 73 designator-row exclusions (3 recovered runtimes retained), 103 conflicting-exact-bytecode rows quarantined |
| S2 repair Excel truncation | 3,082 | 727 | 1,553 | 797 | 5 | 89 Excel-truncated (32,767-char) `benign_cleared` bytecodes replaced with prefix-verified `eth_getCode` runtime |
| S3 repair fetch-error row | 3,082 | 727 | 1,553 | 797 | 5 | 1 `benign_cleared` row whose stored bytecode was an HTTP-timeout string; true runtime refetched |
| **v2 population split** | 2,190 primary (727/1,463) + 797 external + 5 qualitative + 90 excluded | | | | | 90 rows moved OUT of primary because their source verdict was computed on the (now-repaired) corrupted input |

**This traces the reported 727/1,463/2,190/90 exactly.** The path from S1's 727/1,553 to v2's
727/1,463 is precisely the 90-row move (1,553 − 90 = 1,463); positives are untouched by the
v2 correction.

### 3.1 Does the repo contain the original Huang EOA-targeted population, and is it reproducible?

- `USENIX EIP-7702 artifact/eoa_detect/get_code/contracts_with_bytecode.xlsx` holds the
  **2,685 observed EIP-7702 delegate addresses** (the candidate pool for both classes) —
  this is present and is the origin of both S0 malicious (793) and benign_cleared (1,657 =
  2,685 − 793 − 235 empty-bytecode fetches, verified exactly).
- `USENIX EIP-7702 artifact/eoa_detect/detect_result.jsonl` holds the rule output (793 flagged
  keys; 727 survive quarantine) — present and joined exactly (727/727 retained positives have a
  `detect_result.jsonl` row; 0/1,553 retained negatives do).
- **The transition from S0 (`capability_dataset.csv`) is NOT independently reproducible from
  the repo**: the script that built `capability_dataset.csv` from the USENIX artifact is
  **absent**. `recon_report.md` gives only a narrative description. This is a known,
  already-documented gap (`repository_audit.md` §16.3), not a new finding — flagged again here
  because it blocks a from-scratch artifact rebuild.
- Everything **downstream** of `capability_dataset.csv` (task alignment → v2 correction) **is**
  scripted and reproducible: `task_alignment.py`, `revision_v2/audit/scripts/build_benchmark_v2.py`,
  with SHA-256 hashes recorded in `task_aligned_result_provenance.md` and `revision_v2/audits/frozen_ledger.json`.

### 3.2 Filtering/exclusion rules — exact code path, reason, counts

| Rule | Code path | Positives affected | Negatives affected | Resulting count |
|---|---|---:|---:|---:|
| Empty-bytecode fetch removal | (upstream, pre-`capability_dataset.csv`; not scripted in-repo) | 0 | 235 removed from 2,685 pool | 1,657 benign_cleared |
| Designator (`ef0100‖address`) resolution | `paper_build/data_hygiene/task_alignment.py` lines ~128–190 | 0 (all on negative side) | 76 total: 3 recovered+retained, 73 excluded | −73 rows |
| Cross-class exact-bytecode conflict quarantine | `task_alignment.py` lines ~200–233 | part of 66 removed from 793→727 | part of 103-row/23-group quarantine | 727 positives; conflict rows removed from both sides |
| Excel-truncation repair + primary exclusion | `revision_v2/audit/scripts/repair_truncated.py`, `build_benchmark_v2.py` | 0 | 89 rows moved to EXCLUDED_UNCERTAIN_INPUT | 1,463 primary negatives |
| Fetch-timeout-string repair + primary exclusion | same | 0 | 1 row moved to EXCLUDED_UNCERTAIN_INPUT | (included in the 90 above) |

**Investigated specifically, per the audit brief:**
- *Invalid/missing runtime bytecode*: handled upstream as the 235 empty-fetch removal (not
  scripted in-repo — inherited count only).
- *Excel-truncated bytecode*: 89 rows, all exactly 32,767 hex chars (Excel's cell-length cap);
  repaired via prefix-verified read-only `eth_getCode` refetch (cache: `repair_rpc_cache.json`,
  ledger: `truncation_repair.csv`); 7 of the 89 repaired bytecodes turned out byte-identical to
  curated `benign_AA` implementations — independent confirmation the repair recovered true
  runtime.
- *Timeout strings*: 1 row (`base:0x2521ab07…`) stored the literal string
  `error: HTTPSConnectionPool(… Read timed out …)` as its bytecode; already present in the
  source artifact, not introduced by this repo's pipeline.
- *Exact duplicate removal*: **not removed** — exact duplicates are retained as rows and
  tracked via `exact_duplicate_group`/`exact_duplicate_count` columns; only **cross-label**
  exact-duplicate groups (23 groups / 103 rows) are quarantined.
- *Cross-chain duplicate handling*: retained as separate rows (174 bytecodes appear at multiple
  addresses; 175 appear across multiple chains, per `DATASET_AUDIT_REPORT.md` Part 4); not
  deduplicated away.
- *Conflicting labels*: 23 exact-hash groups / 103 rows quarantined outcome-blind by
  `task_alignment.py`; 0 conflicting-exact-bytecode labels remain in the retained v1/v2 data
  (`split_invariant_audit.json`, assertion `NO_CONFLICTING_EXACT_BYTECODE_LABEL` — PASS).
- *Address-level dedup*: not performed as a filter — addresses are the observation unit; unique
  address counts are reported (§2) but rows are not collapsed by address.
- *Bytecode-level dedup*: not performed as a filter either; `exact_duplicate_group` is a
  descriptive/auditable field, not an exclusion mechanism.
- *Failed retrievals*: the 235 empty-bytecode removals (upstream) and the 90 corrupted-input
  repairs (in-repo) are the only failed-retrieval handling found.
- *Family construction*: see §1.3/§2 — MinHash 128-perm blake2b, union-find, frozen at 0.85.
- *Undocumented filters*: none found beyond the above; every step above has a code path and an
  audit-report entry. The one genuinely undocumented item is the `matched` column in
  `sa_contract_malicious.xlsx` (826 rows, superset of the 793 positives + 13 retained
  negatives) — its semantics are **UNKNOWN** and it is not used as a filter, only cross-referenced
  as a flag (`flag_usenix_matched`).

No rows were found to have vanished without a traceable step; the only unresolved item is the
pre-`capability_dataset.csv` construction script itself (§3.1), which is a **script-absence**
gap, not a row-accounting gap — S0's 3,258/793/1,657/800/8 counts are internally consistent and
independently re-derivable from the USENIX and PhishingHook artifacts still present in the repo.

### 3.3 Mapping the 727 positives to Huang et al.'s manually verified EOA-targeted set

**Not verifiable as "manually verified" from repository data.** The 727 positives are defined
entirely by a **static rule** (Gigahorse/Soufflé decompiled reachability: external call
reachable from `receive()`/`fallback()`) over `detect_result.jsonl` — there is no per-row
transaction, victim, loss, or blocklist evidence for any of the 727 in the repository, and no
file identifies which (if any) of them were part of a separate *manual* verification pass by
the source study. The only manual/independent corroboration found anywhere is **exactly 1**
positive with independent behavioral evidence (`independent_malicious.csv`,
`flag_independent_behavioral_evidence`, victim-account convergence + sweep analysis). The
undocumented `matched` column in `sa_contract_malicious.xlsx` might be a manual-verification
flag from the source study, but its semantics could not be recovered from the artifact
(classification: UNKNOWN in `circularity_signals.csv`) — **do not claim it maps to manual
verification without contacting the source authors or finding an additional artifact file.**

---

## 4. Current label structure

Binding source: `revision_v2/audit/LABEL_CLAIM_CONTRACT.md` (already the project's own
policy document — reproduced/verified here, not re-derived).

- **Where labels come from**: a single deterministic Datalog rule
  (`USENIX EIP-7702 artifact/eoa_detect/decompile/analyze.dl`) run by the source study over
  Gigahorse-decompiled runtime bytecode of the same 2,685-delegate pool the benchmark draws
  from. y=1 ⇔ `(chain,address) ∈ detect_result.jsonl`. y=0 (primary) ⇔ in the pool, non-empty
  bytecode, not in `detect_result.jsonl`.
- **Exact label fields** (in `authguardbench_7702_v2.csv.gz`): `label` (0/1),
  `label_semantics`, `label_source`, `label_evidence_type`, `label_strength` (5-tier:
  `A_curated_legitimate`, `B_external_benign_label`, `C_source_rule_only`,
  `C_source_unflagged_weak`, `D_source_verdict_on_corrupted_input`), `population`,
  `is_eip7702_delegate`, plus 5 boolean cross-reference flags
  (`flag_usenix_matched`, `flag_external_blacklist`, `flag_phishinghook_phishing_bytecode`,
  `flag_independent_behavioral_evidence`, `flag_repaired_matches_curated_aa`).
- **Label-generation code**: this repo does not regenerate labels — it *reads* the upstream
  `detect_result.jsonl` (§3) and joins/tiers them. `revision_v2/audit/scripts/explore_provenance.py`
  performs the join; `build_benchmark_v2.py` assigns tiers/populations.
- **Binary, rule-based, manually verified, or inferred?** Binary and **rule-based**, not
  manually verified (except the curated `benign_AA` control by project documentation, and 1
  positive by independent behavioral evidence).
- **Manual-verification metadata from Huang locally?** No — see §3.3. Not present or not
  recoverable.
- **Are negatives merely analyzer-unflagged?** Yes, entirely — `C_source_unflagged_weak`
  negatives have zero benignity verification of any kind; "unflagged" is the only claim the
  benchmark makes about them.
- **Confidence/uncertainty fields?** Yes — `label_strength` tiers plus the 5 boolean flags above
  function as evidence-strength/uncertainty metadata (this is a deliberate v2 addition, not
  present in the original `capability_dataset.csv`).
- **Legitimate external labels?** Yes, two: `benign_general` (797, PhishingHook-labeled benign,
  a different population — general Ethereum contracts, not EIP-7702 delegates) and `benign_AA`
  (5, curated legitimate delegate implementations by project documentation — see §9).

### 4.1 What would be required to add human-adjudicated labels

A package for exactly this already exists but is **empty of results**:
`revision_v2/artifact/label_audit/` — 170 stratified items (random positives, random weak
negatives, high-scoring false positives, low-scoring false negatives, exact-bytecode conflicts,
highest-scoring `benign_general`), blinded evidence packets
(`evidence_packets.json` — derived structural fields + the model's own risk score; no raw
bytecode/chain/address, by design), per-reviewer blank CSV forms
(`review_form_R{1,2,3}_BLINDED.csv`, columns `anon_id,reviewer_id,label,confidence,rationale`),
a withheld unblinding key, and a kappa-computation script (`agreement.py`, Cohen's + Fleiss'
kappa, majority-vote adjudication only). **`agreement_results.json` confirms 0 labels have ever
been collected.**

To reach the brief's target schema, the following gaps must be closed:
- **Label taxonomy**: current forms use `malicious | benign | uncertain`. The requested
  `SAFE / UNSAFE / INDETERMINATE / NOT-BYTECODE-SCREENABLE` taxonomy does not exist anywhere
  and requires a schema change to `REVIEWER_GUIDELINES.md`, the CSV column, and `agreement.py`'s
  label list.
- **Reviewer IDs**: already present (`reviewer_id` column, `R1/R2/R3`).
- **Independent annotations**: already designed for (blinding instructions + all-3-reviewers
  assignment), but never executed.
- **Adjudication**: `agreement.py` implements only simple majority vote of the same 3 raters —
  there is **no dedicated third-reviewer/tie-break workflow** distinct from the double-reviewer
  pool; a true "2 reviewers + escalate to 3rd on disagreement" workflow needs new logic.
- **Confidence**: already present (`confidence` column, `high|medium|low`).
- **Evidence categories**: evidence packets contain only *derived* structural fields (byte
  count, opcode counts, selector flags, a 40-token opcode prefix, the model's own risk score) —
  no raw bytecode, no disassembly, no links to a block explorer. Richer evidence (full
  disassembly, explorer links) is needed if reviewers are expected to do more than pattern-match
  on summary statistics; this also reopens the circularity concern, since the packets are
  bytecode-derived and partly model-score-derived.
- **Actual human reviewers**: the package is reviewer-ready but zero reviewers have completed
  it — this is a people/scheduling gap, not a code gap.

---

## 5. Model and training inventory

### 5.1 AuthGuard-Seq — implementation and exact architecture

AuthGuard-Seq is **not** a standalone class — it is the shared `AuthGuardFusion` model
(`revision_v2/authguard7702/model.py:71-120`) instantiated with only its sequence view active:
`FusionConfig(active_views=(True, False, False))`. Import chain:
`revision_v2/experiments/baseline_v2/run_baseline_v2.py` (the script that produced the frozen
`baseline_summary.csv`) → dynamically loads `experiments/authguard_fusion/run_authguard_fusion.py`
→ `from authguard7702.model import AuthGuardFusion, FusionConfig`. Independently confirmed by
`revision_v2/audit/scripts/run_sanity_v2.py:172` using the identical construction.

| Property | Value | Source |
|---|---|---|
| Tokenizer | opcode-level; 225 EVM opcodes with `PUSH1..PUSH32` collapsed to one `PUSH` token; `PAD_ID=0`, `UNK_ID=1`, `VOCAB_SIZE=227` | `pipeline/ag_common.py`, `authguard7702/features.py:24-27` |
| Chunk size | 256 tokens | `run_baseline_v2.py:436-444` (hardcoded); `run_authguard_fusion.py:363` (`--chunk-size`, default 256) |
| Max chunks | 64 | `run_baseline_v2.py` (hardcoded, no CLI flag in this script); `run_authguard_fusion.py:364` (`--max-chunks`, default 64) |
| Max opcode coverage | 256 × 64 = 16,384 tokens; contracts longer than this use **evenly-spaced chunk sampling across the whole stream**, not prefix truncation. No contract in the corpus actually exceeds 16,384 (max observed 10,795 tokens per `BASELINE_IMPLEMENTATION_NOTES.md`), so this path is currently inert | `authguard7702/features.py:103-105` |
| Convolution | per-chunk: `Embedding(227→32, pad=0)` → `Conv1d(32→64, k=5, pad=2)` → GELU → `Conv1d(64→64, k=3, pad=2, dilation=2)` → GELU | `model.py:28-38` |
| Pooling (within chunk) | masked **max** pool over tokens | `model.py:49-50` |
| Attention | real attention exists, at **chunk** granularity (not token-level self-attention): `Linear(64→1)` logit per chunk → softmax over chunks → weighted sum of chunk vectors | `model.py:39,53-56` |
| Classifier head | `sequence_view` output, zero-padded-concatenated with two inactive zero views, through a learned gate → `fusion = Linear(256→128)→GELU→Dropout(0.15)→LayerNorm(128)` → `risk_head = Linear(128→1)` | `model.py:71-120` |
| Loss | `BCEWithLogitsLoss(pos_weight = n_neg/n_pos on the train fold)`, ≈2.0 | `run_baseline_v2.py:225` |
| Optimizer | AdamW, lr=1e-3, weight_decay=1e-4, grad-norm clip 5.0 | `run_authguard_fusion.py:254,284` |
| Batch size | 16 | `run_baseline_v2.py:72` (`FUSION_BATCH=16`) |
| Early stopping | best validation AUPRC, patience 5, max 30 epochs | `run_baseline_v2.py:70-71` |
| Calibration | single-scalar temperature scaling, LBFGS on validation logits only (not Platt/isotonic) | `run_authguard_fusion.py:197-212` |
| Thresholds | order-statistic thresholds on validation-negative calibrated scores at nominal 1%/5%/10% FPR, never touching test labels | `authguard7702/policy.py:9-30` |
| Seeds | 7702, 7703, 7704 (actual per-run seed passed is `seed + fold`, not the raw seed) | `run_baseline_v2.py:69,446` |
| Fold rotation | test = fold *f*; validation = fold `(f+1) mod 5`; train = remaining 3 folds; 5 folds × 3 seeds = 15 runs/model | `run_baseline_v2.py:391-396` |

**Parameter count (181,877) — traced, with an important caveat.** Computed by code
(`torch_complexity()`, `run_baseline_v2.py:285-289`, invoked per model at lines 456-461, written
to `baseline_model_complexity.csv`); independently re-derived during this audit's background
research by instantiating the model directly — matches exactly. **Caveat for planning
ablations**: `AuthGuardFusion.__init__` always instantiates all three views (sequence, n-gram,
dense) regardless of `active_views`; `forward()` zeroes the two inactive branches but they still
contribute to the reported parameter count (~117,258 of the 181,877 params never receive a
forward pass under `active_views=(True,False,False)`; they get gradient only via AdamW's
decoupled weight decay). AuthGuard-Seq's *architecturally active* capacity is closer to
`sequence_view`'s 29,985 params plus the active portions of gate/fusion/risk_head — the
complexity/latency table is **not** an apples-to-apples "active capacity" comparison against
`flat_cnn`/`bigru`/`transformer`, which have no dead parameters.

### 5.2 Calibration/threshold artifact locations (v2, canonical)

Per-(model, seed, fold) `temperature`, `threshold_01/05/10` are in
`revision_v2/experiments/baseline_v2/baseline_fold_seed_results.csv` (mirrored, not
independently averaged, to `revision_v2/results/baseline_v2/`). Per-sample raw and calibrated
scores are in `baseline_predictions.csv.gz`. **`reports/frozen_thresholds.json` (repo root) is
an unrelated, pre-revision_v2 legacy artifact** — its keys (`opcode_rf`, `opcode_xgb`,
`authguard`, `selector_lr`) don't match v2 model names and nothing under `revision_v2/`
references it; do not use it for v2 threshold reproduction.

### 5.3 Other baselines in `baseline_summary.csv`

| Model | File | Input budget | Architecture notes |
|---|---|---|---|
| `hist_ngram_xgb` | `run_baseline_v2.py:407-432` | 225-d opcode histogram + 512-d hashed opcode 4-gram (737-d) | XGBoost, 300 trees, depth 6, lr 0.1 |
| `dense_only` | `AuthGuardFusion(active_views=(False,False,True))` | 261-d structural/histogram | `LayerNorm→Linear(261→128)→GELU→Dropout→Linear(128→64)→GELU` |
| `ngram_only` | `AuthGuardFusion(active_views=(False,True,False))` | same 512-d hashed 4-gram vector | same MLP shape as dense_only |
| `flat_cnn` | `run_baseline_v2.py:80-99` | **2,048 tokens**, uniform-stride subsampled | `Embedding(227→64)→Conv1d(k7,ch128)→Conv1d(k5,ch128)→masked max-pool→Linear(128→1)` |
| `bigru` | `run_baseline_v2.py:102-126` | 2,048 tokens | BiGRU(hidden 96), readout = concat[final hidden states, masked mean] |
| `transformer` | `run_baseline_v2.py:129-153` | **1,024 tokens** | d_model 128, 4 heads, 2 layers, FFN 256, learned positional embedding, masked mean pool |
| `authguard_seq` | §5.1 | up to **16,384 tokens** via 256-token chunks | only model with hierarchical chunk structure + chunk attention |

AuthGuard-Seq's larger effective budget (16,384 vs. 2,048/1,024 for the others) is disclosed as
an intentional architectural property in `BASELINE_IMPLEMENTATION_NOTES.md:42-52`, but **this
same budget asymmetry becomes materially important, and is not similarly disclosed, in the
robustness comparison** — see §7.

### 5.4 Missing baselines vs. earlier planning

`revision_v2/planning/experiment_matrix.csv` (Phase 3A) called for TF-IDF n-gram + LR, TF-IDF +
linear SVM, and hashed-4gram-only XGBoost as additional baselines; `revision_v2/results/baselines/`
does contain outputs for these (`hash_xgb.json` and others per the matrix), but they are **not**
part of the `baseline_v2` 7-model official comparison table in `FINAL_RESULTS_MANIFEST.md` — they
exist as a separate, earlier-generation experiment. Anyone adding a new baseline should decide
explicitly whether to compare against the `baseline_v2` protocol (current canonical) or the older
`baselines/` outputs, not both.

### 5.5 Configurability of ablation axes

| Axis | Configurable today without code changes? | Detail |
|---|---|---|
| Sequence length / chunk size / max_chunks | **Partially.** `run_authguard_fusion.py` exposes `--chunk-size`/`--max-chunks` as CLI flags. **But** `run_baseline_v2.py` — the script that actually produced the frozen `baseline_summary.csv` — hardcodes `256, 64` inline at every call site; reproducing frozen v2 numbers with a different chunk size requires editing `run_baseline_v2.py` itself. |
| Attention on/off, mean pooling, "full-stream Flat CNN" | **Code exists but is not on `main`.** `revision_v2/experiments/long_context_ablation_v3/run_long_context_ablation_v3.py` implements exactly this: `ControlledSequenceCNN(aggregation)` with `"flat"/"mean"/"attention"` as a constructor argument, plus a `--models` CLI selecting `flat_control_2048`, `flat_control_16384`, `chunk_attention_control_2048`, `chunk_mean_control_16384`, `chunk_attention_control_16384`, `authguard_reference_16384`. **This file is not present on `main`** (only stale `__pycache__` remains) — its source lives on branch `revision-3` at commit `a79a7ea` (based on `699ab37`), which `git merge-base --is-ancestor a79a7ea HEAD` confirms is **not merged into `main`**. The same applies to `multiscale_confirmation_v1/run_multiscale_confirmation_v1.py` (defines `AuthGuardMSP`, fusing attention+mean+max chunk summaries). **Action: merge or cherry-pick from `revision-3` before attempting this ablation — do not rewrite from scratch.** |
| 2,048-token AuthGuard | Same as above — defined as `chunk_attention_control_2048` on `revision-3`. |
| 8,192-token AuthGuard | **Does not exist anywhere**, on `main` or `revision-3`. Only 2,048 and 16,384 budgets are defined. Requires a new `ModelSpec` entry even after merging `revision-3`. |
| 16,384-token AuthGuard | Exists on `main` as the *trained* AuthGuard-Seq's implicit budget (§5.1); exists explicitly as a labeled ablation arm (`chunk_attention_control_16384`, `authguard_reference_16384`) only on `revision-3`. |

---

## 6. Existing results and reproducibility

`revision_v2/paper_handoff/EXPERIMENT_SOURCE_MAP.md` is the project's own authoritative
paper-number-to-file map; this section reproduces and verifies its key rows rather than
re-deriving them.

| Reported number | Exact source file | Producing command/driver |
|---|---|---|
| **0.924 AUPRC** (AuthGuard-Seq clean) | `revision_v2/experiments/baseline_v2/baseline_summary.csv` (exact: 0.924447943) | `revision_v2/experiments/baseline_v2/run_baseline_v2.py` |
| **0.833 Recall@5% FPR** | same file (exact: 0.832667663) | same |
| **0.920 Flood-200% AUPRC** | `revision_v2/experiments/robustness_operational_v2/robustness_summary.csv` | `revision_v2/experiments/robustness_operational_v2/run_robustness_operational_v2.py` |
| **4.121 ms median screening latency** | `revision_v2/experiments/robustness_operational_v2/operational_latency_results.csv` (full local screening pipeline, 1,500 calls; mean 5.183 ms, p95 14.547 ms, p99 21.429 ms) | same driver |
| Paired 95% CIs (e.g. AuthGuard-Seq − Flat CNN AUPRC +0.039 [+0.009,+0.073]) | `revision_v2/experiments/statistical_analysis_v2/paired_bootstrap_results.csv` | `revision_v2/experiments/statistical_analysis_v2/run_statistical_analysis_v2.py` (family-clustered paired percentile bootstrap, 10,000 reps, seed 77022026) |
| Model complexity (181,877 params; 742,625-byte operational artifact; 737,548-byte raw state) | `revision_v2/experiments/baseline_v2/baseline_model_complexity.csv`; `revision_v2/experiments/robustness_operational_v2/operational_metadata.json` | same drivers |

**Aggregation trap (repeated here because it is easy to get wrong when reusing these files):**
`baseline_summary.csv`'s 0.924447943 AUPRC is **macro-averaged over folds, then over seeds**.
Pooling all rows together gives a different number (0.9113 in a prior check on the older
aggregation). **Any new model must be compared macro-over-folds-then-seeds against these
numbers, never against a pooled re-derivation, or the comparison is invalid.**

### 6.1 Checkpoints, logs, per-fold/seed outputs — located

- Fold/seed traceability: `baseline_v2/baseline_fold_seed_results.csv`,
  `robustness_operational_v2/robustness_fold_seed_results.csv` (3 seeds × 5 folds each).
- Per-row predictions for paired inference: `baseline_predictions.csv.gz`,
  `robustness_predictions.csv.gz` — canonical; per `EXPERIMENT_SOURCE_MAP.md`, "do not rerun,"
  these are the frozen paired-inference source.
- Model checkpoints: `revision_v2/experiments/robustness_operational_v2/models/` and
  `.../checkpoint.json`; the timed seed-7702/fold-0 checkpoint used for the latency number is
  explicitly documented as "a fold-specific cross-validation artifact used for timing and
  illustration, not a final deployment model" (`FINAL_RESULTS_MANIFEST.md` §6).
- Donor-isolation audit: `robustness_operational_v2/donor_isolation_audit.json` — status PASS,
  regenerated live each run, not a stale artifact (confirmed by the §7 research agent).
- Bootstrap distributions: `statistical_analysis_v2/bootstrap_distributions.csv.gz`.
- Generated paper tables: `revision_v2/paper_handoff/FINAL_TABLES.md` (frozen snapshot);
  regenerable via `revision_v2/experiments/manuscript/generate_tables.py`.
- `revision_v2/manuscript/README.md` documents the exact 4-command TeX rebuild
  (`pdflatex`/`bibtex`/`pdflatex`/`pdflatex`) but notes **no TeX engine is installed on the
  finalization host** — `static_audit.json` substitutes for a real build; PDF generation is an
  unverified external step.

All four headline numbers in the brief trace cleanly to a specific file and driver script; none
were found to be free-floating or unsourced.

---

## 7. Robustness implementation (Flood-200% / Rewrite+Flood-200%)

Driver: `revision_v2/experiments/robustness_operational_v2/run_robustness_operational_v2.py`.
This is a **complete rewrite** of the original single-fixed-donor flooding in
`pipeline/04_mutations.py` — it reuses only the byte-level mutation primitives (metadata
rewrite, PUSH20/PUSH4 rewriting) from the old module; flooding itself is a new fold- and
family-isolated multi-donor sampler (`revision_v2/experiments/donor_pools/pools.py`).

- **Donor selection**: donors are drawn from `benign_general`, deduplicated by SHA-256 of the
  executable region, filtered to ≥64 bytes. Each flood call samples donors **uniformly at
  random** via a seeded RNG keyed on `(experiment_id, outer_fold, rng_domain, recipient sid,
  condition, frac)` — deterministic/reproducible, and explicitly **not** the old single
  fixed-donor design (`donor_isolation_protocol.md` documents this as deprecated).
- **Data-partition / family isolation**: donor pool role (train/val/test) is assigned per-family,
  fold-aligned; `flood()` excludes the recipient's own family and asserts disjointness across
  train/val/test pools. `donor_isolation_audit.json` reports **PASS**: 4,380/4,380 expected
  recipient×condition pairs observed, `wrong_partition_rows: 0`,
  `same_recipient_donor_family_rows: 0` — regenerated live each run, not a stale claim.
- **What "200%" means**: 200% of the **recipient's own executable-region byte length**, in
  bytes — not opcode-token count. Appended-donor byte length for F200 has median ≈5,170 bytes
  (from the existing donor ledger, `transformation_donor_ledger.csv.gz`; not re-derived by
  re-running generation). Exact resulting **opcode-token** length distribution is **not
  determinable from stored output alone** (would require re-running disassembly, out of scope
  for a read-only audit) — flagged as an open question for anyone building on this.
- **Handling of over-length sequences**: AuthGuard-Seq is scored with **no `max_chunks` cap** on
  flooded inputs (`create_variants` calls `encode_bytecode` with `max_chunks=None`) — the full
  flooded sequence is chunked with no truncation; the architecture has no positional embedding
  for chunk order, so it is chunk-count-agnostic. Flat CNN explicitly downsamples any sequence
  >2,048 tokens via uniform-stride index selection over the whole stream (same strategy as its
  clean-data path). `hist_ngram_xgb` is length-invariant (aggregate statistics).
- **⚠ Input-budget asymmetry — a genuine, code-confirmed confound not disclosed in the paper
  handoff docs.** AuthGuard-Seq was *trained* with a 256×64=16,384-token cap but is *evaluated*
  on F200/M3+F200 with **no cap at all**, while Flat CNN is capped at 2,048 tokens on both clean
  and flooded data. Given median appended-donor bytes ≈5,170 atop a median executable region of
  roughly half that, flooded sequences plausibly reach several thousand opcode tokens for a
  large share of the test set — well above Flat CNN's budget while AuthGuard-Seq sees the whole
  thing. **The reported F200 AUPRC gap (0.920 vs. 0.535 for Flat CNN, per
  `FINAL_RESULTS_MANIFEST.md`) is therefore potentially confounded by input-budget mismatch, not
  purely attributable to architecture** — this caveat does not appear in
  `FINAL_RESULTS_MANIFEST.md`, `ROBUSTNESS_OPERATIONAL_FINAL_SUMMARY.md`, or
  `ROBUSTNESS_EVALUATION_REPORT.md`. This is the single most important new finding from this
  audit for reviewer defensibility (see Immediate Decisions, item 2).
- **"Rewrite" (M3)**: rewrites CBOR metadata, PUSH20 address immediates, and PUSH4 selector
  immediates matching a sensitive-selector set — token-sequence-preserving by construction for
  the pre-metadata region, but selector rewriting can change *semantics* (a rewritten selector
  routes a call differently). Current v2 docs are already appropriately hedged here: both
  `donor_isolation_protocol.md` and `FINAL_RESULTS_MANIFEST.md` state M3+F200 "is representation
  stress; its rewriting is not guaranteed to preserve semantics" — this is **not** an overstated
  claim; it is more careful than the original (pre-v2) pipeline's implicit framing. A bounded
  empirical execution-fingerprint check exists only for F200 (10 delegates / 100 calls,
  `revision_v2/experiments/adaptive_attacks/run_attack_execution_audit.py`), explicitly labeled
  "bounded evidence, not formal equivalence."
- **Feasibility of an equal-input-budget experiment**: **addable without rewriting baseline
  pipelines.** `create_variants` can call `encode_bytecode(variant, chunk_size=256,
  max_chunks=8)` (8×256=2,048, matching Flat CNN's budget) to produce a budget-capped
  AuthGuard-Seq inference variant as a new condition label, alongside the existing uncapped one.
  `opcode_chunks` already implements evenly-spaced chunk selection when `max_chunks` is set,
  mirroring Flat CNN's linspace downsampling at chunk (not token) granularity. No retraining
  needed — same trained model, different inference-time truncation. `hist_ngram_xgb` has no
  natural "input budget" analogue, so an equal-budget arm meaningfully compares only
  AuthGuard-Seq vs. Flat CNN.

---

## 8. Temporal-data readiness (EIP-7702 delegates by date)

**Current capability: address-in to bytecode-out only. Nothing in the repo discovers new
delegates by date.**

- Every RPC script (`pipeline/ind_01_inventory_getcode.py`, `fetch_benign_7702_delegates.py`,
  `revision_v2/authguard7702/scorer.py`) takes a **pre-existing address list** and calls
  `eth_getCode` at block tag `"latest"`. `scorer.py::score_authorization()` *parses* a
  caller-supplied `authorizationList` object; it does not fetch one from chain.
- **No script anywhere calls `eth_getBlockByNumber`, `eth_getTransactionByHash`,
  `eth_getLogs`, or parses a transaction's `authorizationList` field to discover new
  delegates.** A prior off-`main` manual probe (commit `f86be6f`, branch `revision-3`,
  `reports/00_preflight.md`) confirmed authorizationList data *is* live-readable via
  `eth_getBlockByNumber` with full transactions (13 type-0x04 txs observed in 6 recent mainnet
  blocks) — but this was an ad-hoc test, never committed as reusable code.
- **No timestamps recorded anywhere** — every call uses `"latest"`; no script stores
  `blockNumber` or block time. A date-to-block-number resolver does not exist for any chain.
- **Deduplication**: address-level (`ind_01`, set unions) and bytecode-level (MinHash family
  construction, `01_freeze_families.py`) both exist, but the family builder is a **one-shot
  batch job** over the whole frozen corpus — it doesn't persist per-row MinHash signatures, so
  there is no index to classify one new delegate against existing families incrementally.
  Building "is this new delegate a member of an existing family?" requires new code (reusing
  `ag_common.disasm()`/`minhash_signature()` as primitives, but writing the incremental-match
  logic from scratch).
- **RPC/chain support** (consistent with prior session state, re-verified): no Etherscan/Dune/
  Alchemy/Infura key anywhere. `eth.drpc.org` is the most capable free endpoint (archive state,
  `trace_block`, `trace_filter`, `eth_getLogs` on Ethereum) but has **no JSON-RPC batching**
  (HTTP 500) and `trace_filter` fails on 5/6 non-Ethereum chains. `eth_getCode` works today on
  **all 7 chains** (`fetch_benign_7702_delegates.py`'s `RPCS` table); block/transaction/
  authorizationList scanning works on **none of them** in committed code (only manually
  probed on Ethereum, at a measured throughput implying roughly 5 days single-threaded per
  chain for a Pectra-to-head-sized block range).

**Concretely missing to isolate a Feb 1 to Jun 30 2026 temporal population:**

| Missing piece | Status |
|---|---|
| Date to block-number resolution (any chain) | absent |
| Authorization-list scanning (block/tx-level discovery) | absent; only manual, off-`main` probing |
| Credentials for a paid RPC/indexer tier | absent (free public RPC only) |
| Rate-limit/batching/retry infrastructure for a multi-week scan | absent |
| Timestamp storage schema on delegate rows | absent (no `block_number`/`authorization_timestamp` column exists) |
| Incremental family-classifier for new delegates | absent (batch-only clustering) |

This is a **build-from-scratch** capability, not a configuration gap. Do not begin large-scale
collection without first: (a) validating a date-to-block resolver and authorization-list parser
on a small manual sample per chain, (b) deciding on RPC budget/credentials, and (c) building the
incremental family-classification step so new delegates can be compared against the frozen
0.85-threshold families rather than requiring a full reclustering.

---

## 9. Legitimate external-control readiness

### 9.1 Existing curated legitimate delegates

Source: `fetch_benign_7702_delegates.py` (`SEED_DELEGATES`, 8 projects, 45 chain-rows) leads to
`benign_7702_bytecode.csv`, ingested as class `benign_AA` / population `QUALITATIVE_CONTROL`.
**8 curated projects, 5 survive task alignment** (3 dropped as designator-row exclusions):

| Address | Project | Chains (per script) | Provenance | Confirmed as an actual on-chain 7702 delegate authorization? |
|---|---|---|---|---|
| `0x0000000020fe...7E9D` | Biconomy Nexus v1.3.1 | eth, base, polygon, arbitrum, optimism, bnb, gnosis | `docs.biconomy.io` | No — address-and-docs level only, no authorizationList sighting in-repo |
| `0x000000005c84...030e` | Uniswap Calibur v1.1.0 | eth, base, optimism, bnb, arbitrum | `developers.uniswap.org` | No |
| `0x690077027641...E139` | Alchemy SemiModularAccount7702 | eth, base, bnb, arbitrum, optimism, polygon | Alchemy docs | No |
| `0xd6CEDDe84be4...5b28` | ZeroDev Kernel v3.3 (7702) | eth, optimism, bnb, polygon, base, arbitrum | ZeroDev SDK constants | No |
| `0xe40ccB2D9497...6fA4` | OKX SmartWalletEntry | eth, base, optimism, arbitrum, bnb, polygon | OKX repo README | No |

Dropped from the final control (present in `benign_7702_bytecode.csv`, excluded by task
alignment): MetaMask `EIP7702StatelessDeleGator`, Ambire `EIP7702Account`, Coinbase
`EIP7702Proxy`.

**Minor but real anomaly**: the ZeroDev and Alchemy addresses also independently appear
(different letter case) inside the **rule-silent `benign_cleared`** primary-negative pool —
same label, so no conflict, but it means 2 of the 5 qualitative controls are also separately,
unlabeled-as-curated, present inside the primary negative pool (already documented in
`DATASET_AUDIT_REPORT.md` as a "minor anomaly, not material").

**Cross-chain byte identity**: Ambire, Uniswap Calibur, Alchemy, and Coinbase are byte-identical
across all listed chains. **Biconomy, ZeroDev, OKX, and MetaMask are NOT** — each differs by one
embedded 32-byte constant at a fixed offset (a chain-specific immutable, e.g. a router/entrypoint
address baked in at compile time). Since 3 of the final 5 controls (Biconomy, ZeroDev, OKX) are
in this non-identical group, and `family_assignment_frozen.csv` stores only **one representative
chain row per project**, the frozen family assignment **does not capture the per-chain bytecode
variation** for those three — a gap if per-chain robustness of the control is ever needed.

**Provenance strength**: every entry cites an official project doc/GitHub URL in code comments,
but the script itself explicitly warns these addresses must be independently verified — this is
"cite a docs page," not an audited/attested confirmation, and there is **no evidence of any of
the 5 having actually been used in a live EIP-7702 authorization** (consistent with Section 8's
finding that no authorizationList scanning has ever been performed).

### 9.2 Code to find more legitimate candidates

`revision_v2/experiments/legitimate_registry_expansion_v1/` has **no source on `main`** (only
stale `__pycache__` locally), but full source was recovered read-only from commit `a79a7ea`
(branch `revision-3`). Its `audit_registry_overlap.py` is a **Phase-0-only manual overlap
audit**: it hand-transcribes six addresses from ethereum.org's Pectra/EIP-7702 "Known
implementations" page and checks them for address-level overlap against the existing benchmark
to flag leakage risk — **it does not programmatically scan any registry**, and its own
`IMPLEMENTATION_PLAN.md` states explicitly: "This study can strengthen the paper only as
provenance-backed, leakage-resistant qualitative deployment evidence. It cannot establish a
population benign FPR at n=6."

**No code in the repo automatically scans verified-source registries** (Etherscan
verified-contracts, Sourcify, audit-firm registries) for candidate legitimate delegates. Per the
project's own binding terminology contract (`LABEL_CLAIM_CONTRACT.md`), the primary negative
pool's rule-unflagged rows are explicitly **not** eligible to be promoted to "legitimate"
status, and no script in the repo attempts this. Any new collection effort should (a) reuse
`fetch_benign_7702_delegates.py`'s pattern (hardcoded, documented, project-attributed address
list) rather than auto-labeling unflagged rows, and (b) fetch bytecode **per chain** rather than
once per project, given the cross-chain non-identity found above.

---

## 10. Human-annotation platform readiness

**No web application, API, database, or review UI exists anywhere in the repository** —
confirmed by an exhaustive repo-wide search (including third-party bundled artifacts
`PhishingHook Zenodo artifact/`, `PTXPhish-main/`, `USENIX EIP-7702 artifact/`,
`scamsonethereum-main/`): zero `package.json` files anywhere; the only `main.py`/`app.py`/
`server.py` hits are third-party batch decompilation scripts, not HTTP servers; zero hits for
Flask/FastAPI/Django imports, `@app.route`, `sqlite3.connect`/`CREATE TABLE`, or any `.html`
template. The entire pipeline is Python scripts producing/consuming CSV and JSON.

### 10.1 What exists today: `revision_v2/artifact/label_audit/`

| File | Content |
|---|---|
| `evidence_packets.json` | 170-item JSON array; one flat dict per item: `anon_id, code_bytes, n_ops, n_call_family, has_delegatecall, has_sstore, n_selectors, has_sensitive_selector, is_delegation_pointer, opcode_prefix (first 40 mnemonics), model_risk_score`. No raw bytecode, chain, or address (blinded by design). |
| `review_form_R{1,2,3}_BLINDED.csv` | columns `anon_id,reviewer_id,label,confidence,rationale`, all blank |
| `reviewer_assignments.csv` | all 170 items assigned to all 3 reviewers (`R1;R2;R3`) |
| `sampling_manifest.json` | seed 7702, 7 sampling strata, score source = pooled G-DET v2 test scores |
| `REVIEWER_GUIDELINES.md` | label set `malicious / benign / uncertain`; confidence `high/medium/low`; explicit blinding instruction ("do not look up addresses, work independently") |
| `REVIEWER_KEY_do_not_distribute.csv` | unblinded mapping, deliberately excluded from any distributable artifact (asserted by `revision_v2/experiments/artifact/audit_anonymity.py`) |
| `agreement_results.json` | **`{"status": "pending_human_labels", "found": 0}`** — zero labels collected, confirmed literally |

Generators: `revision_v2/experiments/label_audit/build_audit_package.py` (builds the stratified
sample + evidence packets — bytecode-derived, so it reproduces the same circularity concern
noted in Sections 3-4). `agreement.py` (88 lines) implements Cohen's and Fleiss' kappa and
majority-vote adjudication — but **no dedicated third-reviewer tie-break workflow** beyond
simple majority of the same 3 raters.

### 10.2 Reusable technology already in the repo

`revision_v2/audits/requirements.txt` (actual pinned pipeline deps): pandas/numpy/scikit-learn/
xgboost/scipy/matplotlib/pycryptodome/openpyxl — **zero web framework**. `pip_freeze.txt` (full
snapshot) does list `fastapi`, `uvicorn`, `starlette`, `customtkinter` — but these are verified
**not installed** in `revision_v2/.venv` and **not imported anywhere** in the codebase; they are
unused transitive dependencies of an unrelated local package. **Net finding: this project has no
web framework in active use anywhere.**

### 10.3 Recommendation

Given zero existing web infrastructure, a single-audience internal tool (a handful of named
reviewers, roughly 170-500 items, no concurrent-traffic concerns), and a codebase that is 100%
pandas/CSV/JSON with the exact per-item schema and kappa math already written
(`agreement.py`), the fastest path is a **minimal single-process FastAPI + SQLite + server-
rendered templates (Jinja2 or plain HTML/vanilla JS) app** — no Node/npm toolchain (the repo has
zero trace of one), no React/Vue build step. FastAPI's pydantic validation is a fast way to
define the requested structured schema (SAFE/UNSAFE/INDETERMINATE/NOT-BYTECODE-SCREENABLE plus
confidence, justification, evidence links) with minimal code; SQLite (stdlib, zero ops burden)
replaces the current CSV-round-trip workflow with row-level locking so reviewers can annotate
concurrently without file-merge collisions, while remaining trivially exportable back to the
CSV/JSON schema the pipeline already expects. `evidence_packets.json` becomes seed data for a
one-time import script; `agreement.py`'s kappa functions can be lifted nearly verbatim into a
stats endpoint. This avoids Django's unneeded ORM/admin machinery for a small single-table
problem and avoids introducing the repo's first-ever JS build pipeline.

---

## 11. Environment and execution

Directly measured on the current host during this audit (not assumed):

| Item | Value |
|---|---|
| System Python | 3.12.12 (pyenv) |
| PyTorch | 2.9.0+cu128 |
| CUDA available | Yes |
| GPU | NVIDIA GeForce RTX 2080 SUPER |
| CPU | 12 logical cores |
| OS | Linux 7.0.0-28-generic (Ubuntu 24.04-based / Linux Mint), x86_64 |
| `revision_v2/.venv` Python | 3.13.8, pandas 3.0.3, xgboost, scikit-learn, openpyxl — **no torch** |

Two-environment split is intentional: `revision_v2/.venv` for pandas/xgboost/audit work, system
`python3` for all GPU-based AuthGuard-Seq/Fusion training (5-fold sequence training runs in
about 1 minute on this GPU per prior session measurement).

**Cross-platform note**: `revision_v2/audits/environment.json` (the environment snapshot
recorded when Revision v2 was originally executed) shows Python 3.13.9 on **macOS-26.5.1-arm64**
— i.e. the canonical v2 results were produced on Apple Silicon, not this Linux/CUDA host.
`revision_v2/audits/harness_validation_linux_x86.json` and `harness_validation_macos_arm.json`
both exist, indicating a deliberate cross-platform validation pass was already done; anyone
retraining on this GPU host should diff against those two files before trusting bitwise
reproducibility (the paper handoff docs already note the frozen GPU path is not bitwise
deterministic across runs — `FINAL_RESULTS_MANIFEST.md` §4).

**Dependency files**:
- `revision_v2/audits/requirements.txt` — pinned pipeline deps (numpy 2.3.4, pandas 3.0.3,
  scikit-learn 1.9.0, xgboost 3.3.0, scipy 1.18.0, matplotlib, pycryptodome, openpyxl). No
  `torch` pin here — the neural training stack's exact version is only recorded in
  `FINAL_RESULTS_MANIFEST.md` prose ("PyTorch 2.9.0+cu128").
- `revision_v2/audits/pip_freeze.txt` — full 118-line snapshot (includes unused transitive
  fastapi/uvicorn/customtkinter, see §10.2).
- **No `requirements.txt`/lockfile exists at the repo root.**

**Environment variables / credentials**: none found (no `.env` file, no key-reading code
anywhere). All RPC access is unauthenticated public endpoints (see §8).

**Required RPC/API services**: `eth.drpc.org` (primary, Ethereum-capable, no batching),
`ethereum-rpc.publicnode.com` (needs a browser User-Agent header or 403s — already worked
around in `fetch_benign_7702_delegates.py`), and per-chain endpoints in
`fetch_benign_7702_delegates.py`'s `RPCS` table for the other 6 chains (`eth_getCode` only).

**Approximate runtime of one training seed**: not independently re-measured in this audit
(explicitly out of scope — "do not rerun training"). From existing logs/docs: 5-fold
sequence-model training for one seed runs in about 1 minute on a CUDA GPU (prior session
measurement, consistent with the small 181,877-parameter model size and 2,190-row primary
corpus); `revision_v2/experiments/robustness_operational_v2/logs/` and
`revision_v2/logs/*.log` contain wall-clock timestamps for the actual v2 runs if a precise
figure is needed without any new execution.

---

## 12. Gap analysis

Legend for **existing support**: `NONE` / `PARTIAL` / `FULL`. Difficulty and compute cost are
relative, qualitative estimates for planning, not measured.

| Required task | Existing support | Missing components | Files to modify/add | Difficulty | Compute cost | Human involvement | Major risks |
|---|---|---|---|---|---|---|---|
| Provenance reconstruction | PARTIAL — everything downstream of `capability_dataset.csv` is scripted and hashed; the S0 construction script itself is absent | Write/recover the USENIX-artifact → `capability_dataset.csv` builder | new `revision_v2/audit/scripts/build_capability_dataset.py` | Medium | Low (I/O only) | None mandatory | Reconstructed script might not exactly reproduce 3,258 rows if upstream artifact versions drifted |
| Unique-bytecode census | FULL — this audit's `dataset_census.csv`/`project_inventory.json` cover it | none | — | — | — | — | Keep census script under version control so it's rerunnable, not just a one-off audit output |
| Family statistics | FULL — `family_assignment_frozen.csv`, `family_structure.json`, this audit's census | none for the frozen 0.85 threshold; sensitivity at 0.75/0.90 exists as columns but not rerun as G-DET arms on v2 | `revision_v2/results/family_sensitivity/` (exists from Phase 3C, verify it used v2 not v1 data) | Low | Low | None | Confirm Phase 3C ran on v2, not the superseded v1 dataset |
| Equal-budget ablation (§7) | PARTIAL — code path identified, not implemented | new inference-time capped-chunk condition in `create_variants` | `revision_v2/experiments/robustness_operational_v2/run_robustness_operational_v2.py` | Low | Low (inference-only, no retraining) | None | None — this is the highest-value, lowest-cost fix identified in this audit |
| Pooling ablation (mean/max/attention) | PARTIAL — code exists only on unmerged branch `revision-3` | merge/cherry-pick `long_context_ablation_v3` and `multiscale_confirmation_v1` | merge commit `a79a7ea` onto `main` (or cherry-pick), then `run_long_context_ablation_v3.py` | Low once merged | Low-Medium (several small retrains) | Decision: merge branch or cherry-pick | Branch `revision-3` may have diverged from `main` elsewhere — diff before merging |
| Sequence-length ablation (2,048/16,384/8,192) | PARTIAL — 2,048 and 16,384 exist on `revision-3`; 8,192 exists nowhere | add an 8,192 `ModelSpec`; merge branch as above | same file, +1 new config entry | Low | Medium (full retrains at each length) | None | None |
| Chunk-size ablation | PARTIAL — `run_authguard_fusion.py` has a CLI flag; `run_baseline_v2.py` (the canonical driver) hardcodes 256/64 | parametrize `run_baseline_v2.py`'s chunk args | `revision_v2/experiments/baseline_v2/run_baseline_v2.py` | Low | Medium (full retrains) | None | Must not silently overwrite the frozen `baseline_v2` outputs — write to a new experiment dir |
| Evidence-packet generation | FULL — `build_audit_package.py` exists and works | richer evidence (raw disassembly, explorer links) if reviewers need more than derived stats | `revision_v2/experiments/label_audit/build_audit_package.py` | Low | Low | Decision on evidence richness vs. blinding | Adding raw bytecode to packets could deanonymize via unique identifiers |
| Annotation webpage | NONE | full build: schema, backend, DB, UI (see §10.3) | new `revision_v2/annotation_app/` (proposed) | Medium | Low (no ML compute) | Design/UX decisions | Scope creep; keep to the 170-item (or expanded) package's existing schema needs |
| Gold-Dev construction | NONE | requires annotation platform + ≥2 reviewers + adjudication rule | depends on above | Medium | Low | 2+ human reviewers, ongoing | Small n limits statistical power; must not leak into Gold-Test |
| Locked Gold-Test construction | NONE | same as above, plus a hard freeze/hash-lock mechanism (pattern already exists: `frozen.py`) | new protocol doc + extend `frozen.py`'s `FROZEN_FILES` | Medium | Low | Same reviewers, distinct item pool from Gold-Dev | Must be drawn before any model sees it, and never touched afterward |
| Temporal collection | NONE (see §8) | date→block resolver, authorization-list scanner, per-chain rate-limit handling | new `revision_v2/temporal/` module | High | Medium-High (multi-day scans per chain on free RPC) | Decide RPC budget/credentials | Free-tier RPC instability (429/408/500 errors observed on 5/6 chains already) |
| Legitimate external controls (expansion) | PARTIAL (see §9) | per-chain bytecode capture for the 3 non-identical projects; broader registry scan (manual, by design) | `fetch_benign_7702_delegates.py` (extend `SEED_DELEGATES` + per-chain fetch) | Low | Low | Curation/verification of new candidates | Must not auto-promote unflagged primary-negative rows to "legitimate" (explicitly banned by `LABEL_CLAIM_CONTRACT.md`) |
| Label-noise-aware training | NONE | choose/implement a noise-robust loss or label-smoothing approach appropriate to rule-defined weak negatives | new training variant in `run_baseline_v2.py`-style driver | Medium | Low-Medium | Scientific judgment on noise model assumptions | Risk of conflating rule-noise with genuine model error; needs a clear noise model before implementation |
| Positive-unlabeled learning | NONE | PU-learning framing is a natural fit given "unflagged ≠ verified benign," but no PU estimator exists in the codebase | new experiment dir, e.g. `revision_v2/experiments/pu_learning_v1/` | Medium-High | Medium | Scientific judgment on class-prior estimation | Class-prior misestimation could produce misleading corrected metrics |
| Structural-feature hybrid model | PARTIAL — the 261-d dense/structural feature block and n-gram baselines already exist and are combinable (`dense_only`, `ngram_only`, `hist_ngram_xgb`) | a true hybrid *architecture* combining AuthGuard-Seq's sequence view with structural features is literally what `AuthGuardFusion`'s dense+sequence views already do — just needs `active_views=(True,False,True)` or similar, evaluated as a new named baseline | `revision_v2/experiments/baseline_v2/run_baseline_v2.py` (add a config) | Low | Low-Medium | None | The dead-parameter caveat from §5.1 applies — verify which views are actually active in gradient flow |
| Matched-budget robustness | Same as equal-budget ablation above | — | — | Low | Low | — | — |
| ONNX/WASM deployment | NONE | export path from PyTorch model to ONNX; WASM runtime integration | new `revision_v2/deploy/` module | Medium | Low | None mandatory | Custom ops (chunked attention pooling) must be verified ONNX-exportable; latency claims would need re-measurement in the new runtime |
| Reproducibility package | PARTIAL — extensive hashing/provenance already exists (`frozen_ledger.json`, `task_aligned_result_provenance.md`); Phase 6A (`P6A-ARTIFACT`) in the master execution plan targets this directly and may already be substantially done given `revision_v2/results/` is populated | root-level `requirements.txt`; licensing decision for corpus redistribution; verify `revision_v2/artifact/` (if it exists beyond `label_audit/`) contains a full fresh-environment reproduction path | `revision_v2/artifact/`, root `requirements.txt` | Medium | Low | Licensing decision (human) | Third-party USENIX/PhishingHook data redistribution rights are unresolved |

---

## 13. Recommended implementation order

Grouped by delegability, parallelism, and dependency — not a fixed calendar, since the audit
brief asks for prioritization logic rather than a schedule.

### 13.1 Fully delegable to the AI coder (no new data, no human judgment call)
1. **Equal-input-budget robustness variant** (§7, §12) — highest value-to-cost ratio found in
   this audit: a few lines in `run_robustness_operational_v2.py`, inference-only, directly
   addresses a reviewer-defensibility gap in the current F200 headline claim.
2. **Merge/cherry-pick `revision-3`'s ablation code** (`long_context_ablation_v3`,
   `multiscale_confirmation_v1`) onto `main`, then run the pooling and 2,048-vs-16,384
   sequence-length ablations it already implements.
3. **Add an 8,192-token config** to the merged ablation harness.
4. **Parametrize chunk size** in `run_baseline_v2.py` (write to a new experiment directory, never
   overwrite `baseline_v2/`'s frozen outputs).
5. **Structural-feature hybrid baseline** — a new `AuthGuardFusion` config combining sequence +
   dense views, evaluated under the existing `baseline_v2` protocol.
6. **Root-level `requirements.txt`** consolidating `revision_v2/audits/requirements.txt` +
   the torch version actually used.

### 13.2 Requires human scientific judgment before implementation
1. **Label taxonomy decision** (SAFE/UNSAFE/INDETERMINATE/NOT-BYTECODE-SCREENABLE vs. the
   existing malicious/benign/uncertain) — must be settled before building the annotation
   platform, not after.
2. **Gold-Dev / Gold-Test construction protocol** — stratification rules, adjudication
   tie-break design, and the hard-freeze point all need a human decision, mirroring the care
   already shown in `donor_isolation_protocol.md` and `gateA_success_criteria.md`.
3. **Noise model for label-noise-aware training / PU-learning class-prior** — these are
   statistically consequential choices, not implementation details.
4. **RPC budget/credentials decision** for temporal collection — determines whether the Feb–Jun
   2026 window is even reachable in the available time.
5. **Corpus redistribution licensing decision** (blocks a truly public reproducibility package).

### 13.3 Parallelizable
- §13.1 items 1–4 (ablations) have no data dependency on each other and can run concurrently
  once the branch merge is done.
- Annotation-platform *build* (schema + FastAPI/SQLite app) can proceed in parallel with the
  ablation work — it depends only on the taxonomy decision (13.2.1), not on any model result.
- Legitimate-control expansion (per-chain bytecode capture for the 3 non-identical projects) is
  fully independent of everything else.

### 13.4 Blocked by missing data
- Temporal population isolation (§8) is blocked until the date→block resolver and
  authorization-list scanner are built — nothing else in the plan depends on it, so it should
  not gate other work, but it cannot itself start without that infrastructure.
- Gold-Dev/Gold-Test-based re-evaluation of AuthGuard-Seq is blocked until the annotation
  platform produces adjudicated labels.

### 13.5 Sequencing constraints (must not start before an earlier result is known)
- Do not build the full annotation *platform* before the taxonomy decision (13.2.1) — the label
  schema is a foundational field in every downstream table (DB schema, export format, kappa
  computation).
- Do not attempt PU-learning or label-noise-aware training before the human-adjudicated
  Gold-Dev exists — without it there is no independent signal to validate whether a noise
  correction actually helped versus just changing the fit to the same rule-based labels.
- Do not finalize ONNX/WASM latency claims before deciding whether the structural-feature hybrid
  model (13.1.5) becomes the new deployment candidate — exporting and re-measuring twice is
  wasted effort.
- The reviewer-defensible priority order, given everything above: **(1) equal-budget robustness
  fix → (2) merge ablation branch + run sequence/pooling/chunk ablations → (3) taxonomy decision
  → (4) build annotation platform → (5) Gold-Dev/Gold-Test → (6) label-noise-aware / PU-learning
  retraining → (7) temporal collection and legitimate-control expansion (parallel, independent)
  → (8) ONNX/WASM deployment and final reproducibility packaging.** This ordering keeps
  AuthGuard-Seq's existing strong result intact and cheaply defensible (steps 1–2) before
  spending the much more expensive human-annotation effort (steps 3–6) that could change what
  "strong" even means once better labels exist.

---

## Immediate decisions needed

1. **Merge or cherry-pick branch `revision-3` into `main`?** The sequence-length/pooling
   ablation code (`long_context_ablation_v3`, `multiscale_confirmation_v1`) and the legitimate-
   registry overlap audit both exist only there. Without this decision, §12's cheapest,
   highest-value ablations cannot start.
2. **Is the F200 robustness headline (0.920 vs. 0.535 AUPRC) acceptable to report with the
   input-budget asymmetry disclosed, or must the equal-budget experiment (§7, §12) run first and
   replace/supplement it?** This affects any near-term paper or report claim about robustness.
3. **What label taxonomy governs the next annotation effort** — the existing
   malicious/benign/uncertain scheme (already built, zero labels collected) or the
   SAFE/UNSAFE/INDETERMINATE/NOT-BYTECODE-SCREENABLE scheme named in the brief? This decision
   is a hard prerequisite for building the annotation platform and cannot be deferred past that
   point.
4. **What is the RPC/credential budget for temporal collection?** Free-tier public RPC alone
   makes a full Feb–Jun 2026 authorization-list scan across 7 chains a multi-week effort with
   no batching and observed instability on 5/6 non-Ethereum chains; a credentialed
   indexer/archive-node service would change the feasibility timeline substantially.
5. **What is the licensing/redistribution status of the USENIX-artifact-derived bytecode
   corpus and the PhishingHook dataset?** This blocks whether a public reproducibility artifact
   (§12, Phase 6A in the existing master execution plan) can include the corpus itself or only
   reconstruction instructions and hashes.
