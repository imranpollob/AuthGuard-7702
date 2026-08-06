# Dataset Statistics

Run `v2`, Ethereum mainnet, blocks 25,595,577–25,695,577. All values read from saved artifacts.

## Collection (`data/collected_delegates/`)

| | |
|---|---:|
| Blocks scanned | 100,444 |
| Type-0x4 transactions | 374,878 |
| Authorization entries | 1,335,391 |
| Signers recovered | 1,335,384 (99.9995%) |
| Recovered signer ≠ tx.from | 1,309,586 (98.07%) |
| Distinct nonzero delegates | 760 |
| Screenable | 752 |
| NOTSCREENABLE | 8 |

## Families (`data/bytecode_families/`)

| | |
|---|---:|
| Unique runtime bytecodes | 669 |
| Similarity families (Jaccard ≥ 0.85) | 454 |
| Largest family | 212 members |

## Labels — full screenable population (rubric v3)

| Label | n | share |
|---|---:|---:|
| B | 305 | 40.6% |
| U | 324 | 43.1% |
| R1 | 99 | 13.2% |
| R2 | 24 | 3.2% |

## Human-reviewed gold dataset (`data/gold_dataset/v2_gold_reviewed.csv`)

| | |
|---|---:|
| Reviewed runtimes | 300 |
| Gold contracts (after exact-bytecode propagation) | 306 |
| — directly reviewed | 300 |
| — propagated across identical bytecode | 6 |
| Split groups | 223 |
| NOTSCREENABLE held separately | 8 |

| Label | train | val | test | total |
|---|---:|---:|---:|---:|
| R1 | 31 | 9 | 8 | 48 |
| R2 | 9 | 0 | 1 | 10 |
| B | 73 | 41 | 35 | 149 |
| U | 80 | 12 | 7 | 99 |
| **total** | **193** | **62** | **51** | **306** |

Decidable (R1/R2/B) rows: train 113, val 50, test 44. Test prevalence 0.205 (9/44).

## Huang weak-label reference set

| | |
|---|---:|
| Rows | 2,450 |
| Positive (rule-flagged) | 806 |
| Used for pretraining after overlap exclusion | 2,367 |
| Excluded for overlap with the gold population | 83 |

## Provenance hashes

| Artifact | SHA-256 (first 16) |
|---|---|
| Frozen human review | `8a8ad2562bdd6123` |
| Split manifest | `f87cf8f419e7fede` |
