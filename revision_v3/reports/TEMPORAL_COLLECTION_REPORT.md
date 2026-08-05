# Temporal Collection Report — Phase 2, Part 8

## Infrastructure built

`revision_v3/src/temporal/`:
- `rpc_client.py` — minimal, dependency-free JSON-RPC client, per-chain endpoint config for
  all 7 historical chains, retry/backoff, no batching (per prior-session finding that
  `eth.drpc.org` returns HTTP 500 on batched requests), and a `find_block_by_timestamp`
  binary-search date→block resolver (a handful of RPC calls, not a full scan — this is the
  "date-to-block resolution capability" the prior repository audit flagged as entirely
  absent).
- `collector.py` — sequential block scanner: for each block, fetches full transactions,
  filters `type == "0x4"` (EIP-7702 SetCode transactions), extracts every entry in each
  transaction's `authorizationList` (delegate address, per-authorization `chainId`, nonce,
  tx hash, block number, block timestamp), appends to a per-chain CSV, and checkpoints every
  50 blocks.
- `checkpoint.py` — JSON checkpoint per (chain, run_id); resuming re-reads the last completed
  block and continues from there, never reprocessing a completed block.
- `enrich.py` — for each unique delegate address discovered: `eth_getCode`, SHA-256 of the
  runtime bytecode, opcode-4-gram extraction (`revision_v3/src/features`, the same disassembler
  used throughout this project), exact-hash lookup against the canonical
  `authguardbench_7702_v2.csv.gz`, and Jaccard-similarity comparison against one representative
  bytecode per historical `family_id` (790 families) at the same 0.85 threshold the canonical
  project freezes for family membership — classifying each new delegate as an **exact
  historical duplicate**, a **member of an existing family** (similarity ≥ 0.85), or a
  **previously unseen family**.

This closes every gap the prior repository audit (`PROJECT_AUDIT_FOR_TPS.md` §8) identified as
missing: authorization-list discovery (previously: none existed, only `eth_getCode` on
pre-known addresses), timestamp/block-number recording (previously: none), and an incremental
family-classifier (previously: batch-only, no persisted signatures to query against).

## Pilot: real data, both chains, within the actual Feb 1 – Jun 30 2026 target window

Given the free public RPC's lack of batching (confirmed again this session) and observed
throughput of ~7 blocks/s on Ethereum, scanning the **full** 5-month target window
(~3.2M blocks on Ethereum alone) is a multi-day, multi-chain background operation, not
something to run to completion inside this session. Per the audit brief's own instruction
("before running a massive collection, perform a pilot... If the pilot is successful,
continue... using background workers"), this section reports a **real, honest, bounded
pilot** — 300 consecutive blocks on each of Ethereum and Base, starting at the exact first
block of the target window (found via `find_block_by_timestamp`, not estimated) — rather than
fabricating full-window numbers.

| | Ethereum | Base |
|---|---:|---:|
| First block of window (2026-02-01 00:00 UTC) | 24,358,293 (actual timestamp 00:00:11 UTC) | 41,557,327 (actual timestamp 00:00:01 UTC) |
| Blocks scanned | 300 | 300 |
| Data source | `eth.drpc.org` (primary) | `base.drpc.org` (primary — see note below) |
| Type-0x4 (EIP-7702) transactions found | **270** | **113** |
| Authorization-list entries found | **276** | **113** |
| Unique delegate addresses | **32** | **12** |
| Unique runtime bytecode hashes among them | 32 | 12 |
| Exact historical duplicates (bytecode already in the canonical v2 benchmark) | 0 | 0 |
| Matches to an existing historical family (similarity ≥ 0.85) | **14** | **7** |
| Previously unseen families | **18** | **5** |
| Collection throughput (this run) | 6.91 blocks/s | 1.40 blocks/s (rate-limited, see below) |
| RPC errors encountered | 0 | 2 (both recovered via checkpoint/resume) |

Full raw and enriched data: `revision_v3/temporal/raw/pilot_v1_{ethereum,base}_authorizations.csv`,
`pilot_v1_{ethereum,base}_enriched.csv`; checkpoints:
`revision_v3/temporal/checkpoints/pilot_v1_{ethereum,base}.json`.

### What the pilot demonstrates

1. **EIP-7702 usage is active and substantial** at the start of the target window — 270
   authorization transactions in 300 Ethereum blocks (~1 hour of blocks) is far from rare.
2. **Known legitimate delegates dominate the traffic observed**: of the 44 total unique
   delegates across both chains, several resolve via exact/near-exact family match (similarity
   1.0) to addresses already in this project's own curated legitimate-project list
   (`revision_v3/external_controls/`) — e.g. `0x63c0c19a...` (MetaMask StatelessDeleGator,
   family `F00215`, similarity 1.000, observed on **both** chains), `0xd6cedde8...` (ZeroDev
   Kernel), `0x69007702...` (OKX SmartWalletEntry). This is read-only, incidental corroboration
   from live chain data, not a claim this project fabricated — it emerged directly from the
   pilot.
3. **A revocation edge case surfaced and is handled correctly, but is worth flagging**: one
   Ethereum authorization pointed at `0x000...000` (the zero address — EIP-7702's
   delegation-clearing mechanism), which the enrichment pipeline correctly recorded as
   zero-length code / similarity 0 / "previously unseen family" — technically correct but
   semantically it is a *revocation*, not a new delegate implementation. A production run
   should special-case the zero address as "revocation," not silently count it as a novel
   family.
4. **Checkpoint/resume works under real failure conditions, not just in a unit test**: the
   Base scan hit two transient failures (see below) across three separate invocations of the
   same command and resumed correctly each time with zero duplicate or skipped blocks.

### A real infrastructure finding: `base-rpc.publicnode.com`'s free tier prunes old history

The first Base pilot attempt failed immediately: `base-rpc.publicnode.com` returned
`{"code": 4444, "message": "pruned history unavailable"}` for a block ~7.7M behind its current
head. `base.drpc.org` served the identical historical block without issue. `rpc_client.py`'s
endpoint order for Base was corrected (drpc.org first, publicnode.com as fallback) based on
this observed, not assumed, constraint. The Base run also hit two `HTTP 429 Too Many Requests`
errors under sustained sequential polling; both were resolved simply by re-invoking the same
command (checkpoint resumed cleanly) with a small inter-block delay (0.3–0.6s), at the cost of
lower effective throughput (1.4 blocks/s vs. Ethereum's 6.9 blocks/s that run). **Any full-scale
collection must budget for this**: Base produces blocks roughly 6× faster than Ethereum, so a
naive equal-effort scan would fall further and further behind on Base specifically.

## What a full Feb 1 – Jun 30 2026 collection would require

Extrapolating directly from the measured pilot throughput (not re-estimated from stale prior
figures):

| Chain | Approx. blocks in window | At measured pilot throughput | Estimated wall time (single-threaded, this RPC tier) |
|---|---:|---:|---:|
| Ethereum | ~1.08M (12s/block × 150 days) | 6.91 blk/s | ~1.8 days |
| Base | ~6.45M (2.01s/block, derived from the observed gap between the 2026-02-01 block and the chain's current head at pilot time, × 150 days) | 1.40 blk/s (rate-limited) | **~53 days at this throughput** — impractical without either a higher-tier endpoint, multiple parallel API keys, or an indexed data source |

**Base is the binding constraint, not Ethereum.** A full historical scan of Base at
block-by-block granularity on free public RPC is not practical. Recommended next steps, in
order of preference: (a) find a free or low-cost indexed data source for type-0x4 transactions
specifically (e.g. a block-explorer API with a "transactions by type" filter, if one becomes
available with a free tier) rather than scanning every block; (b) parallelize block fetches
across multiple public endpoints/IPs with careful rate-limit budgeting; (c) accept a lower
sampling rate (e.g. every Nth block) for Base specifically, with the resulting coverage gap
explicitly reported rather than silently accepted. None of these were implemented in this
phase — Part 8's mandate was infrastructure + a pilot, not the full collection, and the pilot's
own numbers show why proceeding straight to a full run without addressing the Base throughput
problem would silently produce very poor Base coverage.

## Explicit non-claims

- **No historical/label collection was performed on the temporal population.** The 44 pilot
  delegates were fetched, hashed, and family-matched only — no human or model label was
  attached to any of them, satisfying the phase's stop condition.
- **The pilot's 300-block window is not the full Feb–Jun 2026 window** — it is the first ~1
  hour (Ethereum) / ~10 minutes (Base, at its faster block time) of that window, used to
  validate the infrastructure end-to-end with real data and real failure modes. Extrapolated
  full-window numbers above are estimates from measured throughput, not claims of completed
  collection.
