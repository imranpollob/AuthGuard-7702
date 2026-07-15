# Result Provenance Ledger

This ledger defines the source, protocol, and permitted use of every result proposed for the paper. Values from different protocol groups must not share comparison columns.

## Frozen artifact fingerprints

| Artifact | SHA-256 | Purpose |
|---|---|---|
| `capability_dataset.csv` | `6ce025981d59894be16506a6a963262c47a2495a00533c4434616bdbd66c6bfa` | sample population and labels |
| `family_assignment_frozen.csv` | `88ba3ef0c031425e3a7802e8723f24fd5a8ff9a504fa6615713cf73182ab204e` | frozen family IDs |
| `results/detection_results.json` | `3350875417e1e557e286a9ba79ee099fb7813b6005b3d8346a16e84826427be7` | G-DET results |
| `results/mutation_curve.json` | `73025647b15205b09e667d8210ccf3ff1e98000f725d7f6fe4b69dfc05be1052` | G-MUT retained recall |
| `results/mutation_volume.json` | `edef9e96fc66696ae989fa0456a3a7a973d2a905a66a0ae7e92abc444d803863` | G-VOL flooding sweep |
| `results/supporting.json` | `011882287cdf8389c82e5bb93794fa42c7d213678177504d8c457daacd2d5525` | contamination and latency |
| `advtrain_results.json` | `721f7eeeebd5de073cc4b03b33b9a70eba96dcfdd1d7481a57bb932ce6fd8036` | G-ADV fold metrics |
| `paired_results.csv` | `d686f11ec424012c6d9d2c7eeff27928db16e471147687b77106b5d0781d4073` | G-ADV per-contract scores/predictions |
| `reports/advtrain_leakage_assertions.txt` | `e75d5f3ed1826f86e05fcd4228c6e50fac950e7ef9ae673026d79fa3ececa9a6` | split and mutation leakage assertions |

Any rerun that changes these fingerprints requires a new reconciliation pass.

## Dataset and family provenance

| Result | Verified value | Direct source | Producing/checking code | Paper use |
|---|---:|---|---|---|
| total contracts | 3,258 | `capability_dataset.csv` | direct CSV count | Table 1/methodology |
| positives | 793 | dataset plus 793 address objects in USENIX `detect_result.jsonl` | label assembly described in Phase 0 artifacts | Table 1; always disclose rule-derived labels |
| `benign_cleared` | 1,657 | dataset | direct CSV count | primary weak negatives |
| `benign_general` | 800 | dataset | direct CSV count | secondary only |
| `benign_AA` | 8 | dataset | direct CSV count | small control only |
| frozen global families | 1,329 | frozen CSV | `pipeline/01_freeze_families.py` | Table 1 |
| global singleton families | 912 (68.6%) | frozen CSV / family JSON | same | methodology |
| cross-class families | 44 (3.3%) | frozen CSV / family JSON | same | leakage/contamination discussion |
| positive-bearing families | 214 | frozen CSV | direct grouped count | Table 1 |
| pure-positive families | 178 | frozen CSV | direct grouped class-set count | optional methodology text |
| positive-member singletons | 113/214 (52.8%) | frozen CSV | direct grouped count | Table 1 |
| largest positive family | 58 | frozen CSV | direct grouped count | Table 1 |

## G-DET: primary family-grouped detection

Population: 793 rule-labeled positives versus 1,657 `benign_cleared` weak negatives.  
Split: `GroupKFold(5)` by frozen global family; each run trains on four outer folds and tests on one.  
Estimator selection: fixed in code.  
Operating threshold for precision/recall/F1: max-F1 on in-sample training predictions.  
Primary threshold-free metric: AUPRC.  
Source: `results/detection_results.json`; producer: `pipeline/03_detection.py`.

| Method | Family AUPRC | SD | AUROC | Precision | Recall | F1 | Random AUPRC |
|---|---:|---:|---:|---:|---:|---:|---:|
| sensitive-name rule approximation | 0.344 | 0.093 | 0.518 | 0.884 | 0.038 | 0.071 | 0.352 |
| external-call structural over-approximation | 0.341 | 0.084 | 0.539 | 0.341 | 1.000 | 0.503 | 0.341 |
| blocklist | 0.324 | 0.078 | 0.500 | 0.000 | 0.000 | 0.000 | 0.558 |
| selector-LR | 0.519 | 0.068 | 0.670 | 0.459 | 0.617 | 0.521 | 0.558 |
| opcode-RF | 0.775 | 0.076 | 0.895 | 0.782 | 0.444 | 0.557 | 0.941 |
| opcode-XGB | 0.789 | 0.060 | 0.907 | 0.784 | 0.656 | 0.704 | 0.948 |
| **AuthGuard** | **0.856** | **0.043** | **0.930** | **0.871** | **0.641** | **0.720** | **0.961** |

Derived AuthGuard random-minus-family AUPRC gap: `0.9607622395 - 0.8564974959 = 0.1042647436`, reported as 0.105 or about 0.10.

The JSON also contains a `usenix_shipped_oracle` with 1.000 metrics because it reads the class label. It is a tautological sanity check, not an evaluated detector, and is excluded from the recommended main table.

## G-MUT: cumulative M0--M3 mutation evaluation

Population/split: G-DET primary population and five family folds; learned models train on clean M0 training families. Only held-out positives are mutated.  
Threshold: max-F1 on in-sample training predictions.  
Metric: retained recall on the held-out positives.  
Sources: `results/mutation_curve.json`, `results/mutation_preservation.json`; producer: `pipeline/04_mutations.py`.

| Method | M0 | M1 metadata | M2 + address/dead code | M3 + selector rewrite |
|---|---:|---:|---:|---:|
| sensitive-name rule approximation | 0.038 | 0.038 | 0.038 | 0.000 |
| external-call structural over-approximation | 1.000 | 1.000 | 1.000 | 1.000 |
| blocklist | 0.000 | 0.000 | 0.000 | 0.000 |
| selector-LR | 0.617 | 0.621 | 0.623 | 0.621 |
| opcode-XGB | 0.656 | 0.659 | 0.518 | 0.518 |
| **AuthGuard** | **0.641** | **0.668** | **0.588** | **0.588** |

Checker result: 793/793 variants at each of M1, M2, and M3 preserve the original pre-metadata opcode-token sequence according to `verify_preservation`. Describe these variants as structure-preserving. EVM execution equivalence was not run.

## G-VOL: compound M3-style dead-code flooding

Population/split/threshold: separate protocol implemented by the latter part of `pipeline/04_mutations.py`.  
Condition: metadata rewrite + address rewrite + sensitive-selector rewrite, with flooding amount varied; this is not the G-ADV pure-M0 F200 condition.  
Metric: retained recall on held-out positives.  
Source: `results/mutation_volume.json`.

| Method | +0% | +25% | +50% | +100% | +200% |
|---|---:|---:|---:|---:|---:|
| AuthGuard | 0.668 | 0.567 | 0.500 | 0.310 | **0.139** |
| opcode-XGB | 0.659 | 0.523 | 0.498 | 0.473 | 0.485 |
| external-call structural over-approximation | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| sensitive-name rule approximation | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |

Use only as a separately labeled limitation or motivation. Do not imply G-ADV recovered this 0.139 compound condition.

## G-ADV: stricter adversarial-training protocol

Population: same 2,450 primary samples.  
Outer split: five family-grouped test folds. For outer fold `f`, fold `(f+1) mod 5` is validation and the other three folds are train-fit.  
Training conditions for augmented models: M0, M1, M2, F25, F50, F100, with each source’s total weight normalized to one.  
Threshold: max-F1 on clean-M0 validation families.  
Held-out conditions: M3 and F200. F200 is a held-out severity but is generated from pure M0, not from M3.  
Sources: `advtrain_results.json`, `paired_results.csv`, `reports/advtrain_analysis.json`; producers: `pipeline/adv_run.py`, `pipeline/adv_analysis.py`.

### Fold-mean AuthGuard results

| Condition | Model | AUPRC | Precision | Recall | Benign FPR |
|---|---|---:|---:|---:|---:|
| clean M0 | AuthGuard-M0 | 0.830 | 0.693 | 0.797 | 0.192 |
| clean M0 | AuthGuard-aug | 0.849 | 0.720 | 0.761 | 0.164 |
| held-out M3 | AuthGuard-M0 | 0.754 | 0.613 | 0.787 | 0.276 |
| held-out M3 | AuthGuard-aug | 0.814 | 0.686 | 0.801 | 0.196 |
| held-out pure-M0 +200% | AuthGuard-M0 | 0.596 | 0.525 | 0.624 | 0.314 |
| held-out pure-M0 +200% | AuthGuard-aug | 0.750 | 0.615 | 0.790 | 0.275 |

### Same-protocol representation comparator at +200%

| Model | AUPRC | Recall | Benign FPR |
|---|---:|---:|---:|
| opcode-XGB | 0.562 | 0.606 | 0.352 |
| opcode-XGB-aug | 0.688 | 0.701 | 0.324 |
| AuthGuard-aug | 0.750 | 0.790 | 0.275 |

### Family-shape and paired evidence

| Result | Verified value | Source and caveat |
|---|---:|---|
| +200% singleton recall | 0.655 → 0.850 | `reports/advtrain_analysis.json` |
| +200% family-macro recall | 0.674 → 0.844 | same |
| pooled +200% recall | 0.636 → 0.797 | paired predictions |
| pooled +200% recall difference | +0.161 | paired predictions |
| current 95% interval | [0.131, 0.193] | contract bootstrap; must be replaced or labeled non-family-aware |
| pooled clean recall | 0.803 → 0.772 | paired predictions; real clean tradeoff |
| pooled clean FPR | 0.189 → 0.158 | paired predictions |

All five logged source-overlap, family-overlap, train/test hash-overlap, and mutant-family-inheritance assertions pass. The assertions support split integrity; they do not repair the contract-level bootstrap caveat.

## Runtime and negative-set provenance

Source: `results/supporting.json`; producer: `pipeline/05_supporting.py`.

| Result | Value | Scope |
|---|---:|---|
| local mean | 3.367 ms/contract | feature extraction + single-contract prediction |
| local p50 | 2.469 ms | same |
| local p95 | 10.673 ms | same |
| batched mean | 3.181 ms/contract | batch of 300 |
| `benign_cleared` same malicious-bearing family | 135/1,657 (8.1%) | heuristic contamination upper bound |
| `benign_cleared` exact malicious duplicate | 20/1,657 (1.2%) | strong overlap evidence |

Excluded from latency: authorization parsing, RPC/network fetch, caching, wallet/UI handling, and any full USENIX/decompiler pipeline. Hardware provenance is absent.

## Independent-set provenance

Source chain: `reports/inventory.json` → `reports/getcode_summary.json` → `reports/independent_targets.csv` / `target_maliciousness.json` → `reports/funnel.json` → `reports/independent_detection.json` and per-contract CSV.

Verified funnel: 7,915 blacklist addresses → 49 designating accounts → 9 delegate targets → 4 independently confirmed malicious → 3 absent as exact samples → 1 outside the frozen malicious families. Final verdict: **INSUFFICIENT DATA (N=1)**. No quantitative generalization or superiority statement may be derived.

## Provenance rules for drafting

1. Copy numeric values from this ledger or the direct artifact, not from the old `.tex`.
2. State the protocol group in every results table/figure caption.
3. Use fold means for the main metric table; use pooled paired values only for explicitly paired analyses.
4. Do not mix fold-mean and pooled values without labeling the aggregation.
5. Do not use the existing confidence interval as family-aware.
6. Use “sensitive-name rule approximation” and “external-call structural over-approximation.”
7. State that the full USENIX pipeline was not executed.
