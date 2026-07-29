# AuthGuard-7702 — Revision v3 (Phase 1: Model Defensibility)

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

## Phase 1 scope

In scope: controlled equal-budget ablation, reference-model parity validation, exploratory
hybrid model candidates, corrected parameter accounting, matched-budget robustness.

Out of scope (explicitly, per phase objective): human annotation, temporal data collection,
PU/label-noise learning, ONNX/WASM deployment, manuscript rewriting.
