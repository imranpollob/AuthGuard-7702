# HIGH_VALUE_CHANGES — material benchmark changes in revision v2

Only changes that materially affect the paper's credibility are listed. Everything
else found by the audit was either already sound (and is now *documented* rather than
changed) or cosmetic.

## 1. Repaired 90 corrupted negative observations (data validity)

- **What:** 89 `benign_cleared` bytecodes were truncated at exactly 32,767 hex chars
  (Excel cell cap — the source artifact's `.hex` files carry the same truncation) and
  1 row stored an HTTP timeout error string as its "bytecode". All 90 true runtimes
  were refetched read-only and **prefix-verified** (89/89 strict extensions of the
  stored prefix; 7 turned out byte-identical to curated legitimate AA
  implementations, independently confirming the repair).
- **Why necessary:** corrupted inputs sat in the training/evaluation corpus as
  negatives; 89 of them formed the extreme length tail of the negative class — a
  potential artifact lever the model could exploit, and a reviewer-visible defect.
- **Where:** `repair_rpc_cache.json`, `truncation_repair.csv`, benchmark columns
  `bytecode_repaired`, `data_quality_flag`.

## 2. Moved the 90 repaired rows out of PRIMARY_EVALUATION (label validity)

Their source-rule verdict ("unflagged") was computed on truncated or absent code, so
the label is not established for the true runtime. They stay in the file as
population `EXCLUDED_UNCERTAIN_INPUT` with repaired bytecode. Primary task:
2,280 → **2,190 rows (727 positives / 1,463 negatives)**. All fold/family invariants
still pass; signal verified to survive (`revision_v2_signal_check.md`).

## 3. Reframed label semantics; added evidence-strength metadata (construct validity)

The audit established that **every** primary label is a deterministic function of the
runtime bytecode via the source study's Gigahorse rule (727/727 positives = rule
fired; 0/1,553 negatives; the repository holds independent malicious evidence for
exactly 1 positive). The benchmark therefore now states what it measures:
**source-identified risk screening** (analyzer-surrogate), not independent malware
detection. New columns: `label_semantics`, `label_source`, `label_evidence_type`,
`label_strength` (A_curated_legitimate / B_external_benign_label /
C_source_rule_only / C_source_unflagged_weak / D_source_verdict_on_corrupted_input).
Binding terminology and claim boundaries: `LABEL_CLAIM_CONTRACT.md`.

## 4. Hard population separation with machine-readable tags (task validity)

`population ∈ {PRIMARY_EVALUATION, EXTERNAL_BENIGN_CONTROL, QUALITATIVE_CONTROL,
EXCLUDED_UNCERTAIN_INPUT}`. Justified empirically: `chain` alone identifies the
external control with AUPRC/AUROC 1.000 (`shortcut_diagnostics.csv`) — mixing it into
the primary task would manufacture separability. (The prior design already kept it
secondary; v2 makes the separation an explicit, enforceable field.)

## 5. Flagged (kept) 13 negatives with external contradiction evidence

4 USENIX-`matched`, 1 scamsonethereum-blacklisted, 8 whose bytecode hash appears in
PhishingHook's *phishing* set. Removal is not justified by the weak evidence;
flags (`flag_*` columns, `negative_flags.csv`) make them auditable and excludable in
sensitivity analyses.

## What was deliberately NOT changed

- Folds, families, and the frozen task-alignment quarantine — audited, all leakage
  assertions pass; no regeneration needed.
- No positives were removed or re-tiered: an "independently evidenced" positive tier
  cannot be built from existing data (n=1) and inventing one would fabricate
  evidence.
- No rebalancing/resampling: shortcut diagnostics show no within-task acquisition
  shortcut (trivial-feature AUROC ≤ 0.62), so the real task distribution is kept.
