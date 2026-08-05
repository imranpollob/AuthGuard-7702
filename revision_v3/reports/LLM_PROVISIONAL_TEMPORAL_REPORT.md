# Provisional Temporal Report

**LABEL_SOURCE=LLM_PROVISIONAL. STATUS=PROVISIONAL_NOT_FOR_FINAL_CLAIMS.**

Built from the real (partial — see `TEMPORAL_COLLECTION_FINAL_STATUS.md`) Part 11 collection:
Ethereum (24,300/1,068,475 blocks scanned at time of sampling) and BNB (1,501-block pilot,
complete). Temporal data was **not** used for training anywhere in this pipeline (verified by
`test_temporal_data_never_referenced_by_training_scripts`).

## Sample construction (Part 12)

40 delegates sampled from 234 unique delegates discovered so far (208 Ethereum + 26 BNB),
prioritized: previously-unseen families first (up to 70% of the sample), then by
authorization-count (usage), across both available chains. One item
(`0x0000...0000`, a zero-address revocation) correctly had no runtime code and was excluded,
leaving **39 enriched items**.

## Results

| Subset | Count |
|---|---|
| All temporal items | 39 |
| Previously unseen families | 27 (69%) |
| Exact historical duplicates | 0 |
| Documented legitimate (present in `verified_legitimate_controls.csv`) | overlap not yet cross-referenced (concrete follow-up) |
| Unresolved proxies | not separately broken out this pass |
| UNCERTAIN | 1 |

Label distribution: **38 UNSAFE, 1 UNCERTAIN, 0 SAFE.**

## The central, honest finding

This sample is **overwhelmingly UNSAFE by provisional label (97%)** — starkly higher than
Gold-Dev (89% of binary items) or Gold-Test (95%). Two plausible, non-exclusive explanations,
neither confirmed:

1. Real-world, unfiltered EIP-7702 authorization traffic in this window may be dominated by
   automated/bot/drainer-style contract deployments rather than the curated, deliberately
   more-ambiguous Gold-Dev/Gold-Test samples.
2. The sample-construction prioritization (favoring high-authorization-count delegates) may
   itself bias toward mass-automated deployments, which are more likely to be simple,
   unrestricted forwarding/draining contracts than bespoke legitimate smart-account code.

**No AUPRC/AUROC could be computed** (`run_temporal_provisional.py` explicitly checks for
this and refuses to report a single-class metric) — 38/39 binary items share the same label,
so rank-based metrics are undefined. This is reported as a real limitation of the current
partial sample, not worked around.

## What this does NOT show

This is not evidence about steady-state, general EIP-7702 usage safety — it is a small,
partial-collection, usage-weighted sample from 2 of 7 target chains. Extending collection
(Ethereum/Base jobs remain running; Optimism/Arbitrum/Polygon/Gnosis pilots add more
diversity) is the concrete next step before drawing any broader conclusion.
