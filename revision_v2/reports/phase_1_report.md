# Phase 1 Report — Claim and Protocol Integrity

## Objectives

Correct unsupported claims, repair G-DET/G-MUT/G-VOL threshold transfer, isolate flooding
donors in G-ADV, add the compound M3+F200 condition, and quantify primary uncertainty with
family-clustered inference.

## 1A — Claim audit

`revision_v2/audits/claim_corrections.md` identifies eight manuscript correction groups.
Production-readiness, wallet-integration, unmeasured reference-analyzer cost, and general
robustness language is unsupported and removed at Phase 6 integration. The frozen manuscript
under `paper_build/` remains unchanged.

## 1B — Corrected threshold transfer

G-DET, G-MUT, and G-VOL now choose maximum-F1 thresholds from family-grouped inner OOF
predictions within each outer-training population, refit on the full outer train, and evaluate
the outer test once. AuthGuard G-DET remains 0.881 +/- 0.028 AUPRC (threshold-free), while the
corrected operating point is F1 0.782, precision 0.794, recall 0.808, and FPR 0.101. The old
in-sample thresholds were conservative rather than optimistic: recall rose from 0.576 to 0.808
and precision fell from 0.869 to 0.794.

The family-grouped pooled AuthGuard AUPRC is 0.867 with 95% CI [0.804, 0.922]. AuthGuard minus
opcode-histogram XGBoost is +0.091 [0.042, 0.147]; random minus family-grouped AuthGuard is
+0.107 [0.051, 0.171]. Both paired intervals exclude zero.

Under donor-isolated G-MUT, AuthGuard recall changes from 0.808 at M0 to 0.770 at M3. Under
donor-isolated G-VOL it falls from 0.816 at +0% to 0.379 at +200%; opcode-histogram XGBoost
falls from 0.809 to 0.423. The retained v1-donor diagnostic is confounded in both directions:
opcode XGBoost rises to 0.826 at +200%, demonstrating donor-signature sensitivity rather than
general flooding robustness.

## 1C — Donor-isolated G-ADV v2

All five outer folds completed. The primary arm preserves the original clean validation-fold
threshold design; the sensitivity arm uses inner family-grouped OOF thresholds. Training,
validation, and test donor families are partition-isolated. Every fold passed source/family,
bytecode-hash, and donor-pool assertions. The provenance ledger contains 103,250 copied donor
segments.

Primary validation-threshold fold means for AuthGuard-M0 versus AuthGuard-aug are:

| Condition | AUPRC M0 -> aug | Recall M0 -> aug | FPR M0 -> aug |
|---|---:|---:|---:|
| M0 | 0.814 -> 0.867 | 0.717 -> 0.850 | 0.127 -> 0.197 |
| M3 | 0.771 -> 0.822 | 0.678 -> 0.799 | 0.139 -> 0.234 |
| F200 | 0.550 -> 0.675 | 0.349 -> 0.659 | 0.124 -> 0.279 |
| M3+F200 | 0.563 -> 0.671 | 0.343 -> 0.626 | 0.138 -> 0.285 |

The paired family-clustered pooled estimates confirm that augmentation improves F200 recall by
+0.336 [0.263, 0.408] and AUPRC by +0.130 [0.085, 0.178], and compound M3+F200 recall by
+0.311 [0.239, 0.384] and AUPRC by +0.111 [0.070, 0.154]. However, FPR also worsens: +0.129
[0.098, 0.164] at F200 and +0.121 [0.091, 0.154] for M3+F200. Therefore the old claim that
augmentation recovers recall while reducing false positives is false under donor isolation.
The supported claim is a ranking/recall gain with a material false-positive trade-off.

The OOF-threshold sensitivity arm has the same qualitative conclusion, though lower FPRs:
F200 recall 0.324 -> 0.520 and FPR 0.092 -> 0.125; compound recall 0.367 -> 0.504 and FPR
0.108 -> 0.112.

## Cross-platform reproducibility deviation

The original exact replay was produced on macOS ARM64. On this Linux x86_64 host, with matched
numpy/pandas/scikit-learn/XGBoost versions, validation is deterministic across repeated runs
and 4-versus-12 worker settings but does not reproduce the frozen ARM fold scores within 1e-6
(maximum differences 0.022 AuthGuard and 0.055 opcode XGBoost). Remaining conclusions use only
within-host paired comparisons. No manuscript comparison mixes a Linux-refit number with an
ARM-refit comparator. Exact reproduction of frozen scores requires the recorded ARM platform.

## Integrity and failures

- Frozen guard passed before and after every completed run: 144/144 files unchanged.
- Protocol hash audit: four of five frozen protocol hashes verify. The donor-isolation file
  contains the committed v1.1 fold-aligned amendment made before donor-isolated results, but
  `protocols.sha256` retains its v1.0 hash. Neither frozen artifact was rewritten; the stale
  ledger entry is documented in `revision_v2/audits/protocol_hash_validation.md`.
- The first G-ADV attempt was interrupted after fold 1 and produced no retained partial output;
  the complete rerun above is the only v2 result source.
- The v1 single-donor design and v1 in-sample threshold selection are retained as documented
  invalid/confounded comparators, not silently replaced.
- Cross-platform 1e-6 validation failed; the deterministic architecture-specific deviation is
  documented rather than waived.

## Claims enabled

- Thresholds are selected on family-disjoint OOF or explicitly labeled validation families.
- Random splitting is materially optimistic on this corpus.
- AuthGuard outperforms the strongest pre-existing evaluated bytecode baseline with a paired CI.
- Donor-isolated augmentation improves F200 and compound ranking/recall but increases false
  positives at the primary operating point.

## Frozen-hash verification

PASS: 144 frozen files verified unchanged after Phase 1 completion.
