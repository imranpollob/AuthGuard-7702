# Reference analyzer cost v1

This experiment measures the official pinned Gigahorse decompiler/lifter on a frozen,
family-distinct EIP-7702 delegate sample. It answers a deployment-cost question only; it
does not compare predictive accuracy or claim semantic equivalence with AuthGuard-Seq.

## Reproduction

From the repository root:

```bash
revision_v2/experiments/reference_analyzer_cost_v1/launch_image_pull_detached.sh
nohup setsid revision_v2/experiments/reference_analyzer_cost_v1/wait_image_pull_completion.sh \
  >> revision_v2/logs/reference_analyzer_cost_v1/image_pull_waiter.log 2>&1 < /dev/null &

revision_v2/experiments/reference_analyzer_cost_v1/launch_cost_study_detached.sh smoke
# Read smoke_waiter.log after the detached waiter reports completion.

revision_v2/experiments/reference_analyzer_cost_v1/launch_cost_study_detached.sh full
# The full worker resumes the passed smoke, runs cold and warm stages, analyzes,
# verifies, and builds the compact artifact manifest.
```

The runner refuses to overwrite incomplete stages. Preserve a failed stage under a unique
failure directory before a deliberate retry. Never delete or reuse a partially populated
cold cache as if it were fresh.

## Primary outputs

- `revision_v2/results/reference_analyzer_cost_v1/per_contract.csv`
- `revision_v2/results/reference_analyzer_cost_v1/summary.json`
- `revision_v2/results/reference_analyzer_cost_v1/REFERENCE_ANALYZER_COST_REPORT.md`
- `revision_v2/results/reference_analyzer_cost_v1/VERIFICATION.json`
- `revision_v2/results/reference_analyzer_cost_v1/ARTIFACT_MANIFEST.json`

The protocol and paper claim boundary are frozen in
`revision_v2/protocols/reference_analyzer_cost_v1.md`.
