# Result Reconciliation & Provenance

All values traced to artifacts. Where a value cannot be traced it is marked `[NOT MEASURED]`.
No value is reconstructed from a plot when a result file exists.

## Missing / renamed artifacts
- **`features.parquet` — MISSING.** Features were persisted as `results/features_dense.npz`
  (dense 261-d), `results/features_ngram.npz` (512-d hashed 4-grams), and
  `results/feature_meta.json` (column names, `hist_dim=225`, banned-feature list). Functionally
  equivalent; the paper should cite the `.npz` triple, not a parquet file.
- All other required artifacts are present.

## Result-provenance table
Legend for **Comparable?**: values sharing the same protocol row-key are directly comparable.

| # | Metric | Value | Subset | Split | Fold | Threshold selection | Aggregation | Model version | Artifact | Comparable group |
|--|--|--|--|--|--|--|--|--|--|--|
| 1 | AUPRC | **0.856**±0.043 | mal 793 vs benign_cleared 1657 | leave-family-out | GroupKFold(5), **train=4 folds** | in-sample max-F1 (train) — *AUPRC is threshold-free* | mean±std/fold | AuthGuard (full feats) | `results/detection_results.json` → primary/leave_family_out/authguard | **G-DET** |
| 2 | AUPRC | 0.961 | same | **random 5-fold** | random | in-sample max-F1 | mean/fold | AuthGuard | `detection_results.json` → random_split/authguard | G-DET (leakage-context) |
| 3 | AUPRC | **0.830** | same | leave-family-out | GroupKFold(5), **train-fit=3 folds**, 1 fold=val | **held-out clean-M0 val** max-F1 | mean/5 folds | AuthGuard-M0 | `advtrain_results.json`→AuthGuard-M0/M0/AUPRC | **G-ADV** |
| 4 | AUPRC | 0.849 | same | leave-family-out | 3-fold train-fit | held-out val max-F1 | mean/5 | AuthGuard-aug | `advtrain_results.json`→AuthGuard-aug/M0/AUPRC | G-ADV |
| 5 | retained recall M3 | 0.588 | held-out malicious mutants | split-before-mutate LFO | GroupKFold(5), train=4 | in-sample max-F1 | mean/fold | AuthGuard-M0 | `results/mutation_curve.json`→authguard/M3 | **G-MUT** |
| 6 | recall M3 | 0.787 | mutated mal+benign test | LFO | 3-fold train-fit | held-out val max-F1 | mean/5 | AuthGuard-M0 | `advtrain_results.json`→AuthGuard-M0/M3/recall | G-ADV |
| 7 | retained recall +200% | **0.139** | held-out malicious, **M3-base + 200% flood** | split-before-mutate LFO | train=4 | in-sample max-F1 | mean/fold | AuthGuard-M0 | `results/mutation_volume.json`→authguard/"2.0" | **G-VOL** |
| 8 | recall +200% | **0.624** | mutated test, **M0-base + 200% flood** | LFO | 3-fold train-fit | held-out val max-F1 | mean/5 | AuthGuard-M0 | `advtrain_results.json`→AuthGuard-M0/F200/recall | G-ADV |
| 9 | recall +200% | 0.790 | M0-base+200% flood | LFO | 3-fold | held-out val | mean/5 | AuthGuard-aug | `advtrain_results.json`→AuthGuard-aug/F200 | G-ADV |
| 10 | latency ms/contract | 3.37 mean / 2.47 p50 / 10.67 p95 | 300 sampled | n/a | n/a | n/a | mean/pctl | AuthGuard featurize+predict | `results/supporting.json`→latency | — |
| 11 | contamination upper bound | 8.1% (135/1657); 1.2% exact-dup | benign_cleared | n/a | n/a | n/a | count | — | `supporting.json`→contamination | — |
| 12 | independent truly-novel confirmed | 1 | scamsonethereum ∩ on-chain | n/a | n/a | n/a | count | — | `reports/funnel.json` | — |

## The six required reconciliations

**R1 — 0.856 vs 0.830 (AuthGuard family-grouped AUPRC).** *Cause: training-set size, not
threshold.* AUPRC is rank-based and threshold-independent, so the differing threshold protocol
cannot explain it. Row 1 trains on 4 GroupKFold folds; row 3 reserves one fold for clean-M0
threshold validation and trains on 3, i.e. ~25% less data. The ~0.026 drop is the cost of the
stricter held-out-threshold protocol. **Not directly comparable** (different train size).
*Paper use:* 0.856 for the main detection table (G-DET, all baselines present); 0.830 only inside
the adversarial-training table (G-ADV). Never present them as the same quantity.

**R2 — 0.849 vs 0.830 (aug vs M0 clean).** Same protocol (G-ADV), paired, directly comparable.
Augmentation *raises* clean AUPRC by +0.019 and *lowers* benign FPR 0.192→0.164 at a small clean
recall cost (0.797→0.761). This is the correct "no clean cost" evidence. *Paper use:* Table 5.

**R3 — 0.139 vs 0.624 (the "+200% collapse").** *Two differences at once:* (a) **condition** —
row 7 floods the **M3 base** (compound: selector-rewrite + address-rewrite + 200% pad), row 8
floods the **M0 base** (pure severity); (b) **threshold** (in-sample vs held-out-val) and train
size. **Not comparable.** The 0.139 is the compound worst case that *motivated* the augmentation
study; the augmentation study did **not** retest it (flooding was defined on M0 to keep M3
held-out and leakage-safe). *Paper use:* report 0.139 as the original M3+flood worst case
(G-VOL) and 0.624→0.790 as the pure-M0 +200% severity recovery (G-ADV) — explicitly distinct
axes. Do **not** claim the 0.139 collapse was recovered.

**R4 — M3 retained 0.588 vs recall 0.787.** Same model, same M3 condition, different protocol:
row 5 uses in-sample max-F1 (higher threshold → lower recall) on 4-fold training; row 6 uses
held-out-val max-F1 (lower threshold → higher recall) on 3-fold. **Not comparable** across
G-MUT and G-ADV. Both are leakage-safe within their own group. *Paper use:* keep the M0–M3
mutation curve (G-MUT) for the *rule-vs-learned brittleness* story (which is threshold-robust for
the rules), and the G-ADV numbers for the augmentation story; never overlay them.

**R5 — M3-only vs M3+heavy-flood.** M3 alone is not the weakness (AuthGuard-M0 retains
0.588 [G-MUT] / 0.787 [G-ADV]); the weakness is the **compound** M3+heavy-flood (0.139, G-VOL).
The augmentation study evaluated the two held-out axes **separately** (M3 condition; +200%
severity) and did not evaluate their combination. This is the single most important scoping
caveat and must appear wherever recovery is claimed.

**R6 — clean 0.830 vs 0.856.** Same as R1 (train size). Use 0.856 as the headline detection
number; treat 0.830 as the G-ADV re-baseline under the stricter protocol.

## Protocol-group rule (enforced in every table/figure)
- **G-DET** (detection_results.json): 4-fold train, in-sample threshold, 8 methods, +random-split.
- **G-MUT** (mutation_curve.json): M0–M3 retained detection, in-sample threshold.
- **G-VOL** (mutation_volume.json): M3-base flooding sweep, in-sample threshold.
- **G-ADV** (advtrain_*): 3-fold train-fit + held-out-val threshold, pure-M0 flooding, 5 models.

Values from different groups **must not** share a table column or a figure axis.
