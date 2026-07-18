# AuthGuardBench-7702 — Dataset Audit Report (Revision v2)

Audit date: 2026-07-18. All figures produced by scripts in
`revision_v2/audit/scripts/` from repository artifacts; nothing in this report is
estimated or manually labeled. Frozen originals were not modified.

Scripts: `explore_provenance.py` (provenance joins), `audit_dataset.py` (statistics,
invariants, comparability), `repair_truncated.py` (bytecode repair),
`build_benchmark_v2.py` (corrected benchmark), `shortcut_diagnostics.py`,
`run_sanity_v2.py` (signal check).

---

## Part 1 — Label provenance (fully reconstructed and verified)

Paper counts verified exactly: **3,082 rows = 727 malicious + 1,553 benign_cleared +
797 benign_general + 5 benign_AA** in
`paper_build/data_hygiene/task_aligned_dataset_v1.csv` (SHA-256 recorded in
`task_alignment_protocol.md`), derived from the 3,258-row `capability_dataset.csv`.

### Lineage per subset (details in `dataset_provenance.csv`)

**malicious (793 → 727).** Source: USENIX EIP-7702 artifact, `eoa_detect` pipeline.
The source study enumerated **2,685 observed EIP-7702 delegate addresses** across 7
chains (`analysis_information/sa_contract.xlsx`), fetched their runtime bytecode
(`eoa_detect/get_code/contracts_with_bytecode.xlsx`), decompiled each with
Gigahorse/Soufflé, and flagged 793 whose decompiled code has an external call
reachable from `receive()`/`fallback()` (`detect_result.jsonl`; the shipped rule
output whose 866 tuples all have `enclosingFuncSig ∈ {receive(), fallback()}`).
Join verified: 793/793 detected keys ⊂ candidate pool; 727/727 retained positives
have a rule hit. 66 rows removed by the frozen conflict quarantine.

**benign_cleared (1,657 → 1,553).** The complement inside the same pool:
2,685 − 793 detected − 235 empty-bytecode fetches = **1,657 exactly** (verified).
Task alignment removed 104 (73 designator rows, 31 conflict rows). These are
*rule-silent* delegates — no benignity verification of any kind exists.

**benign_general (800 → 797).** Verified by exact bytecode-hash join: **800/800**
sampled from PhishingHook's 3,542 deduplicated benign bytecodes (Ethereum-only;
`chain="ethereum(implied)"`). General contracts, **not** EIP-7702 delegates.

**benign_AA (8 → 5).** Curated legitimate delegate implementations fetched by
`fetch_benign_7702_delegates.py` (MetaMask delegation framework et al.); all 8
hash-match `benign_7702_bytecode.csv`; 3 dropped in task alignment.

### Designator handling
The original corpus contained 76 bare `ef0100||address` EIP-7702 delegation
designators (all on the negative side). The frozen task-alignment protocol resolved
them before modeling: 3 replaced by verified target runtime, 73 excluded. The
task-aligned manifest contains **0 designator rows** (verified).

### Minor anomaly (documented, not material)
Two `benign_AA` addresses also occur as `benign_cleared` rows with different letter
case (`ethereum:0xd6CEDDe…`/`0xd6cedde…`, `0x69007702…`). Same label (0), so no
label conflict; the cleared copies are truncated observations of the same deployments
and are among the 90 v2-excluded rows. v2 keeps original case in `sample_id`;
consumers should compare addresses case-insensitively.

---

## Part 2 — Source-detector circularity (the central finding)

Complete signal inventory of the source label pipeline, with overlap classification
(`circularity_signals.csv`):

| source signal | role | classification |
|---|---|---|
| Gigahorse decompiled reachability rule (fallback/receive → external call) | **defines all positives** | **DERIVED_OVERLAP** |
| sensitive-function-name lexical rule (`sweep/drain/attack/…`) | auxiliary output (58/793 positives) | DERIVED_OVERLAP |
| observed 7702 delegation (pool membership) | defines the candidate pool for **both** primary classes | INDEPENDENT (label-neutral) |
| `matched` column, `sa_contract_malicious.xlsx` (826 rows; ⊇ all 793 positives + 13 retained negatives) | undocumented | UNKNOWN |
| transaction / victim / attack-tx evidence | **absent from artifact** (ethics-scrubbed) | — |
| scamsonethereum blacklists; PhishingHook phishing set | not used by source; audit cross-reference | INDEPENDENT (0/727 positives hit) |

**Conclusion: yes — the model is learning to reproduce the source detector.** The
positive label is a deterministic function of the runtime bytecode the model
receives. No repair can add independent evidence that does not exist; the defensible
fix is reframing (source-identified risk screening / analyzer surrogate) plus
evidence-strength metadata, implemented in v2. This matches the tool's actual
positioning (fast screening stage ahead of the heavyweight analyzer). Note the model
does *not* trivially reproduce the rule (AUPRC 0.92, not 1.0): the rule involves
decompiled control-flow reachability that is genuinely hard to recover from raw
bytes, which is what makes the surrogate task non-degenerate.

Corrective actions considered and the choice made: excluding rule-defined positives
would delete the entire positive class; a strong-evidence tier is impossible (n=1
corroborated positive). Chosen: **CASE C reframing + tier fields + honest claims**,
preserving all data.

---

## Part 3 — Dataset-source shortcut diagnostics

`shortcut_diagnostics.csv`; family-disjoint stored folds; logistic + XGBoost on
trivial features only (never opcode content). Primary task prevalence 0.32–0.33.

| features | original primary AUPRC/AUROC (best of 2 models) | v2 primary |
|---|---|---|
| bytecode length | 0.37 / 0.55 | 0.40 / 0.55 |
| opcode count | 0.42 / 0.60 | 0.42 / 0.58 |
| CBOR metadata presence | 0.35 / 0.55 | 0.35 / 0.53 |
| duplicate-group size | 0.35 / 0.52 | 0.36 / 0.52 |
| family size | 0.51 / 0.62 | 0.52 / 0.62 |
| chain (one-hot) | 0.33 / 0.51 | 0.35 / 0.52 |
| all trivial combined | 0.50 / 0.62 | 0.51 / 0.60 |

**No strong within-task shortcut.** The gap to the learned models (0.83–0.92) is
carried by opcode content, not acquisition metadata. (Family size is mildly
informative — malicious families are larger, median 9 vs 4 rows — an honest property
of attacker redeployment, reported as such.)

**Population-identification control:** `chain` alone separates
`benign_general` from primary negatives with AUPRC/AUROC = **1.000** (all trivial
features w/o chain: 0.69/0.77). Any design mixing the external control into primary
classification would be invalid; the benchmark keeps it separated and `chain` stays
a banned feature (per `DECISIONS.md` D4, confirmed).

---

## Part 4 — Duplicates, families, split leakage

Original task-aligned manifest (`dataset_statistics_original.json`): 3,082 rows;
3,080 unique chain:address keys (see anomaly above); 2,820 unique addresses; 2,528
unique bytecodes; 233 exact-duplicate groups covering 787 rows; **0 cross-label
exact-bytecode conflicts** (down from 23 hash groups / 103 rows in the pre-alignment
corpus, all quarantined); 174 bytecodes at multiple addresses; 175 across chains;
1,258 frozen families (856 singletons, max size 58); 28 cross-class similarity
families (similarity, not identity — retained by design, cannot cross folds).

Assertions (`split_invariant_audit.json`) — original and v2, primary and secondary:

| assertion | original | v2 |
|---|---|---|
| NO_FAMILY_CROSS_FOLD | PASS | PASS |
| NO_EXACT_BYTECODE_CROSS_FOLD | PASS | PASS |
| NO_CONFLICTING_EXACT_BYTECODE_LABEL | PASS | PASS |
| NO_TRANSFORMATION_DONOR_LEAKAGE (78,514 ledger rows: segment-hash, donor-family, donor-vs-foreign-recipient-family) | PASS | PASS (same protocol) |

No split regeneration was required (decision rule CASE E not triggered).

---

## Part 5 — Population comparability

Primary positives vs primary negatives (`population_comparability.json`):
**same source, same acquisition pipeline, same analysis pass, all observed EIP-7702
delegates.** Code-size medians nearly identical (2,701 vs 2,727 bytes; KS stat 0.155).
Chain mix differs significantly but modestly (χ² p = 1.7e-4; e.g. bnb 28% of
negatives vs 24% of positives). CBOR metadata: 98% of positives vs 87% of negatives.
Family size: malicious median 9 vs 4. The task-aligned primary pairing is the most
source-comparable construction available; no better negative pool exists in the
repository. `benign_general` differs on everything (single implied chain, median
4,967 bytes, non-delegates) → external control only. **CASE D does not apply to the
primary task; it already applies to the controls and they are already separated.**

---

## Part 6 — Data-quality corrections discovered and applied (v2)

1. **89 Excel-truncated negatives.** All `benign_cleared` bytecodes of length exactly
   32,767 hex chars (the Excel cell cap; 89/89 also truncated in the artifact's own
   `.hex` zip — repair from the artifact is impossible). Repaired by read-only
   `eth_getCode` refetch with **prefix verification**: 89/89 fetched runtimes are
   strict extensions of the stored truncated prefix (`truncation_repair.csv`,
   cache `repair_rpc_cache.json`). 7 repaired rows turn out byte-identical to curated
   `benign_AA` implementations — independent confirmation the repair recovered true
   runtime.
2. **1 fetch-error row.** `base:0x2521ab07…` stored the literal string
   `error: HTTPSConnectionPool(… Read timed out …)` as its bytecode (already present
   in the source artifact). True runtime (2,692 bytes) refetched.
3. **Verdict-on-corrupted-input exclusion.** For all 90 repaired rows the source
   pipeline's rule verdict was produced on truncated/absent code, so their
   "unflagged" label is not established for the true runtime → population
   `EXCLUDED_UNCERTAIN_INPUT`, `label_strength=D_source_verdict_on_corrupted_input`.
   They remain in the file with repaired bytecode for future use.
4. **13 negative contradiction flags** (kept, flagged): 4 USENIX-`matched`, 1
   external blacklist, 8 PhishingHook-phishing bytecode (7 of them in the external
   control, which PhishingHook itself labels inconsistently).

---

## Part 7 — The corrected benchmark

`revision_v2/data/authguardbench_7702_v2.csv.gz` — 3,082 rows, 28 columns including
`label_semantics`, `label_source`, `label_evidence_type`, `label_strength`,
`population`, `is_eip7702_delegate`, duplicate/family/fold fields, and per-row flags.
Populations: **PRIMARY_EVALUATION 2,190** (727 pos / 1,463 neg, 790 families, folds
preserved), EXTERNAL_BENIGN_CONTROL 797, QUALITATIVE_CONTROL 5,
EXCLUDED_UNCERTAIN_INPUT 90. Construction ledger with per-step counts:
`dataset_construction_ledger.csv`. Statistics:
`dataset_statistics_revision_v2.json`. All invariants pass.

Label-strength tiers actually supported by evidence (no fabricated tiers):
`C_source_rule_only` (727 positives; 1 carries
`flag_independent_behavioral_evidence`), `C_source_unflagged_weak` (1,463),
`A_curated_legitimate` (5), `B_external_benign_label` (797),
`D_source_verdict_on_corrupted_input` (90, excluded).

---

## Part 8 — Signal sanity check

See `revision_v2_signal_check.md`. Headline: AuthGuard-Seq family-disjoint AUPRC
**0.918 (original) → 0.920 (v2)**, hist+4-gram XGBoost 0.841 → 0.828 (seed 7702,
5 folds, identical protocol). The research signal survives the correction; the model
advantage over the strongest traditional baseline persists (+0.09 AUPRC).

---

## Residual limitations (cannot be fixed with existing data)

- Independent malicious ground truth: n=1 positive. Human adjudication package
  (`revision_v2/artifact/label_audit/`, 170 items) pending.
- The `matched` column's semantics are unrecoverable from the artifact (UNKNOWN).
- Whether the source pipeline decompiled full or truncated bytecode for the 89
  truncated rows is unknowable from the artifact; v2 excludes them from primary.
- `benign_AA` control has n=5 — qualitative only.
