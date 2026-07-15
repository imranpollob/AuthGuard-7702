# Recommended Tables

Rule: never mix protocol groups (G-DET/G-MUT/G-VOL/G-ADV) in one table. Values verified against
artifacts. Placement and 8-page cut plan noted.

## Table 1 — Dataset composition (MAIN)
Columns: subset | contracts | families | singleton-family % | label source | role.
| subset | contracts | families(bearing) | singleton % | label source | role |
|--|--|--|--|--|--|
| malicious | 793 | 214 | 52.8% (of mal fams) | USENIX rule | positives |
| benign_cleared | 1,657 | — | — | rule-silent (weak) | primary negatives |
| benign_general | 800 | — | — | general sample | secondary negatives |
| benign_AA | 8 | — | — | hand-verified | clean control |
Global: 1,329 families, 68.6% singletons, largest 58. **Source:** `family_structure.json`, `capability_dataset.csv`. **Caption:** "Dataset and frozen family structure." **Cut:** keep (small, essential).

## Table 2 — Main family-grouped performance (MAIN) — G-DET only
Columns: method | AUPRC | AUROC | P | R | F1 | (±std AUPRC). Rows: AuthGuard-M0(=AuthGuard), opcode-RF, opcode-XGB, selector-LR, blocklist, sensitive-name approx., external-call struct approx. **Do NOT** put AuthGuard-aug or opcode-XGBoost-aug here (G-ADV, different protocol). Values from `detection_results.json` (see evaluation_inventory RQ1). **Caption:** "Leave-family-out detection (mal vs benign_cleared), mean±std over 5 folds; oracle is tautological." **Cut:** keep; drop AUROC column first if space.

## Table 3 — Random vs family split (MAIN) — G-DET
Columns: model | random AUPRC | family AUPRC | gap. Rows: AuthGuard 0.961/0.856/0.105; opcode-XGB 0.948/0.789/0.159; opcode-RF 0.941/0.775/0.166; blocklist 0.558/0.324/0.234. **Source:** `detection_results.json`. **Caption:** "Random-split inflation (memorization gap)." **Cut:** can merge into Table 2 as two extra columns if >8 pp.

## Table 4 — Original mutation robustness M0–M3 (MAIN) — G-MUT
Columns: method | M0 | M1 | M2 | M3 (retained recall). Rows: sensitive-name 0.038/0.038/0.038/0.000; external-call struct 1.000×4; blocklist 0×4; opcode-XGB 0.656/0.659/0.518/0.518; AuthGuard 0.641/0.668/0.588/0.588. **Source:** `mutation_curve.json`. **Caption:** "Retained detection under structure-preserving mutation (in-sample threshold); preservation verified 793/793." **Cut:** keep — it carries the evasion-brittleness contribution.

## Table 5 — Adversarial-training evaluation (MAIN) — G-ADV only
Columns: model | condition | AUPRC | P | R | FPR | singleton-recall | family-macro-recall. Conditions: clean M0, M3, +200%. Rows: AuthGuard-M0, AuthGuard-aug, opcode-XGBoost, opcode-XGBoost-aug. Key cells: AuthGuard-M0 F200 R 0.624/AUPRC 0.596/FPR 0.314; AuthGuard-aug F200 R 0.790/AUPRC 0.750/FPR 0.275/singleton 0.850/macro 0.844; clean AUPRC 0.830→0.849. **Source:** `advtrain_results.json`, `advtrain_analysis.json`. **Caption:** "Adversarial-training evaluation under the stricter held-out-val-threshold protocol; +200% is a held-out severity, M3 a held-out condition; compound M3+flood not tested." **Cut:** keep — carries C3.

## Table 6 — Runtime (MAIN, small) — measured only
Rows: feature extraction+inference (end-to-end) 3.37 ms mean / 2.47 p50 / 10.67 p95; batched 3.18 ms. **Do NOT** include a decompiler row (`[NOT MEASURED]`). **Source:** `supporting.json`. **Caption:** "End-to-end per-contract latency (no decompiler; excludes network fetch)." **Cut:** can move to text if >8 pp.

## Appendix tables (cut from main first)
- A1: family-threshold sensitivity (0.75/0.85/0.90) — `family_structure.json`.
- A2: original flooding sweep M3+flood +0…+200% (G-VOL, 0.139) — `mutation_volume.json`; label clearly as the *compound* worst case, distinct from Table 5.
- A3: full per-fold values + Wilson/bootstrap CIs — `advtrain_analysis.json`.
- A4: contamination + independent-set funnel — `supporting.json`, `funnel.json`.

## 8-page cut priority
Keep Tables 1,2,4,5. Fold Table 3 into Table 2 (columns). Move Table 6 to text. Everything
else → appendix. Never delete the random-vs-family evidence (it is contribution C2).
