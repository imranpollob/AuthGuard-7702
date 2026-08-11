# Gate 0B — Trivial similarity baseline (kNN)

## Headline result

Nearest-neighbour bytecode lookup reaches **AUPRC 0.6121** (MinHash, k=5) against AuthGuard-Seq's **0.9244**, a paired family-clustered difference of **−0.3023, 95% CI [−0.3797, −0.2264]** — the learned model is decisively better than similarity lookup, and this supports the paper's claim on the one axis the gate tests.

## Status

**PASS**, with a large caveat that limits how much credit the result deserves.

kNN lands 0.31 AUPRC below AuthGuard-Seq, far outside the 0.03 band that would have made the learned model's marginal value thin. The deployment story does not become "maintained similarity index." However, the family-disjoint evaluation protocol *guarantees* much of this outcome by construction: only **1.2%** of test rows have a training neighbour above 0.9 similarity, because folds are family-disjoint and families were themselves formed by MinHash clustering. The protocol removes the near-duplicate signal kNN depends on before kNN is ever run.

This gate therefore does not rescue the paper. Gate 0A remains a FAIL, and a strong result here does not offset it: the emulator that ties AuthGuard-Seq in Gate 0A is not a similarity method, so the two gates are not in tension.

---

## Method

- **Data / splits / seeds / aggregation:** identical to Gate 0A (v2 benchmark, `PRIMARY_EVALUATION`, stored `fold_id`, seeds 7702/7703/7704, macro over folds then seeds).
- **Leak avoidance:** the index is built **from the training folds only and rebuilt per outer fold**. The frozen `family_id` is not used anywhere in scoring. This matters because families were clustered globally across all rows including test; reusing them would leak test membership into the index.
- **Index parameters** (documented separately from `pipeline/01_freeze_families.py`, which uses 128 permutations):
  - tokens: opcode 4-grams from linear-sweep disassembly, PUSH*n* collapsed to `PUSH`
  - MinHash: **256 permutations**, blake2b-64 with an 8-byte little-endian salt (`PYTHONHASHSEED`-independent)
  - similarity: estimated Jaccard = fraction of agreeing signature positions
  - second view: L2-normalised **opcode-histogram cosine**
- **Classifier:** k ∈ {1, 3, 5}; score = similarity-weighted malicious fraction of the k nearest training rows.

**Entry point:** `revision_v2/experiments/gate_0b_knn/run_gate_0b.py`
**Artifacts:** `revision_v2/results/gate_0b_knn/`

---

## Results

### Overall (macro over folds)

| Model | AUPRC | AUROC | Recall@5%FPR |
|---|---|---|---|
| **AuthGuard-Seq** | **0.9244** | 0.9627 | 0.8327 |
| kNN MinHash, k=5 | 0.6121 | 0.7913 | 0.000 |
| kNN MinHash, k=3 | 0.5972 | 0.7869 | 0.000 |
| kNN MinHash, k=1 | 0.5406 | 0.7358 | 0.000 |
| kNN opcode-hist cosine, k=5 | 0.5520 | 0.7368 | 0.2063 |
| kNN opcode-hist cosine, k=3 | 0.5343 | 0.7390 | 0.1169 |
| kNN opcode-hist cosine, k=1 | 0.5051 | 0.7147 | 0.000 |

MinHash beats the opcode-histogram view at every k, and larger k helps both. The zero recall@5%FPR entries are a resolution artefact, not a failure: with k=5 the score takes at most six distinct values, so there is often no operating point at or below 5% FPR.

Note that the best kNN (0.6121) sits only modestly above the provenance-only floor of 0.5239 (`family_size` alone, from `shortcut_diagnostics.py`).

### Paired family-clustered bootstrap vs AuthGuard-Seq

| Model | Δ AUPRC | 95% CI | Excludes zero? |
|---|---|---|---|
| kNN MinHash, k=5 | **−0.3023** | [−0.3797, −0.2264] | Yes |

1,998 replicates, multinomial family weights, macro-over-folds recomputed per replicate.

### Stratified by maximum similarity to the training fold (MinHash, k=5)

This is the table the gate exists to produce.

| Max train similarity | n | Positives | Prevalence | AUPRC |
|---|---|---|---|---|
| > 0.9 | 27 | 5 | 0.185 | 0.185 |
| 0.7 – 0.9 | 955 | 361 | 0.378 | 0.7475 |
| 0.5 – 0.7 | 724 | 240 | 0.332 | 0.6265 |
| < 0.5 | 484 | 121 | 0.250 | 0.3140 |

Performance degrades monotonically as the nearest training neighbour gets further away, exactly as expected — except in the >0.9 bin, where AUPRC collapses to 0.185. That bin holds only 27 rows with 5 positives, so it is dominated by sampling noise and its prevalence (0.185) is itself below base rate; no weight should be placed on it.

Distribution of max training similarity across the 2,190 test rows: median **0.684**, IQR 0.543–0.770, max 0.984. **Only 1.2% exceed 0.9.**

### Latency

| | Value |
|---|---|
| Index build (all 2,190 rows, signatures) | 8.93 s |
| Mean query (one test row vs full training fold, brute force) | 0.678 ms |

Query latency is below AuthGuard-Seq's 4.121 ms even without an ANN structure, but at 0.61 AUPRC it is not buying anything.

---

## What this does not show

- **The protocol pre-determines much of this result.** Families were formed by MinHash-similarity clustering and folds are family-disjoint, so by construction a test row's near-duplicates are largely excluded from its training index. kNN is being asked to generalise across exactly the boundary the split was designed to enforce. A deployment-time similarity index — which *would* see prior members of a reused family — would perform substantially better than 0.6121. This gate measures kNN under the paper's evaluation protocol, not kNN's operational value.
- **It says nothing about detecting theft.** As in Gate 0A, the target is the source-analyzer label, not observed malicious behaviour.
- **Brute-force scoring only.** No LSH banding, no ANN index, no tuning of permutation count, k-gram size, or the similarity-weighting scheme. kNN received a fixed reasonable configuration while AuthGuard-Seq is a tuned artifact; the work order's equal-budget rule is not satisfied here, and the gap is therefore an upper bound on the true gap.
- **The >0.9 similarity stratum is too small to interpret** (27 rows, 5 positives).
- **Single host, single-threaded**, same caveat as Gate 0A.
