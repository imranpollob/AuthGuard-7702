# Dataset Statistics (run `v2`, as of Stage 5 completion)

Every number below is read from a saved file under `data/`; see the path in each row.

## Population (Stage 2)

| | |
|---|---:|
| Blocks scanned | 100,444 |
| Type-0x4 transactions | 374,878 |
| Authorization entries | 1,335,391 |
| Distinct nonzero delegate addresses | 760 |
| Screenable (bytecode retrieved) | 752 |
| NOTSCREENABLE | 8 |

Source: `data/collected_delegates/v2_ethereum_population.csv`,
`v2_ethereum_population_summary.json`. Full detail in `reports/collection_report.md`.

## Bytecode families (Stage 3)

| | |
|---|---:|
| Exact-bytecode groups | 669 |
| Bytecode families (Jaccard ≥ 0.85) | 454 |
| Singleton families | 407 (89.6%) |
| Largest family | 212 members |

Source: `data/bytecode_families/v2_family_assignment.csv`, `v2_family_summary.json`.

## Evidence + LLM preliminary review (Stages 4–5)

| | |
|---|---:|
| Evidence packages | 752 |
| Verified source (Sourcify) | 64 (8.5%) |
| Matches a documented known project | 8 (1.1%) |
| LLM proposed R1 | 23 |
| LLM proposed R2 | 524 |
| LLM proposed B | 205 |
| LLM proposed U | 0 |

Source: `data/evidence_packages/v2_evidence_index.csv`, `data/llm_reviews/v2_review_index.csv`.
Full detail in `reports/labeling_report.md`.

## Huang/USENIX weak-label reference population (independent of the above collection)

| | |
|---|---:|
| Rows (chain,address pairs with bytecode) | 2,450 |
| Positive (rule-flagged) | 806 |
| Negative | 1,644 |
| Distinct addresses | 2,153 |

Source: `dataset_pipeline/lib/huang_loader.py`, read directly from
`USENIX EIP-7702 artifact/eoa_detect/`. No prior loader for this raw artifact existed in the
repository.

## Not yet available

Human-reviewed gold labels, family-disjoint temporal train/val/test splits, model results
(Experiments A/B/C), and coverage-deferral results all require
`data/human_reviews/v2_completed.jsonl` to exist and cover all 752 screenable rows first (Stage
6, in progress — `data/human_reviews/v2_queue.csv`). This document will be extended with those
sections once that stage completes; no placeholder numbers are included here in the meantime.
