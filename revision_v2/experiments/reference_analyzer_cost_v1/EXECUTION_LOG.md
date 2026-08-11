# Reference-analyzer cost v1 execution log

## 2026-07-25/26: pre-experimental smoke attempts

### Attempt 1 — harness failure exposed

- The pinned image had been pulled and its digest verified.
- The smoke invoked `sample_048.hex` with one analysis job, a 30-second per-contract
  timeout, a fresh isolated cache, and no downstream client.
- Docker statistics recorded 79 usable samples and approximately 3.9 GiB peak memory
  before termination.
- The runner treated a nonzero `docker wait` CLI status as a lifecycle exception before
  capturing `docker logs` or final container inspect state. Therefore the underlying
  container failure cannot be classified from this attempt.
- The incomplete stage and two generated Souffle C++ files are preserved under
  `results/reference_analyzer_cost_v1/failed_attempts/` and excluded from scientific
  summaries.

Action: reorder failure handling so logs and inspect state are captured before interpreting
the container exit. Never overwrite the failed attempt.

### Attempt 2 — missing local image

- Before a second container was created, the exact image digest was no longer present in
  the local Docker image store.
- The runner stopped at the image-provenance gate. No analyzer observation was produced.
- Other pre-existing Docker images remained present, so this was not a complete image-store
  reset.

Action: preserve the first successful pull packet, repeat the exact-digest pull as a
detached setup job, and rerun the corrected smoke only after the new pull waiter reports
success.

### Attempt 3 — manifest/configuration digest distinction

- The repull resolved the frozen repository manifest digest to image configuration ID
  `sha256:9c1e...` and retained the required `repo@sha256:f676...` repository digest.
- The setup gate incorrectly expected Docker's local configuration ID to equal the remote
  manifest digest and stopped before container creation.

Action: freeze and validate both identifiers according to their distinct meanings. This is
a provenance-gate correction; it does not modify the sample, analyzer flags, timeout, or
reported measurements.

### Attempt 4 — smoke passed

- Both frozen Docker identifiers passed.
- The isolated `sample_048.hex` smoke completed with one result and no error/timeout meta
  flags.
- Empty-cache container wall time was 261.733 seconds, dominated by compilation; the
  contract's exposed internal timing totaled approximately 1.330 seconds.
- The isolated smoke cache contains the compiled default, scalable-fallback, and inliner
  executables. Smoke outputs remain excluded from scientific summaries.

Action: launch the detached full sequence. It resumes the passed smoke, performs the
predeclared cold invocation with its own initially empty cache, then runs the 60-input warm
serial bulk with binary reuse before analysis and fail-closed verification.

## Scientific status

The frozen 60-family warm run is the only primary cost observation. No manuscript timing
claim is authorized until its verifier passes.
