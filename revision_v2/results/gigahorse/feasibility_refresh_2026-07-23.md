# Gigahorse feasibility refresh — 2026-07-23

## Outcome

The earlier `feasibility.md` blocker is partially obsolete: this host now has a working
Docker Desktop 28.5.1 engine. The official Gigahorse repository documents a prebuilt
amd64 container path, so a bounded analyzer-cost experiment is now feasible without
building Souffle locally.

## Pinned upstream artifact

- Image: `ghcr.io/nevillegrech/gigahorse-toolchain`
- Resolved `latest` amd64 manifest:
  `sha256:f676ca8aaf88acd47be27ed1967acddc9c99acdd041b34e79472cfb028910743`
- Compressed layer size: approximately 1.18 GB
- The image has not yet been pulled in this refresh.

The digest, rather than the mutable `latest` tag, must be used for any reported run.

## Highest-ROI bounded experiment

After the active long-context study finishes:

1. prepare a deterministic, family-distinct sample stratified by label, fold, and opcode
   length;
2. run the pinned Gigahorse decompilation path with an explicit per-contract timeout;
3. report cold-start time separately from warm per-contract latency;
4. report median, tail latency, timeout rate, error rate, and peak container memory; and
5. compare information and latency boundaries without calling decompilation output an
   independent label validation.

This experiment can answer why a millisecond-scale learned triage layer may be useful
before deeper analysis. It cannot establish an end-to-end speedup over the exact Huang
et al. client rule unless that rule and its dependency paths are also reproduced inside
the pinned container.

## Scheduling decision

Do not pull or execute the 1.18 GB image while the CPU-bound long-context ablation is
running. This avoids resource contention in the primary contribution experiment.

