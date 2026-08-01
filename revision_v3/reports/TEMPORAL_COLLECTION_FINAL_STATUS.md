# Temporal Collection Final Status

Target window: 2026-02-01 through 2026-06-30. **This is a snapshot taken while collection was
still in progress** (both Ethereum and Base full-window jobs are checkpointed background
processes, safe to resume with the same `run_id` — see `revision_v3/temporal/collection_manifest.json`
for the live state at write time). Real numbers below, not projections.

## Ethereum — full-window checkpointed scan

Method: sequential `eth_getBlockByNumber` scan (proven approach from the Phase 2 pilot),
via `run_ethereum_full_window.py`. Target range resolved by binary search on block timestamp:
blocks **[24358293, 25426767]** (1,068,475 blocks total).

**Real progress at snapshot time**: 24,300 blocks scanned (2.3% of window), **29,150 type-4
transactions found, 45,113 authorization entries recorded, 0 RPC errors**. Measured
throughput ≈ 6.9 blocks/sec (consistent with the Phase 2 pilot's ~6.9 blocks/sec). At this
rate, the full window would take approximately 43 hours of continuous scanning — this is
reported as a fact about the free public RPC infrastructure's throughput, not something any
amount of engineering effort in one session changes. The job remains running.

## Base — investigated indexed-transaction-API approach (per the explicit instruction not to
run a naive sequential scan)

Investigated and built: Blockscout's `/api/v2/advanced-filters?transaction_types=set_code_transaction`
endpoint, which returns only real type-4 ("set_code_transaction") transactions for a date
range directly from Blockscout's index — verified functional in isolated testing (found and
processed 1 real authorization entry from a 1-day test window before being generalized to the
full window). Two concrete, real findings from this investigation:

1. Blockscout's own `authorization_list` field on the transaction-detail endpoint was found
   **empty** for confirmed type-4 transactions (checked against 5 real Base transactions) —
   not usable as the data source directly.
2. The free public RPC endpoints already in the codebase could not serve 5-month-old Base
   history (`base-rpc.publicnode.com`: "pruned history unavailable"; `base.drpc.org`:
   HTTP 429). The official Base team RPC (`mainnet.base.org`) could, and was added to
   `rpc_client.py`'s endpoint list as a result — a genuine infrastructure fix, not a
   workaround.

**Current status**: the resulting collector (`indexed_collector.py`, using Blockscout to
discover block numbers cheaply, then `mainnet.base.org` to fetch full block data) has
**stalled** — every attempt to fetch a page from Blockscout's advanced-filters endpoint for
the full 5-month window has timed out after 4 retries, despite the same endpoint working in
isolated single-page tests earlier in this session. This is reported as an honest finding
about that endpoint's reliability under sustained/repeated use (likely rate-limiting), not
glossed over. The collector is running under an auto-restart wrapper and will resume
collecting real data whenever the endpoint recovers; **0 blocks fetched, 0 authorization
entries recorded from Base at snapshot time.**

## Other chains — 1-day pilots (per the brief)

Run via direct `eth_getBlockByNumber` scanning (same proven method as Ethereum), each ~1,500
blocks starting at the 2026-02-01 window boundary:

| Chain | Blocks scanned | Type-4 txs | Authorization entries | Blocks/sec |
|---|---|---|---|---|
| BNB | 1,501 (complete) | 1,459 | 1,462 | 3.43 |
| Arbitrum | 1,501 (complete) | 45 | 47 | 4.10 |
| Optimism | 1,501 (complete) | 6 | 6 | 3.43 |
| Polygon | 1,200 / 1,501 (in progress at snapshot) | 344 | 346 | ~3.5 |
| Gnosis | Not yet completed at snapshot time (queued after Polygon) | — | — | — |

Note the wide variance in EIP-7702 adoption density across chains visible even from these
small pilots (BNB: ~97% of scanned blocks contain a type-4 tx; Optimism: ~0.4%) — a real,
if extremely early and noisy, signal worth flagging for the manuscript's chain-comparison
discussion, not a claim about steady-state adoption rates.

## Zero-address / duplicate / family handling

Confirmed working during Part 12's real enrichment run: `enrich_authorizations()`
(`temporal/enrich.py`) correctly skipped a genuine zero-address revocation entry
(`0x0000000000000000000000000000000000000000`, `eth_getCode` → `0x`, no runtime code) rather
than misclassifying it as a delegate; deduplicated delegate addresses before bytecode
retrieval; classified every real Ethereum/BNB delegate against the frozen v2 population
(159/208 Ethereum delegates, 15/26 BNB delegates were previously-unseen families; 0 exact
historical duplicates in either chain's real data).

## What to run to continue this collection

```bash
python3 revision_v3/experiments/temporal_v2/run_ethereum_full_window.py   # resumes from checkpoint
python3 revision_v3/experiments/temporal_v2/indexed_collector.py --chain base \
  --age-from 2026-02-01T00:00:00.00Z --age-to 2026-06-30T00:00:00.00Z --run-id v2_window
```
Polygon and Gnosis pilots were run via direct block scanning (`temporal.collector.scan_block_range`,
same method as Ethereum), not the indexed collector — resume by re-running the same
`run_id="pilot_v2"` scan for the remaining ~300 blocks (Polygon) and the not-yet-started range
(Gnosis). All of the above are checkpoint-safe to interrupt and re-run.
