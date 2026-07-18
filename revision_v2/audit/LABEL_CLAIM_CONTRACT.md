# LABEL_CLAIM_CONTRACT — AuthGuardBench-7702

The binding statement of what the benchmark's labels mean, what the revised paper may
claim, and what it must not claim. Every statement below is backed by programmatic
evidence in `revision_v2/audit/` (scripts under `revision_v2/audit/scripts/`).

## 1. Exact definition of y = 1 (727 rows)

> **y = 1 ⇔ the contract is an observed EIP-7702 delegate whose runtime bytecode was
> flagged by the source study's static rule.**

Precisely: the `(chain, address)` pair appears in
`USENIX EIP-7702 artifact/eoa_detect/detect_result.jsonl` (793 keys), i.e. the source
study's Gigahorse/Soufflé pipeline decompiled the delegate's runtime bytecode and its
Datalog rule — *"an external call statement is reachable from `receive()` or
`fallback()`"* (high-confidence variant) — fired. 727 of the 793 survive the frozen
task-alignment quarantine (66 removed as members of exact-bytecode groups carrying
conflicting class labels). Verified: 727/727 retained positives have a
`detect_result.jsonl` row; 0/1,553 retained primary negatives do
(`dataset_statistics_original.json → label_rule_identity`).

There is **no per-row transaction, victim, loss, or blocklist evidence** for any
positive in the repository. Exactly **1** of the 727 positives has independent
behavioral corroboration (victim-account convergence and sweep analysis in
`independent_malicious.csv`, `flag_independent_behavioral_evidence`).

## 2. Exact definition of y = 0 (primary task, 1,463 rows in v2)

> **y = 0 ⇔ the contract is an observed EIP-7702 delegate from the same source pool
> whose runtime bytecode did NOT trigger the source rule.**

Precisely: the pair appears in the source candidate pool
(`eoa_detect/get_code/contracts_with_bytecode.xlsx`, 2,685 observed delegates), is not
in `detect_result.jsonl`, and had non-empty fetched bytecode (2,685 − 793 − 235 empty
= 1,657). After frozen task alignment (−73 designator rows, −31 conflict rows → 1,553)
and the v2 correction (−90 rows whose source verdict was computed on truncated or
failed fetches → 1,463). These are **rule-silent weak negatives**: no one ever
verified they are benign.

Non-primary negatives (controls, never mixed into the primary metric):
- `benign_general` (797) — PhishingHook benign-labeled **general Ethereum contracts**;
  not EIP-7702 delegates; external control only.
- `benign_AA` (5) — curated legitimate delegate implementations; qualitative control.

## 3. Positive / negative evidence sources

| class | evidence | independence from model input |
|---|---|---|
| y=1 | source static rule over decompiled runtime bytecode | **DERIVED_OVERLAP** — deterministic function of the exact bytes the model sees |
| y=1 (n=1) | behavioral victim-convergence analysis | INDEPENDENT |
| y=0 primary | absence of a source-rule hit | same DERIVED_OVERLAP, by complement |
| benign_general | PhishingHook dataset label | INDEPENDENT (different population) |
| benign_AA | project documentation | INDEPENDENT (n=5) |

## 4. Label uncertainty

- Positives: the rule is a **capability/reachability heuristic**, not proof of intent
  or of an attack. False positives (legitimate forwarders with fallback call-out) are
  plausible and unquantified. The source study's own external cross-reference column
  (`sa_contract_malicious.xlsx: matched`) covers all 793 positives **plus 13 retained
  unflagged rows**, but its semantics are undocumented (classification: UNKNOWN).
- Negatives: rule silence only. 13 retained negatives carry external contradiction
  flags (USENIX `matched`, scamsonethereum blacklist, or a bytecode hash that appears
  in PhishingHook's *phishing* set) — kept and flagged, not removed
  (`negative_flags.csv`).
- 90 former negatives had their source verdict computed on corrupted input (89
  Excel-truncated at 32,767 chars, 1 stored HTTP-error string). Their true runtime was
  recovered and verified, but their "unflagged" status cannot be trusted →
  `EXCLUDED_UNCERTAIN_INPUT`.
- A human adjudication package (170 items) exists at
  `revision_v2/artifact/label_audit/` and remains **pending**; no human labels were
  fabricated.

## 5. Circularity assessment

**Circularity exists and is structural (Decision rule CASE C).** The positive label is
a deterministic function of the same runtime bytecode the model receives; no
information outside the bytecode contributes to any primary label. Therefore:

- The benchmark **cannot** support "detects malicious contracts" as an independent
  ground-truth claim.
- What the model learns is an **approximation of the source analyzer's decision
  boundary** from raw bytecode, without decompilation. That is a legitimate and
  useful task — a fast pre-authorization *surrogate/screening* stage for a
  heavyweight declarative analyzer — and it is exactly how the tool is positioned.
- Mitigation applied: transparent reframing + evidence-strength fields
  (`label_strength`, `label_source`, `label_evidence_type`) rather than data
  destruction. A strong independent-evidence tier **cannot** be constructed from
  repository data (n=1 corroborated positive); this is documented, not invented.

## 6. Source-shortcut assessment

`shortcut_diagnostics.csv` (family-disjoint folds, AUPRC / ROC-AUC, prevalence 0.33):

- Within the primary task, trivial acquisition features are weak: best single feature
  is family size (AUPRC 0.52, AUROC 0.62); all-trivial-combined ≤ 0.51 / 0.62;
  bytecode length alone 0.40 / 0.55. The learned models' 0.83–0.92 AUPRC is **not**
  explained by trivial provenance artifacts.
- Between populations, `chain` alone identifies the external benign control with
  AUPRC/AUROC = 1.000 — mixing `benign_general` into the primary task would
  manufacture separability. It is kept as an external control (and `chain` remains a
  banned feature).

## 7. Leakage assessment

`split_invariant_audit.json` — all assertions **PASS** on both the original and v2
benchmarks: `NO_FAMILY_CROSS_FOLD`, `NO_EXACT_BYTECODE_CROSS_FOLD`,
`NO_CONFLICTING_EXACT_BYTECODE_LABEL` (primary and secondary tasks), and
`NO_TRANSFORMATION_DONOR_LEAKAGE` (audited from the 78,514-row donor ledger).

## 8. Final recommended terminology

| term | verdict | use instead / condition |
|---|---|---|
| positive class | — | **"source-flagged delegates"** (or "analyzer-flagged risky delegates") |
| negative class | — | **"source-unflagged delegates (weak negatives)"** |
| task name | — | **"bytecode-only pre-authorization screening for source-identified EIP-7702 delegate risk"** (short: *source-identified risk screening*) |
| "malicious delegate" | ❌ not justified as ground truth | only when explicitly citing the source study's label, e.g. "delegates the source study labels malicious" |
| "benign delegate" | ❌ for `benign_cleared` | "unflagged delegate"; "benign" acceptable only for the curated AA control with the qualifier "curated" |
| "risk screening" | ✅ with qualifier | "source-identified risk screening" |
| "detection" | ⚠️ discouraged | "screening"/"flagging"; if used: "detection of analyzer-flagged risk" |
| "ground truth" | ❌ | "source labels" / "reference labels" |

## 9. Claims the revised paper MAY make

1. Bytecode-only models reproduce a heavyweight decompiler-based analyzer's verdict on
   observed EIP-7702 delegates with AUPRC ≈ 0.92 under family-disjoint evaluation,
   without decompilation — supporting a fast pre-authorization screening stage.
2. The primary positive and negative classes come from the **same acquisition
   pipeline and population** (observed delegates, same fetch pass, same analysis
   pass); label-class separation is not an artifact of dataset source (shortcut
   AUROC ≤ 0.62).
3. The evaluation is dependence-aware: frozen families, no exact-bytecode or family
   cross-fold leakage, donor-isolated transformations, validation-derived thresholds.
4. The corrected benchmark repairs 90 corrupted negative observations (verified
   prefix-preserving refetch) and the signal survives the correction
   (`revision_v2_signal_check.md`).
5. Honest limitation statements: labels are analyzer-derived; independent
   malicious ground truth exists for 1 positive; negatives are rule-silent only.

## 10. Claims the revised paper must NOT make

1. "Detects malicious/attack contracts" as if maliciousness were independently
   established (it is established for exactly 1 of 727 positives).
2. "Benign" for the rule-silent negatives, or any false-positive-rate claim phrased
   against "benign delegates" (the FPR is against *unflagged* delegates).
3. Novel-family / zero-day discovery claims: performance is measured against the
   source analyzer's own decision function.
4. Any claim of superiority to (or speed advantage over) the Gigahorse pipeline
   itself — the analyzer was never executed here (see `results/gigahorse/`).
5. "Ground truth", "verified", "confirmed" for any label except `benign_AA`
   (curation) and the single behaviorally corroborated positive.
