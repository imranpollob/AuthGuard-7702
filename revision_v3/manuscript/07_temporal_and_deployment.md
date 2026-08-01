# Temporal Collection Methodology and Deployment Evaluation

## Temporal collection methodology

Target window 2026-02-01 through 2026-06-30, real-world EIP-7702 authorization traffic across
7 chains. Ethereum: sequential `eth_getBlockByNumber` scan (proven, checkpointed, resumable),
measured ~6.9 blocks/sec on free public RPC infrastructure — a real throughput ceiling this
project documents rather than works around. Base: an indexed-transaction-API approach was
investigated and built specifically to avoid a naive sequential scan (per methodological
concern about wasting RPC budget on 99%+ non-EIP-7702 blocks), using Blockscout's
`advanced-filters` endpoint to cheaply discover which blocks contain type-4 transactions
before fetching only those blocks in full — a genuine efficiency contribution, though its
sustained reliability under this project's own testing proved poor (see
`TEMPORAL_COLLECTION_FINAL_STATUS.md`). 5 additional chains (BNB, Optimism, Arbitrum,
Polygon, Gnosis) received real, bounded pilot scans. **[PROVISIONAL/PARTIAL — see the status
report for exact, real block counts and authorization-entry counts at time of writing; the
Ethereum and Base collections remain running as checkpointed background jobs and should be
re-queried before finalizing any temporal claim.]**

Delegate enrichment (`temporal.enrich.enrich_authorizations`) deduplicates delegate
addresses, retrieves runtime bytecode, and classifies each against the frozen historical
population by exact hash and opcode-4-gram family similarity (Jaccard ≥ 0.85, matching the
canonical project threshold) — correctly distinguishing zero-address revocations (no runtime
code) from real delegates.

## Provisional temporal evaluation

39 real, enriched delegates (Ethereum + BNB), prioritized toward previously-unseen families
(69% of the sample) and high-authorization-count delegates. **97% provisional-UNSAFE** — a
striking, single-class-dominated finding reported honestly (no AUPRC could be computed) with
two candidate, unconfirmed explanations discussed in `LLM_PROVISIONAL_TEMPORAL_REPORT.md`
(automated/bot-dominated real-world traffic; or a usage-count sampling bias). This is
explicitly flagged as not representative of steady-state EIP-7702 usage safety without
further, broader collection.

## Deployment evaluation

Real, repeated-measurement benchmarks on this project's own hardware (NVIDIA RTX 2080 SUPER,
PyTorch 2.9.0+cu128): `authguard_sequence_dense` — 97,646 parameters, 397,988-byte
checkpoint, 2.83ms median / 3.44ms p99 CPU forward latency, 125.7 items/sec single-process
CPU throughput. ONNX export succeeded with numerical parity (max abs diff 4.17e-7 vs. native
PyTorch) but was *slower* on CPU (4.99ms median) than native PyTorch in this configuration —
reported as measured, contradicting a naive "ONNX is always faster" assumption. Full
environment/hardware disclosure and the sequence-only reference's numbers in
`DEPLOYMENT_EVALUATION_REPORT.md`; do not compare these latencies to any other paper's
numbers without matching hardware.
