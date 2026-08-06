# Dataset Workflow Plan

Status: draft, written before any new code runs. Scope: implement the 10-step workflow
(collect real EIP-7702 delegates → families → evidence → LLM pre-review → human review →
final splits → model experiments A/B/C → coverage-deferral evaluation → reports/paper
artifacts) as a **fresh, self-contained pipeline**, independent of `revision_v2/` and
`revision_v3/`. Those two directories are read-only reference material for this work and are
never modified.

## 0. What this repo already has

An inventory pass (`Explore` agent + direct reads, 2026-08-06) found that most of the *low-level
mechanics* needed already exist as working, tested code, mainly under `revision_v3/src/`. This
plan reuses that code as library modules (via `sys.path`, not copy-paste) wherever it is
generic and correct, and writes new orchestration/config/output layers around it. Nothing under
`revision_v2/`, `revision_v3/`, `pipeline/`, or `paper_build/` is edited.

| Need | Reusable module | Reuse plan |
|---|---|---|
| Block/tx scanning for type-0x4 authorizations | `revision_v3/src/temporal/collector.py::scan_block_range` | Reuse via import. **Must extend**: it currently drops `yParity/r/s`, `to` designator target, and per-tx sender before writing rows — needed fields for signer recovery, frequency counts, and "recovered signing authority" per the spec. New wrapper script adds these fields and computes first-observed/frequency downstream. |
| RPC client (public, keyless) | `revision_v3/src/temporal/rpc_client.py::ChainClient` | Reuse as-is. Config will surface chain + block range instead of hardcoding. |
| Authorization signer recovery (ECDSA) | `revision_v3/src/temporal/authorization.py::recover_authority` | Reuse as-is; already unit-tested (`revision_v3/tests/test_temporal_authorization.py`). This is the piece that makes "recovered signing authority ≠ tx.from" correct rather than assumed. |
| Bytecode retrieval + caching | `ChainClient.get_code` + new on-disk JSON cache (none of the existing caches — `revision_v3` enrich output, `revision_v2/audit/repair_rpc_cache.json` — are structured as a reusable append-only cache keyed by `(chain,address,block)`; a small new cache module is needed) | New: `dataset_pipeline/lib/bytecode_cache.py`. |
| Opcode disassembly | `revision_v3/src/features/disassembler.py::linear_sweep` | Reuse as-is (independent, stdlib-only, verified feature-parity with the older `pipeline/ag_common.py` disassembler). |
| Opcode k-gram / similarity hashing | `revision_v3/src/features/hashing.py::opcode_kgrams` (Jaccard) and `pipeline/ag_common.py::minhash_signature` (MinHash+union-find) | Reuse Jaccard-vs-representative for fast incremental family assignment (as `enrich.py` already does); reuse MinHash+union-find logic pattern from `pipeline/01_freeze_families.py` for the from-scratch clustering step over the newly collected population (adapted, not copied, since this is a new population, not the frozen v2/v3 one). |
| Huang/USENIX weak-label source | `USENIX EIP-7702 artifact/eoa_detect/{get_code/contracts_with_bytecode.xlsx, detect_result.jsonl}` | Read directly for Experiment A ("Huang labels only") and the "Huang weak-label dataset" deliverable. No loader currently exists for this raw artifact (a known, documented gap — see `PROJECT_AUDIT_FOR_TPS.md` §3.1) — new `dataset_pipeline/lib/huang_loader.py` needed. |
| AuthGuard model architecture/training | `revision_v3/src/models/*.py`, `revision_v3/src/training/harness.py` | Reuse the model classes and training loop structure; new training entrypoint script drives them over the new gold dataset (three modes: Huang-only, human-only, pretrain+finetune) instead of the frozen v2 fold protocol. |
| Coverage-based deferral / selective policy | `revision_v3/src/evaluation/selective_policy.py` (`WARN/LOW_OBSERVED_RISK/DEFER`, `risk_union`, `selective_decisions`, `selective_policy_metrics`) | Reuse as-is for the coverage-based-deferral arm of Step 9; add score-margin and random-deferral comparators (not present anywhere) in new code. |
| Metrics (AUPRC/AUROC/Brier/threshold-at-FPR) | `revision_v3/src/evaluation/metrics.py` | Reuse as-is. |
| Evidence extraction (guard/CFG/proxy analysis) | `revision_v3/experiments/opus5_labeling/evm_cfg.py`, `revision_v3/src/evidence/` (dossier/brief builder) | Reuse the CFG/guard classifier and dossier assembly logic as the base for the new evidence-package builder; extend fields to match the spec's list (fallback/receive, CALL/DELEGATECALL, value transfers, approvals, storage writes, proxy/upgrade, unresolved jumps, coverage). |
| Human review app | `revision_v3/annotation_app/` (FastAPI+SQLite) | **Not reused for this workflow's UI** — the task calls for something "simple" (Streamlit app / lightweight page / CSV+script), and revision_v3's app is coupled to its own blinding/roster/gating logic for its specific reviewer protocol. New workflow uses a small CSV/JSON review script instead (see Step 6 below), which is enough for one human reviewer (the user) and keeps provenance easy to inspect directly as files. |
| LLM preliminary review | None directly reusable (revision_v3's `opus5_labeling` encodes a fixed rule-based decision function, not a live LLM call; no Anthropic/OpenAI API client exists anywhere in the repo) | New: since I *am* the reviewing LLM, "sending evidence to an LLM" for this workflow means I read each evidence package and produce the structured JSON response myself in-session, logged with a prompt version and model identifier (`claude-sonnet-5`), rather than shelling out to an API. This is disclosed explicitly in the labeling report — it is a real LLM judgment, not a simulated one, but it is not an independent/blinded API call. |

## 1. Directory layout for this workflow

```
configs/dataset_pipeline.json        # block ranges, chains, RPC list, seeds, LLM/model id, paths
dataset_pipeline/
  lib/                                # small new modules (cache, huang_loader, family clustering, evidence)
  scripts/                            # one script per pipeline stage, numbered like pipeline/
data/
  collected_delegates/                # Step 2 output (population + per-authorization records)
  bytecode_families/                  # Step 3 output (exact + family ids, leakage checks)
  evidence_packages/                  # Step 4 output (one JSON per screenable contract)
  llm_reviews/                        # Step 5 output (raw + parsed LLM responses, cached)
  human_reviews/                      # Step 6 output (review CSV/JSON, provenance)
  gold_dataset/                       # Step 7 output (final human-reviewed + Huang + splits)
  split_manifests/                    # Step 7 output (train/val/test address+family lists)
reports/
  collection_report.md, labeling_report.md, dataset_statistics.md,
  leakage_check.md, model_results.md, coverage_gate_results.md, limitations.md
paper_artifacts/
  tables/, figures/, latex_values.tex
docs/
  dataset_workflow_plan.md (this file), annotation_guideline.md, dataset_card.md,
  reproducibility.md
```

## 2. Per-stage plan and commands

**Stage 2 — Collect delegates** (`dataset_pipeline/scripts/01_collect_authorizations.py`,
`02_recover_signers_and_bytecode.py`)
Wraps `scan_block_range`, extended to also record `y_parity/r/s`/`to` fields per authorization
so `recover_authority` can run; computes first-observed block, per-delegate authorization
frequency, calls `get_code` at first observation, hashes it, and marks `NOTSCREENABLE` when
`eth_getCode` returns `0x` or fails after retries. No filtering by suspicion/labels/predictions —
every distinct nonzero delegate address in the configured range is kept.
Command: `python3 dataset_pipeline/scripts/01_collect_authorizations.py --config configs/dataset_pipeline.json`
Requires: network access to public RPC endpoints (no credentials available or needed — see
`revision_v3/src/temporal/rpc_client.py` header for known endpoint quirks). Given the ~7.65
blk/s single-endpoint throughput observed in prior sessions, the default config scopes to a
modest, clearly-labeled recent block range rather than the full historical range; the range is
config-driven so it can be widened later without code changes.

**Stage 3 — Families** (`03_build_families.py`)
Exact-hash grouping (trivial) + MinHash/Jaccard clustering at a fixed, documented threshold
(reusing the `pipeline/01_freeze_families.py` algorithm pattern) over the newly collected
population only. Writes `exact_bytecode_id`/`bytecode_family_id` and a same-family-crosses-split
assertion script that Stage 7's split step must pass.
Command: `python3 dataset_pipeline/scripts/03_build_families.py`

**Stage 4 — Evidence extraction** (`04_extract_evidence.py`)
For every screenable contract (has bytecode), emits one JSON evidence file with the fields
listed in the task spec, built from disassembly + the CFG/guard/proxy analysis reused from
`revision_v3/experiments/opus5_labeling/evm_cfg.py`, plus a best-effort Sourcify verified-source
lookup (public API, no key) and Blockscout-based decompiled/verified-source fetch where
available. Heuristic findings are recorded as findings, never auto-escalated to a label.
Command: `python3 dataset_pipeline/scripts/04_extract_evidence.py`

**Stage 5 — LLM preliminary review** (`05_llm_review.py` + in-session review pass)
Loads each evidence package (without any label/split/LLM-irrelevant fields), and I produce the
required structured JSON (`proposed_label`, `confidence`, `risk_categories`, `evidence`,
`uncertainties`, `summary`) using the R1/R2/B/U definitions verbatim from the task spec. Cached
per contract by evidence-hash so re-runs skip already-reviewed contracts. Saved with prompt
version + model name (`claude-sonnet-5`) + raw and parsed response.
Command: `python3 dataset_pipeline/scripts/05_llm_review.py --resume`

**Stage 6 — Human review** (`06_human_review.py`, CSV/JSON-based, not a new web app)
Emits `data/human_reviews/queue.csv` (address, evidence path, LLM label/explanation/confidence,
decision columns to fill: ACCEPT_LLM_LABEL/CHANGE_LABEL/UNRESOLVED, final_label, final_confidence,
comment, corrected_risk_categories). A small script validates and merges completed rows back into
`data/human_reviews/completed.jsonl`, preserving both original LLM label and final human label.
This stage requires the user's actual judgment — I cannot supply it.

**Stage 7 — Final dataset** (`07_build_gold_dataset.py`)
Assembles the 7 deliverables listed in the spec, enforces family-disjoint splits and temporal
ordering (test observed later than train/val) via the frozen-checkpoint block numbers from Stage
2, and writes `reports/leakage_check.md`.

**Stage 8 — Model experiments A/B/C** (`08_train_models.py`)
Reuses `revision_v3/src/models` + `training/harness.py` building blocks; three runs (Huang-only,
human-only, pretrain-on-Huang+finetune-on-human), evaluated once on the frozen temporal test set.
Writes `reports/model_results.md` and `paper_artifacts/tables/`.

**Stage 9 — Coverage-based deferral** (`09_coverage_deferral.py`)
Reuses `selective_policy.py`'s coverage/margin logic; adds a random-deferral baseline at matched
defer rate. Writes `reports/coverage_gate_results.md`.

**Stage 10 — Reports/paper artifacts**
`reports/*.md`, `paper_artifacts/{tables,figures,latex_values.tex}`, `docs/{annotation_guideline,dataset_card,reproducibility}.md`
assembled from the saved intermediate outputs only — no value is written that isn't traceable to
a file produced by an earlier stage.

## 3. Config

`configs/dataset_pipeline.json` holds: `chains`, `block_ranges` (per chain, configurable),
`rpc_endpoints` (defaults to the same public list `rpc_client.py` uses), `family_similarity_threshold`,
`seeds`, `llm_model_id`/`prompt_version`, and output paths. All stage scripts read this file; none
hardcode block ranges or thresholds.

## 4. Explicit blockers / credential notes

- No Etherscan/Dune/Alchemy keys exist in this environment (confirmed in a prior session,
  `revision_v3/src/temporal/rpc_client.py` header). Public RPC only. Verified-source lookups use
  the free Sourcify/Blockscout APIs, best-effort.
- Stage 6 (human review) requires the user directly; I will prepare the queue and merge tool but
  not fabricate review decisions.
- Stage 5 "LLM preliminary review" is performed by me, in-session, rather than via a separate API
  call — there is no Anthropic API key configured for programmatic use here. This is disclosed as
  such in `reports/labeling_report.md`, not presented as an independent second model.
- Full historical block-range collection is impractically slow on free public RPC (~7.65 blocks/s
  single endpoint per prior measurement). The default config scopes collection to a modest recent
  range; widening it is a config change, not a code change, and is the user's call given the time
  cost.
