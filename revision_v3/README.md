# AuthGuard-7702 — Revision v3 (Reviewer-Readiness Workspace)

Independent, from-scratch experimental workspace. Revision v2 (`revision_v2/`) remains the
frozen reference implementation and is never modified by anything under this directory.

## Rules

- No file under `revision_v2/`, `paper_build/`, `pipeline/`, `results/`, `reports/`,
  `capability_dataset.csv`, or `family_assignment_frozen.csv` is ever written by code in
  this directory. This is enforced by an automated test
  (`tests/test_no_v2_writes.py`) and by the frozen-hash guard
  (`revision_v2/experiments/common/frozen.py verify`), run before and after every session.
- No code was merged, cherry-picked, or copied from Git branch `revision-3`. Every source
  file under `revision_v3/src/` is a new, independent implementation. Branch `revision-3` was
  read only during the prior audit (`PROJECT_AUDIT_FOR_TPS.md`) to understand what
  capabilities it implements — none of its code was reused.
- Revision v2's canonical dataset, family IDs, and fold IDs are treated as **immutable
  inputs**. Revision v3 does not regenerate labels, family assignments, or fold membership.
  It re-derives features and re-trains models on top of the same frozen split.

## Directory layout

```
revision_v3/
├── configs/            canonical input paths + experiment configs (read-only paths into revision_v2/)
├── data/                input_manifest.json (hashes/counts of canonical v2 inputs); no raw data copied here
├── src/
│   ├── data/            dataset loader + validation (row/label/family/fold counts, hash guard)
│   ├── features/        independent EVM disassembler, tokenizer, chunking, histogram/n-gram/structural features
│   ├── models/          controlled model architectures (flat CNN, hierarchical chunk models, reference, exploratory hybrids)
│   ├── training/         training harness (folds, seeds, calibration, thresholds)
│   ├── evaluation/       metrics, aggregation, bootstrap
│   ├── analysis/         DCRG schema + versioned protocol-actor registry
│   ├── robustness/       independent Flood-200% reimplementation with donor isolation
│   └── reporting/        table/report generation helpers
├── experiments/          experiment drivers (one subdir per experiment group)
├── results/              CSV/JSON outputs (fold/seed results, summaries, predictions, bootstrap CIs)
├── tests/                automated test suite (pytest)
├── logs/                 run logs
└── reports/              markdown reports (this phase's deliverables)
```

## Canonical inputs (immutable, read-only)

- `revision_v2/data/authguardbench_7702_v2.csv.gz` — dataset, labels, `family_id`, `fold_id`
- Population must remain: 2,190 primary rows (727 positive / 1,463 negative), 790 families

See `revision_v3/data/input_manifest.json` for exact hashes and counts, and
`revision_v3/src/data/loader.py` for the validation the loader performs before any experiment
is allowed to run.

## Running

All commands are run from the repo root using system `python3` (has torch+CUDA; the
`revision_v2/.venv` environment is pandas/xgboost-only and is NOT used for v3 training):

```bash
python3 revision_v2/experiments/common/frozen.py verify   # before
python3 revision_v3/src/data/build_manifest.py
python3 -m pytest revision_v3/tests -q
python3 revision_v3/experiments/reference_validation/run_reference_validation.py
...
python3 revision_v2/experiments/common/frozen.py verify   # after
```

See `revision_v3/reports/PHASE1_MODEL_DEFENSIBILITY_REPORT.md` for exact reproduction commands
once Phase 1 is complete.

## DCRG and provenance-safe evaluation

The reviewer-readiness extension adds a typed Delegation-Context Risk Graph (DCRG), corrects
the storage-guard dominance ordering, uses family-matched out-of-fold checkpoints for sampled
benchmark families, and implements `WARN` / `LOW_OBSERVED_RISK` / `DEFER` decisions. Generate
the core artifacts with:

```bash
python3 revision_v3/experiments/delegation_context/build_dcrg_features.py
python3 revision_v3/experiments/delegation_context/run_dcrg_fusion.py
python3 revision_v3/experiments/delegation_context/run_dcrg_bootstrap.py
python3 revision_v3/experiments/delegation_context/run_dcrg_ablation.py
python3 revision_v3/experiments/delegation_context/run_legitimate_controls.py
python3 revision_v3/experiments/delegation_context/run_legitimate_lopo.py
python3 revision_v3/experiments/delegation_context/benchmark_dcrg_runtime.py
```

Build the unlabeled later-time authority/delegate candidate snapshot from the hydrated,
checkpointed Ethereum authorization artifact with:

```bash
git lfs checkout -- revision_v3/temporal/raw/v2_window_ethereum_authorizations.csv
python3 revision_v3/experiments/temporal_v2/build_postcutoff_snapshot.py
python3 revision_v3/experiments/temporal_v2/sample_postcutoff_review.py
python3 revision_v3/experiments/temporal_v2/build_postcutoff_dcrg.py
python3 revision_v3/experiments/temporal_v2/build_postcutoff_provenance_worklist.py
python3 revision_v3/experiments/temporal_v2/enrich_postcutoff_provenance.py
# One time only, if the audit CSV does not already exist:
python3 revision_v3/experiments/temporal_v2/validate_postcutoff_project_families.py \
  --init-template
# After completing every audit row, validate and materialize training holds:
python3 revision_v3/experiments/temporal_v2/validate_postcutoff_project_families.py
```

This recovers the EIP-7702 tuple signer, retrieves delegate code at the first observed
authorization block, checks canonical-family overlap, freezes exact-runtime candidate families,
takes a deterministic score-blind sample, and extracts authority-aware DCRG artifacts without
labels or model scores. The sampler refuses inputs containing label or model-output columns.
The annotation app treats `postcutoff` like Gold-Test: two primary reviewers and adjudication
on disagreement. Its evidence packet includes the recovered EOA and frozen authorization-event
provenance but excludes DCRG output and every model/source label. Complete the generated
project-family audit and rerun its validator without `--init-template`; it fails closed on
unresolved provenance and materializes related canonical families/control projects as required
retraining holds. The generated provenance worklist supplies score-blind Etherscan links,
authorization-event timestamps, and exact-runtime peer leads; these are investigation aids,
not automatic project-family findings, and they never modify the human audit CSV. The
enrichment command adds resumable, source-text-free verification/name/proxy leads from public
Sourcify and Ethereum Blockscout APIs. It likewise cannot mark an audit row `CONFIRMED`.

Before any post-cutoff review begins, retrain and freeze all label-free scores:

```bash
python3 revision_v3/experiments/temporal_v2/run_postcutoff_retraining.py
```

This command refuses to run if any post-cutoff annotation (including a draft) already exists,
removes every audited related canonical family, reserves canonical fold 0 for validation,
fits calibration and thresholds only after the holds, trains three declared seeds, hashes all
checkpoints and predictions, validates their provenance, and writes the review-unlock file.
It also refuses a second run after scores are frozen. Until the unlock, the annotation UI hides
post-cutoff links, skips them in "next item," and returns HTTP 423 for direct GET or POST access.

Gold-Test scores are likewise frozen before review. The one-time freeze has already produced
score-only fusion and four-model representation-ablation artifacts plus
`results/human_final/gold_test_scoring_lock.json`; do not regenerate them after annotation.
The lock records that the Gold-Test database had zero annotations, removes inherited source
labels from the evaluation files, and binds the manifest, seeds, feature groups, and artifacts
by SHA-256. The final evaluator verifies this lock before reading the human release.

After every frozen review item has an adjudicated final label, export the annotation database
and run the strict human-final evaluation:

```bash
python3 revision_v3/annotation_app/export.py gold_test
python3 revision_v3/experiments/human_label_evaluation/evaluate_against_human_labels.py \
  revision_v3/annotation_app/release_gold_test.json gold_test \
  --agreement-report revision_v3/annotation_app/agreement_gold_test.json

python3 revision_v3/annotation_app/export.py postcutoff
python3 revision_v3/experiments/human_label_evaluation/evaluate_against_human_labels.py \
  revision_v3/annotation_app/release_postcutoff.json postcutoff \
  --predictions revision_v3/results/postcutoff_retraining/postcutoff_predictions.csv.gz \
  --holdout-plan revision_v3/results/postcutoff_snapshot/postcutoff_family_holdout_plan.json \
  --training-manifest revision_v3/results/postcutoff_retraining/postcutoff_training_manifest.json \
  --sample-lock revision_v3/results/postcutoff_snapshot/postcutoff_review_lock.json \
  --agreement-report revision_v3/annotation_app/agreement_postcutoff.json
```

The evaluator refuses incomplete or mismatched releases, and Gold-Test/Pilot cannot pass with
single-review items or unresolved disagreements. It compares sequence, DCRG, and fixed fusion
scores with their item-specific held-out validation thresholds, audits selective-policy errors,
computes paired family-clustered intervals, and repeats the full-vs-capability-only,
full-vs-untyped-guards, and full-vs-no-protocol-actors representation ablations on the independent
labels. It does not retrain or select a model using Gold-Test labels.

Results under `results/delegation_context/` are labeled as inherited-label engineering evidence.
They are not an independent semantic-validity claim. See
`reports/DCRG_REVIEWER_READINESS.md` for mandatory human-label, post-cutoff-family, authority-
context, and runtime acceptance gates.

Audit a candidate LaTeX submission against both claim wording and the live evidence gates:

```bash
python3 revision_v3/experiments/reporting/audit_submission_claims.py path/to/main.tex \
  --json-output revision_v3/reports/SUBMISSION_LATEX_CLAIM_AUDIT.json \
  --markdown-output revision_v3/reports/SUBMISSION_LATEX_CLAIM_AUDIT.md
```

The command exits nonzero for unverified priority claims, stale v2 metrics/architecture,
global baseline superiority or deployment-safety language, unresolved project families,
unfrozen post-cutoff retraining, or incomplete dual-review/adjudication evidence.
