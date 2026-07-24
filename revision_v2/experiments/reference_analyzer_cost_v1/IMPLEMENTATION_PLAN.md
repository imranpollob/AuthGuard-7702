# Reference analyzer cost experiment v1

## Reviewer question

Why use a learned bytecode triage layer instead of running the source study's deeper
decompiler/analyzer path before every EIP-7702 authorization?

## Scope

Measure the official pinned Gigahorse decompilation path on a deterministic 60-contract
sample. This is a latency, failure, and resource-boundary experiment. It is not an
independent label-validation experiment and is not described as the exact Huang et al.
client rule unless that client is separately reproduced.

## Frozen sample

- 2 source labels x 3 source-length strata x 5 outer folds x 2 contracts = 60.
- Length strata: at most 2,048; 2,049--4,096; above 4,096 opcode tokens.
- Every label/length/fold cell is balanced, and families are unique across the complete
  sample.
- Deterministic selection uses a fixed SHA-256 ordering, not model scores.
- The sample manifest retains provenance, fold, label semantics, byte length, opcode
  count, and family ID.

## Container

- Official image:
  `ghcr.io/nevillegrech/gigahorse-toolchain`
- Pinned amd64 digest:
  `sha256:f676ca8aaf88acd47be27ed1967acddc9c99acdd041b34e79472cfb028910743`
- Record image configuration and resolved repository digest with the output.

## Measurements

1. image-pull time and size, reported separately and excluded from per-contract latency;
2. one cold single-contract invocation;
3. warm bulk analysis with explicit job count and per-contract timeout;
4. wall time, CPU time, peak container memory, and output size;
5. median, p90, p95, and maximum per-contract time when exposed by `results.json`;
6. `TIMEOUT`, `ERROR`, and successful-decompilation counts by label and length stratum.

## Execution rule

Do not pull or run the container while the long-context ablation is active. Long Docker
operations use the same detached-launcher plus completion-waiter pattern.

## Claim boundary

A successful run may support a staged-analysis motivation: millisecond-scale learned
triage can prioritize which delegates receive deeper decompilation. It does not prove
that AuthGuard is semantically equivalent to, more accurate than, or a drop-in
replacement for the reference analyzer.
