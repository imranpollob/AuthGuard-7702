# RESULTS_README — exact reproduction

Deterministic end-to-end. Global seed = **7702**. All result-affecting hashing uses seeded
`blake2b`, so `PYTHONHASHSEED` does **not** change any output (verified: identical
`family_assignment_frozen.csv` under `PYTHONHASHSEED=1` and `=999`). We still pin it below for
byte-identical logs.

## Environment
- Python 3.13, `numpy`, `pandas`, `scikit-learn`, `xgboost` (needs OpenMP: `brew install libomp`
  on macOS), `matplotlib`, `pycryptodome` (real keccak selectors), `openpyxl`.
- No decompiler, no Gigahorse/Soufflé, no network calls.

## Run order (from repo root)
```bash
export PYTHONHASHSEED=0
python3 pipeline/01_freeze_families.py    # -> family_assignment_frozen.csv, results/family_structure.{md,json}
python3 pipeline/02_features.py           # -> results/features_dense.npz, features_ngram.npz, feature_meta.json
python3 pipeline/03_detection.py          # -> results/detection_results.json           (~2 min)
python3 pipeline/04_mutations.py          # -> results/mutation_curve.json, mutation_volume.json, mutation_preservation.json (~1 min)
python3 pipeline/05_supporting.py         # -> results/supporting.json
python3 pipeline/06_figures.py            # -> figures/*.png
python3 pipeline/07_summary.py            # -> results_summary.md   (regenerated from JSON; no hand-typed numbers)
```
`run_all.sh` runs the whole chain.

## Inputs (verified on load)
- `capability_dataset.csv` — 3,258 rows (malicious 793 / benign_cleared 1,657 / benign_general 800
  / benign_AA 8). Only `address, chain, family_id_d3(ignored), class, bytecode` are read; the
  `cap_*` columns are NOT used as features (two are tautological, all are positives-only).
- `USENIX EIP-7702 artifact/eoa_detect/decompile/AM_Detect_SensitiveSigName.jsonl` — used only to
  seed the sensitive-selector set for the reimplemented USENIX name-rule.

## Key modules
- `pipeline/ag_common.py` — deterministic disasm + seeded MinHash + opcode vocab.
- `pipeline/ag_features.py` — single featurizer used by BOTH bulk extraction and on-the-fly mutant
  featurization (zero drift). Bytecode-only; banned features asserted out.

## Frozen artifacts downstream code must read (never recompute)
- `family_assignment_frozen.csv` — canonical `family_id` (threshold 0.85) + 0.75/0.90 columns.
  All grouping/splitting reads this file.

## Determinism check
```bash
cp family_assignment_frozen.csv /tmp/a.csv
PYTHONHASHSEED=999 python3 pipeline/01_freeze_families.py
python3 -c "import pandas as pd; print(pd.read_csv('/tmp/a.csv').equals(pd.read_csv('family_assignment_frozen.csv')))"  # True
```

## Output map
| File | Content |
|---|---|
| `results_summary.md` | all paper-ready tables + candid narrative (auto-generated) |
| `results/family_structure.md/.json` | Task A family counts + sensitivity |
| `results/detection_results.json` | Task C: per-method, per-fold + mean±std, LFO & random, both tasks |
| `results/mutation_curve.json` | Task D: retained detection M0–M3 (per-fold + mean±std) |
| `results/mutation_volume.json` | Task D: dead-code volume sweep |
| `results/mutation_preservation.json` | 793/793 semantics-preservation verification |
| `results/supporting.json` | Task E: contamination, latency, explanation, synthetic signer |
| `figures/*.png` | 5 publication figures |
| `DECISIONS.md` | every non-obvious methodological call + why |
