# Temporal Collection Methodology and Deployment Evaluation

## Temporal collection methodology

The target window is 2026-02-01 through 2026-06-30, but the current collection is incomplete
and must not be described as a seven-chain census. Ethereum was scanned sequentially with
checkpointed `eth_getBlockByNumber` calls. Its durable checkpoint covers 283,244 of 1,068,475
target blocks (26.5%), through 2026-03-12, and records 517,930 type-4 transactions and
1,233,059 authorization-list entries with zero block-scan RPC errors. Base's indexed discovery
path remains at zero committed pages because Blockscout's sustained queries time out. BNB,
Optimism, Arbitrum, Polygon, and Gnosis each have a completed bounded 1,501-block pilot. Exact
counts and artifact hashes are in `TEMPORAL_COLLECTION_FINAL_STATUS.md`.

The frozen Ethereum checkpoint contains 134,199 zero-address revocation entries and 740 unique
nonzero delegate addresses. The post-cutoff builder excludes revocations, recovers the actual
authorizing EOA from each usable authorization-tuple signature, retrieves runtime bytecode at
the first observed block, and audits exact hash and opcode-4-gram similarity against every
unique canonical runtime. Historical code is observed at end-of-block state, not transaction
index; same-block code changes therefore remain a stated limitation. It recovered 734 usable
signer/delegate pairs, of which 708 had historical runtime code. Six invalid signatures and 26
no-code observations were excluded. The recovered signer differed from the transaction sender
for 574 pairs, demonstrating why transaction sender cannot substitute for EIP-7702 authority.
Authority-aware DCRG extraction found 27 pairs with a fixed-caller guard matching that signer,
295 with a different fixed caller, and 28 with an EntryPoint guard; these are unlabeled feature
counts, not evidence that a match or mismatch is safe or unsafe.

## Provisional temporal evaluation

The new post-cutoff snapshot is deliberately **unlabeled and unscored**. A deterministic
score-blind sampler selects at most one address per exact-runtime family after excluding exact
and thresholded canonical-runtime matches. This yields 564 eligible exact-runtime families and
a locked sample of 150. The sampler refuses any input containing labels or model outputs. The
older 39-item LLM-provisional temporal exercise is retained only as a pipeline
diagnostic; its usage-prioritized sampling and nearly single-class generated labels are not
evidence for prevalence, accuracy, or generalization. Submission results require dual human
review, project-family provenance, complete related-family training holds, retraining, and a
paired evaluation fixed before any post-cutoff scores are examined.

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
