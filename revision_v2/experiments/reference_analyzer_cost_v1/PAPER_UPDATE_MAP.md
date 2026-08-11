# Paper update map: reference-analyzer cost v1

No manuscript edit is authorized until
`revision_v2/results/reference_analyzer_cost_v1/VERIFICATION.json` exists with
`"status": "PASS"`.

## Evidence-to-text map

1. **Evaluation setup / timing paragraph (after the existing AuthGuard timing setup).**
   Identify the exact pinned Gigahorse digest, deterministic 60-family balanced sample,
   one-job serial run, 120-second timeout, and separation of image pull, cold invocation,
   and warm bulk execution.
2. **RQ4 operational viability.** Report warm status counts, median, p95, and maximum
   internal successful decompilation time, plus warm host wall time and peak sampled
   memory. Keep the existing AuthGuard latency table unchanged unless page budget supports
   a clearly separated second row group.
3. **Discussion.** Replace the current “no runtime advantage” sentence with the measured
   but bounded conclusion that millisecond-scale screening can prioritize which delegates
   receive a deeper, higher-cost analysis.
4. **Limitations.** State that the experiment executes the official decompiler/lifter, not
   the exact Huang et al. client rule; the tools return different information; results are
   host/version/workload specific; and neither image pull nor end-to-end wallet latency is
   part of the per-contract timing.
5. **Roadmap.** Mark Priority A complete and promote benign-delegate expansion to the next
   highest-ROI task.

## Forbidden interpretations

- AuthGuard and Gigahorse have equivalent outputs, accuracy, or semantics;
- AuthGuard is a drop-in replacement for static or symbolic analysis;
- the measured decompiler cost is the Huang et al. client-rule cost;
- the descriptive timing ratio is a controlled accuracy/utility comparison;
- the measurement establishes universal or end-to-end wallet latency.

## Architecture decision

The cost study cannot reopen architecture selection. The risk-focused aggregation study
returned `PARTIAL`: gated softmax improved over flat and mean controls under F200, but was
significantly worse than the current linear attention and moved attention toward benign
donor chunks. AuthGuard-Seq remains the promoted 30,050-parameter model.
