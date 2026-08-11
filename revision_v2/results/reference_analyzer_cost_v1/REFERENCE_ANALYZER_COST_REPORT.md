# Reference analyzer cost report v1

## Outcome

The pinned Gigahorse decompilation run completed for all 60 frozen inputs. Statuses were {"SUCCESS": 60}. The median internal successful analysis time was 2.687 s, p95 was 5.618 s, and the maximum was 28.067 s.

The serial warm bulk invocation took 210.590 s wall time (3.510 s per submitted input, including one container start and batch overhead). Peak sampled container memory was 262.9 MiB.

The separate cold invocation took 264.230 s and reached 10393.6 MiB sampled memory. It includes first-use Datalog compilation and is not pooled with warm per-contract timings.

## Frozen execution

- Image: `ghcr.io/nevillegrech/gigahorse-toolchain@sha256:f676ca8aaf88acd47be27ed1967acddc9c99acdd041b34e79472cfb028910743`
- One job; 120-second timeout per decompilation/analysis phase.
- Default decompilation, fallback, inlining, and signature-resolution settings.
- No downstream Gigahorse client rule was supplied.
- The warm bulk reused the Datalog binaries produced by cold compilation.

## Staged-triage interpretation

This measurement supports the operational motivation for a fast first-stage screen followed by selective decompilation. AuthGuard-Seq's separately measured complete local CPU path has a 2.942 ms median, whereas this pinned containerized decompiler run has a 2.687 s median internal analysis time.

The descriptive median ratio is 913x, but it is not a predictive-performance comparison or a claim that the two tools are interchangeable. Gigahorse reconstructs substantially richer program semantics; AuthGuard-Seq emits only a learned triage score.

## Boundary and limitations

- This is the official Gigahorse decompiler/lifter, not the exact Huang et al. client rule.
- Labels were used only for deterministic sampling and stratified summaries.
- Resource samples and wall time are host-specific; image pull time is excluded.
- Timeout and error rows remain in the denominator and are never silently dropped.
- The 60-family sample is deterministic and balanced, not a universal workload distribution.
- The result does not establish semantic equivalence, accuracy superiority, or end-to-end wallet latency.

## Manuscript decision

Add one bounded measured-cost paragraph and a limitations sentence only after the verifier passes. Preserve the current AuthGuard-Seq architecture and all existing predictive claims.
