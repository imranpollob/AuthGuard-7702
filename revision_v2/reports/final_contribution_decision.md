# AuthGuard-7702 Final Contribution Decision

**Decision date:** 2026-07-17  
**Status:** COMPLETE — manuscript integration is now permitted, but no manuscript file was
modified during this decision.  
**Frozen-artifact status:** 144 frozen files verified unchanged.

## Executive decision

The final paper should present these three contributions:

1. **AuthGuard-7702 pre-authorization screening tool.** An integration-ready, bytecode-only
   CLI/Python tool that screens EIP-7702 delegate code before authorization and emits a risk
   score, validation-derived warning level, directly observed opcode evidence, model provenance,
   and structured JSON.
2. **Hierarchical full-bytecode opcode-sequence modeling.** A lightweight learned architecture
   that splits the complete opcode stream into chunks, encodes local patterns with dilated
   convolutions, and uses attention to aggregate contract-wide evidence. The selected sequence
   model significantly outperforms the strongest histogram+hashed-4-gram XGBoost baseline on
   clean and bounded adversarial conditions.
3. **AuthGuardBench-7702 and operational evaluation.** A task-aligned, dependence-aware benchmark
   with family and exact-duplicate controls, benign controls, matched-FPR policies, bounded
   transformations, per-row predictions, paired family-clustered uncertainty, and local runtime
   measurements.

The originally proposed multi-view, multi-task fusion architecture is **not** the final model.
The sequence-only architecture was selected by held-out validation AUPRC and was also strongest
on test. Transformation-consistent training and adaptive search remain supporting ablations and
stress tests; neither is a standalone contribution.

## Contribution 1 — AuthGuard-7702 screening tool

### Supported claim

> We present AuthGuard-7702, an integration-ready, bytecode-only tool for screening EIP-7702
> delegate contracts before authorization. It accepts runtime bytecode, a delegate address plus
> RPC endpoint, or an EIP-7702 authorization object and returns a risk score, a policy-derived
> warning level, directly observed security indicators, model provenance, and structured JSON.

### Implemented interface

- `scan-bytecode`: scores supplied runtime bytecode without network access;
- `scan-address`: retrieves delegate bytecode with `eth_getCode` and scores it;
- `scan-authorization`: extracts and screens the address in one authorization entry;
- Python `AuthGuardScorer` API;
- four warning outcomes derived from validation-negative thresholds at nominal 1%, 5%, and 10%
  FPR: `high`, `warning`, `caution`, and `low_observed_risk`;
- direct evidence for calls, state writes, delegation/proxy operations, token selectors, approval
  selectors, and code-lifecycle operations; and
- residual-risk notice: a low score is not a safety guarantee.

The tool is integration-ready, not a deployed wallet extension. No wallet user interface or
production RPC/cache service is claimed.

### Novelty boundary

The safe priority wording is: **"to our knowledge, the first EIP-7702-specific ML-based,
bytecode-only pre-authorization delegate-risk screener."** Do not claim the first EIP-7702
detector overall or the first ML bytecode security detector. Existing EIP-7702 work includes
transaction-history, decompilation, and cross-contract static analysis; existing bytecode ML
work addresses other vulnerability or phishing labels.

## Contribution 2 — hierarchical opcode-sequence architecture

### Final architecture

The selected model is `sequence_only`:

1. deterministic linear-sweep EVM opcode tokenization over the complete runtime bytecode;
2. 256-opcode chunks, up to 64 chunks;
3. 32-dimensional opcode embeddings;
4. two convolution layers, including a dilated convolution for local behavioral patterns;
5. max pooling within chunks;
6. learned attention across chunks; and
7. a calibrated binary delegate-risk head.

The largest benchmark contract contains 16,081 opcode tokens, below the 64x256=16,384-token
capacity, so no benchmark contract is prefix-truncated. For larger deployment inputs, chunks are
sampled evenly across the complete stream rather than taking only a prefix. First-STOP is not
used.

### Model selection

On seed 7702, mean validation AUPRC selected the sequence model without using test AUPRC:

| Candidate | Mean validation AUPRC |
|---|---:|
| sequence-only | **0.9482** |
| fusion + source-balanced augmentation | 0.9063 |
| fusion + transformation consistency | 0.8890 |
| fusion + multi-task objective | 0.8644 |
| fusion without auxiliary tasks | 0.8568 |
| n-gram neural branch only | 0.8350 |
| dense structural branch only | 0.7051 |

This supports a focused hierarchical sequence contribution. It does not support a claim that
feature fusion or the multi-task objective caused the gain.

### Three-seed stability

Values below are means across the five family-disjoint folds, followed by variation across the
three training seeds in parentheses where useful.

| Condition | Sequence AUPRC | Hist+n-gram XGB AUPRC | Sequence Recall@5% | Baseline Recall@5% |
|---|---:|---:|---:|---:|
| Clean M0 | **0.9309** (seed SD 0.0090) | 0.8276 | **0.8282** | 0.5822 |
| F200 | **0.9104** (seed SD 0.0070) | 0.5765 | **0.7235** | 0.1714 |
| M3+F200 | **0.9102** (seed SD 0.0137) | 0.5633 | **0.7189** | 0.1788 |

The direction is consistent for seeds 7702, 7703, and 7704 on every reported condition.

### Paired family-clustered evidence

The inferential comparison uses the primary seed, pooled held-out rows, identical folds and
partitions, validation-derived thresholds, and 10,000 family-clustered bootstrap replicates.

| Condition | Metric | Sequence | Baseline | Delta | 95% CI for delta |
|---|---:|---:|---:|---:|---:|
| Clean M0 | AUPRC | 0.8910 | 0.8339 | **+0.0571** | **[+0.0023, +0.1179]** |
| Clean M0 | Recall@5% FPR | 0.8391 | 0.6272 | **+0.2118** | **[+0.0952, +0.3390]** |
| Clean M0 | achieved FPR | 0.0341 | 0.0586 | **-0.0245** | **[-0.0466, -0.0047]** |
| F200 | AUPRC | 0.8828 | 0.5513 | **+0.3314** | **[+0.2561, +0.4089]** |
| F200 | Recall@5% FPR | 0.7538 | 0.1733 | **+0.5805** | **[+0.4678, +0.6794]** |
| M3+F200 | AUPRC | 0.8693 | 0.5439 | **+0.3254** | **[+0.2561, +0.4016]** |
| M3+F200 | Recall@5% FPR | 0.7552 | 0.2091 | **+0.5461** | **[+0.4365, +0.6435]** |

These results support "outperforms the strongest evaluated bytecode baseline" within the frozen
AuthGuardBench task, splits, and bounded transformations. They do not support universal semantic
robustness or superiority over tools trained for different labels.

### Benign-control qualification

On `benign_general`, the three-seed mean FPR at the validation-matched 5% policy is 0.0616 for
the sequence model and 0.0452 for XGBoost. For the primary-seed pooled comparison it is 0.0853
versus 0.0376; the paired delta is +0.0477 with CI [-0.0202, +0.1501], which does not exclude
zero. Therefore:

- do not claim lower benign-general false alerts;
- report the observed values as an operational tradeoff; and
- emphasize threshold selection and policy configurability in deployment.

## Contribution 3 — AuthGuardBench-7702 and operational evaluation

### Benchmark contents

- 3,082 total task-aligned rows;
- 2,280 primary rows: 727 malicious and 1,553 benign-cleared;
- 797 `benign_general` controls and 5 `benign_AA` case observations;
- 819 primary bytecode families;
- 2,528 unique bytecodes;
- 233 exact-duplicate groups containing 787 rows;
- exact duplicates constrained to one primary fold and one primary label;
- frozen family-disjoint outer folds;
- per-row prediction and threshold artifacts;
- F200 and M3+F200 donor-isolated transformations;
- direct benign controls and matched 1%, 5%, and 10% FPR policies; and
- 10,000-replicate paired family-clustered uncertainty.

Transformations are described only as bounded protocol transformations. Execution validation on
tested contracts does not establish universal semantic equivalence.

### Operational runtime

The selected 742,561-byte model was measured on Linux x86_64 with Python 3.12.12 and PyTorch
2.9.0, on CPU. The fixed 300-contract sample was scored for 10 passes (3,000 calls):

| Measurement | Value |
|---|---:|
| mean | **4.334 ms/contract** |
| p50 | 3.172 ms |
| p95 | **14.073 ms** |
| p99 | 16.906 ms |
| model load | 10.047 ms |
| model size | 742,561 bytes (about 0.743 MB) |

The timed scope includes local sequence preprocessing, model prediction, warning policy,
direct-evidence extraction, and construction of the JSON-ready result. It excludes process
startup, RPC/network latency, wallet integration, and UI rendering. Therefore call it **local
screening latency**, not end-to-end wallet latency.

## Rejected or supporting-only claims

1. **First-STOP:** empirical shortcut warning only; not a representation or contribution.
2. **Executable canonicalization:** rejected; do not revive.
3. **Multi-view superiority:** rejected; the full fusion model did not beat sequence-only.
4. **Multi-task benefit:** rejected as a performance claim; the auxiliary objective did not cause
   the selected result.
5. **Transformation-consistent training as a contribution:** rejected; consistency training is a
   supporting ablation and was inferior to sequence-only.
6. **Adaptive search as a contribution:** rejected; retain as a stress-test mechanism only.
7. **Lower benign-general FPR:** unsupported.
8. **End-to-end wallet latency:** unmeasured and unsupported.

## Final paper-ready contribution bullets

1. **AuthGuard-7702.** We introduce an integration-ready, bytecode-only pre-authorization
   screening tool for EIP-7702 delegate contracts that emits a risk score, validation-derived
   warning level, directly observed security indicators, and structured output for wallet and
   security-tool integration.
2. **Hierarchical opcode-sequence learning.** We design a lightweight full-bytecode model that
   learns local opcode patterns and aggregates contract-wide evidence through chunk attention.
   Under family-disjoint evaluation it significantly improves clean and bounded-adversarial
   detection over the strongest evaluated histogram+n-gram baseline.
3. **AuthGuardBench-7702 and operational evidence.** We provide a dependence-aware benchmark and
   evaluation framework with family and duplicate controls, benign controls, matched-FPR
   policies, bounded transformations, paired uncertainty, and local screening measurements. The
   selected model averages 4.334 ms per contract locally (p95 14.073 ms) with a 0.743 MB artifact.

## Final status

The three-contribution path is **SUPPORTED** with the precise boundaries above. Performance
claims may now be integrated into the manuscript from this report and its machine-readable
sources. No manuscript modification should reintroduce rejected claims or describe the runtime
as network-inclusive or end-to-end wallet latency.

