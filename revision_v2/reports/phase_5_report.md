# Phase 5 Report — Reference Analyzer Decision Fork

## Verdict

**Option B: BLOCKED.** The full Gigahorse/Souffle/Datalog reference pipeline was not executed.

## Evidence

This environment has no Souffle engine or Docker/Podman/Colima runtime. More importantly, the
source artifact ships client rules whose `analyze.dl` includes four Gigahorse `clientlib/*.dl`
files that are absent. Reconstructing the toolchain requires installing a container runtime or
building Souffle, fetching the full Gigahorse toolchain, reconciling versions, and validating
the decompiler-to-Datalog path. Estimated remaining work is 1.5--2.5 working days with a
container runtime and higher risk without one, beyond the fixed phase time box.

The bounded fallback reads shipped intermediate rule facts only. All 727/727 task-aligned
positives have at least one fact row, while 4/1,553 weak negatives do. Because these labels were
defined from the same rule output, this is provenance confirmation and circularity evidence,
not independent validation or an analyzer comparison.

## Manuscript consequence

AuthGuard is not claimed to beat, replace, or accelerate the full reference pipeline. The
methods are positioned as complementary and consume different information. No runtime,
coverage, accuracy, or superiority claim against Gigahorse/Datalog is supported.

## Integrity

No frozen artifact was modified and no completed experiment depends on this phase.
