# Labeling and Agreement Report

Run `v2`. Values read from `data/human_reviews/frozen/v2_gold_review_validation.json` and the
frozen review file.

## Review outcome

| | |
|---|---:|
| Rows presented | 300 |
| **Reviewed** | **300** |
| **Accepted LLM label** | **300** |
| **Changed** | **0** |
| **Unresolved** | **0** |
| Rejected as malformed | 0 |

Validation checked every row (not a sample): valid decision, valid confidence, and — for every
`ACCEPT_LLM_LABEL` row — that `final_label` equals `llm_label`. No duplicates. The file was then
copied to a read-only frozen record.

| Artifact | Value |
|---|---|
| Frozen copy | `data/human_reviews/frozen/v2_gold_review_FROZEN.csv` |
| SHA-256 | `8a8ad2562bdd612399d53e224e65c0815ec72b24b140c4388907507fbf2b3f97` |

## Final label distribution (300 reviewed runtimes)

| Label | n |
|---|---:|
| B | 143 |
| U | 99 |
| R1 | 48 |
| R2 | 10 |

Confidence: 283 medium, 17 high.

## Agreement

**LLM–human agreement is 300/300 = 100% by construction: every row was accepted as proposed.**

This means no agreement statistic carries information here. Specifically:

- Cohen's kappa is **not computable** — it requires two independent label assignments, and there
  is one rubric output plus a blanket acceptance.
- No disagreement categories, no adjudication, and no common reasons for label change can be
  reported, because there were none.

The gold labels should therefore be described as **"rubric v3 labels ratified by a human
reviewer"**, not as independently derived human labels. Any downstream claim that the model was
evaluated against independent human judgement would be unsupported. This is the single most
important caveat attached to this dataset.

## Label provenance chain

1. Bytecode-derived evidence, incl. reachability + guard dominance (`data/evidence_packages/v2/`).
2. Rubric v3 proposal, prompt_version `v3`, model `claude-opus-5`
   (`dataset_pipeline/lib/llm_review_rubric_v3.py`); the reviewing model applied a documented,
   deterministic decision procedure rather than a live API call — no Anthropic key is configured
   in this environment.
3. Human ratification of all 300 rows (this report).
4. Propagation to 6 additional contracts sharing identical runtime bytecode; `label_origin` and
   `propagated_from` retained on every row. No propagation across similarity families.

## Rubric validation performed before review

- R1 rule: 25 of 99 R1 contracts independently re-derived; **25/25 confirmed** reachable,
  surviving strong-guard cutting, outside metadata. One systematic false-positive pattern was
  found and fixed (`calldata`+`sload` target provenance = caller-selected *stored* callee → R2,
  not R1), which moved 1 contract (Alchemy SemiModularAccount7702).
- Signer recovery: 150/150 agreement with an independent implementation; 118/120 on-chain
  designator confirmations, the 2 others explained as stale-nonce invalid authorizations.
- Documented-project sanity check: of 8 known implementations, 1 B, 1 R2, 6 U, **0 R1**.
