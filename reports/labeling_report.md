# Labeling Report

Status: **LLM preliminary review complete for run `v2` (752 contracts). Human review not yet
performed** — the queue is built and waiting at `data/human_reviews/v2_queue.csv`.

(An earlier `v1` 86-contract pilot exercised the same pipeline end to end and is preserved on
disk; this report describes the primary `v2` run.)

## Stage 3–4 inputs to labeling

- Families (`data/bytecode_families/v2_family_assignment.csv`): 752 screenable delegates, 669
  exact-bytecode groups (83 delegates are exact duplicates of another delegate's runtime code),
  clustering into **454 opcode-similarity families** at Jaccard ≥ 0.85 (407 singletons, 89.6%).
  The largest family has 212 members, all with byte-identical length (13,527 bytes) — consistent
  with a factory-deployed clone template (e.g. an immutable-constructor-argument pattern), not a
  clustering error; this is exactly the kind of case family-disjoint splitting exists to prevent
  from leaking across train/val/test.
- Evidence (`data/evidence_packages/v2/*.json`, index `data/evidence_packages/v2_evidence_index.csv`):
  64/752 (8.5%) have verified source on Sourcify; 8/752 match a documented known project
  (ZeroDev Kernel v3.3, OKX SmartWalletEntry, Uniswap Calibur v1.1.0, Ambire EIP7702Account,
  MetaMask StatelessDeleGator, Coinbase EIP7702Proxy, Biconomy Nexus v1.3.1, Alchemy
  SemiModularAccount7702).

## How "sending to an LLM" was done in this run

Same method as the `v1` pilot and disclosed identically here: no Anthropic (or other) API key is
configured for programmatic use in this environment. The review was performed by the assistant
(Claude Sonnet 5) applying the explicit, documented decision rubric
(`dataset_pipeline/lib/llm_review_rubric.py`, prompt_version `v1`) to each contract's Stage-4
evidence fields — not 752 independent free-form model calls. See that module's docstring for why
the rubric almost never emits R1 given evidence with no guard/reachability analysis.

## Results

| proposed_label | count |
|---|---:|
| R2 | 524 |
| B | 205 |
| R1 | 23 |
| U | 0 |

| confidence | count |
|---|---:|
| low | 521 |
| medium | 193 |
| high | 38 |

All 23 R1 contracts were flagged by the same rule as the pilot's single R1 case: an apparent
SELFDESTRUCT opcode with no admin/ownership selector or DELEGATECALL detected anywhere in the
linear-sweep disassembly, and all 23 carry `confidence=low` with the disassembler-artifact
uncertainty attached (SELFDESTRUCT counts from a non-CFG-validated sweep can come from misdecoded
data bytes rather than reachable code). None of the 23 matches a known documented project. These
are flagged, not resolved — exactly the set human review should look at first.

## Outputs

- `data/llm_reviews/v2/{chain}_{address}.json` — one record per contract (evidence_hash,
  evidence_path, prompt_version, model_id, raw_response, parsed_response).
- `data/llm_reviews/v2_review_index.csv` — flat index.
- `data/human_reviews/v2_queue.csv` — 752 rows, LLM proposal shown, decision/final_label/
  final_confidence/comment/corrected_risk_categories columns blank, awaiting the human reviewer.

## Remaining steps (require the user)

1. Fill in `decision` (`ACCEPT_LLM_LABEL` / `CHANGE_LABEL` / `UNRESOLVED`), and for
   `CHANGE_LABEL`, `final_label` + `final_confidence`, for each of the 752 rows in
   `data/human_reviews/v2_queue.csv`. Given the volume, prioritizing the 23 R1 rows and a sample
   of the largest families (e.g. the 212-member FAM00016) is a reasonable way to triage if
   reviewing all 752 individually isn't practical — `bytecode_family_id` and
   `llm_risk_categories` in the queue support sorting/grouping for that.
2. Run `python3 dataset_pipeline/scripts/07_merge_human_reviews.py` to validate and merge into
   `data/human_reviews/v2_completed.jsonl`. It reports exactly which rows are still incomplete
   or invalid rather than silently dropping them, and can be run repeatedly as review progresses.
3. Once every screenable row is covered, `08_build_gold_dataset.py` (Stage 7) assembles the gold
   dataset and splits; `09_train_models.py` (Stage 8) and `10_coverage_deferral.py` (Stage 9) run
   after that.

No accepted/changed/unresolved counts, agreement statistics, or common reasons for label changes
are reported yet because **zero rows have been human-reviewed in this run** — those numbers will
be added here once `v2_completed.jsonl` exists, not fabricated in advance.
