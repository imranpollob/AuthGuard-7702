# Reference-analyzer cost protocol v1

Status: frozen before the first Gigahorse decompilation run on 2026-07-25.

## Research question

What latency, failure, and resource boundary does the official Gigahorse decompilation path
exhibit on a deterministic EIP-7702 delegate sample, and does that boundary support using a
millisecond-scale bytecode model as a triage stage before deeper analysis?

This experiment does not compare predictive accuracy with AuthGuard and does not reproduce
the exact Huang et al. client rule. It measures the official decompiler/lifter on the same
kind of runtime bytecode that underlies that rule.

## Frozen sample

- `revision_v2/experiments/reference_analyzer_cost_v1/sample/sample_manifest.csv`
- SHA-256: `26dbccb92a8de05e1b0e57440acbfd2e6f7a36b202eed71aa9b11d994bd1a794`
- 60 distinct bytecode families: 2 source labels x 3 opcode-length strata x 5 folds x
  2 contracts.
- Selection is deterministic and score-independent.
- Cold sample: `sample_021.hex`, the unique deterministic first row closest to the sample's
  median opcode count (2,917 versus median 2,977.5).

Labels are used only to stratify failure and latency summaries. They do not enter execution
or model comparison.

## Frozen toolchain

- Official image: `ghcr.io/nevillegrech/gigahorse-toolchain`
- Pinned amd64 manifest digest:
  `sha256:f676ca8aaf88acd47be27ed1967acddc9c99acdd041b34e79472cfb028910743`
- Resolved image configuration ID:
  `sha256:9c1e6a36fa9fa80e756f67897c4b7003f455bb1e9a7a86233d619555aa20848f`
- Invoke the image's `gigahorse.py` decompilation path without an additional client.
- Preserve default shrinking-context analysis, scalable fallback, inlining, and signature
  resolution.
- Per-contract timeout: 120 seconds, the official documented default.

The image pull is measured separately and excluded from per-contract latency.

## Runs

1. **Interface smoke:** inspect `gigahorse.py --help` inside the pinned image and run one
   small contract with a 30-second timeout in an isolated smoke directory. Smoke results are
   never reported as experimental observations.
2. **Cold invocation:** run only `sample_021.hex` in a fresh working directory and initially
   empty persistent compilation cache, using one job. This includes container startup and
   first-use Datalog compilation but excludes image pull.
3. **Warm serial bulk:** run all 60 contracts with one job, fresh per-contract working
   directories, and the cache populated by the cold invocation. Use `--reuse_datalog_bin`
   only after verifying that the cold cache contains the required compiled binaries.

The cold sample remains in the 60-row warm bulk result; cold and warm numbers answer
different questions and are not pooled.

## Measurements

- host wall time for the image pull, cold invocation, and complete warm bulk run;
- image configuration, resolved digest, and local image size;
- per-contract disassembly, decompilation, inlining, client, and total analysis time from
  `results.json` when exposed by the pinned image;
- success, `TIMEOUT`, and `ERROR` counts overall and by source label and length stratum;
- median, p90, p95, and maximum successful total time;
- peak container memory and sampled container CPU percentage from `docker stats`;
- output/work/cache bytes after each stage.

Container resource sampling is observational and host-specific. It is not a hardware-
independent benchmark.

## Verification

- The exact repository digest and its resolved image configuration ID match the frozen
  values; these are distinct Docker identifiers.
- Every `.hex` input decodes exactly to the corresponding frozen benchmark runtime
  bytecode; computed file/raw-byte hashes are persisted in the result packet.
- Warm `results.json` contains exactly 60 unique filenames, including explicit error or
  timeout rows.
- Every result joins one-to-one to the sample manifest.
- Successful timing components are finite and nonnegative.
- Raw stdout/stderr, `results.json`, resource samples, configuration, summaries, and hashes
  are retained.

## Manuscript decision

The evidence merits a bounded staged-analysis paragraph only if the pinned run is complete
and verifiable. Report measured values without claiming:

- that AuthGuard is equivalent or superior to Gigahorse;
- that this is the exact Huang et al. client-rule latency;
- that the two tools return the same information;
- end-to-end wallet latency; or
- a universal decompiler cost across hardware, versions, or contracts.
