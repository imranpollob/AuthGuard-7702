# Task-Alignment Protocol v1 — FROZEN BEFORE MODEL RERUNS

Freeze date: 2026-07-15  
Status: immutable for the v1 sensitivity rerun  
Global seed: 7702

## Purpose

Construct a bytecode-only evaluation manifest whose rows contain delegate runtime bytecode rather than EIP-7702 designators and whose deterministic input does not carry conflicting class labels. The original dataset, frozen family file, features, folds, and experiment artifacts remain unchanged.

## Frozen source artifacts

- Original dataset: `capability_dataset.csv`.
- Original family assignment: `family_assignment_frozen.csv`.
- Original feature and experiment implementations under `pipeline/`.
- v1 task-aligned dataset SHA-256: `147f86754bd2a01da1a21d78cce21a4710855a5eff3f6788ab6c3e58b4a8ac5f`.
- Designator audit SHA-256: `2c217960d901ba8827276344c1bc2b0678cda4f4115f9f54b11a137916443d66`.
- Conflicting-bytecode audit SHA-256: `73e389713157d6c30c863f3acfed627974f89fe11682b993b0b0c6fb9ae66a1d`.
- Read-only RPC cache SHA-256: `de168f9cd5e3ca9645d903ce6a6fd39e4934bdbbb0650601c839d6d770f93c1a`.

## Designator policy, fixed without model outcomes

A bare 23-byte `ef0100 || address` value is never treated as delegate runtime bytecode.

For each of the 76 designator rows:

1. Parse the 20-byte target address.
2. Search the same chain in existing repository rows for non-designator target runtime.
3. Query the target with read-only `eth_getCode` and cache the response.
4. Prefer one unambiguous repository runtime when present; otherwise use a nonempty, non-designator RPC runtime.
5. If no verified runtime exists, exclude the source row from the task-aligned manifest.
6. If recovered runtime is exact-bytecode-identical to a row in another frozen family, exclude the recovered source row. Reassigning its family would violate the requirement to preserve original family IDs, while retaining it would permit an exact input to cross outer folds.
7. Otherwise replace the designator with verified runtime only in `task_aligned_dataset_v1.csv`, retain the source row identity and original family ID, and record the target address.

Frozen audit outcome before modeling:

- 76 designator rows inspected.
- 32 verified runtimes recovered: 29 from repository target rows and 3 from read-only RPC.
- 29 recovered rows excluded because the recovered exact bytecode already occurs in a different frozen family.
- 3 recovered runtime rows retained.
- 44 unresolved rows excluded: these had no verified non-designator target runtime.
- Total designator-source exclusions: 73.

“Recovered” counts successful runtime acquisition; “retained recovered” is the subset safe under the simultaneous frozen-family and exact-leakage constraints.

## Exact-bytecode conflict policy, fixed without model outcomes

1. Normalize bytecode by lowercasing, stripping `0x`, and dropping a trailing odd nibble, matching the frozen preprocessing.
2. Hash the normalized text with SHA-256.
3. After permitted designator replacement/exclusion, identify every hash assigned to more than one dataset class.
4. Quarantine the entire exact-bytecode group. Never retain only the favorable class and never relabel from a model prediction.
5. Apply the same rule to any conflict induced by designator runtime recovery.

Frozen audit outcome before modeling:

- 23 original conflicting exact hashes.
- 103 total rows across those hashes.
- No additional conflict hash was induced by the three retained recoveries.
- All 103 rows are quarantined.
- The v1 manifest has zero cross-class exact hashes.

The audit classifies malicious-versus-nonmalicious groups as unresolved binary label/context conflicts. Groups differing only between benign subsets are contextual subset overlap; they are still quarantined because the frozen default rule applies to any conflicting class label.

## Frozen v1 manifest

- Total retained: 3,082.
- Malicious: 727.
- `benign_cleared`: 1,553.
- `benign_general`: 797.
- `benign_AA`: 5.
- Primary malicious fraction (`malicious` vs `benign_cleared`): 0.31886.
- Retained frozen families: 1,258.
- Malicious-bearing families: 209.
- Malicious-member singleton families: 112.
- Global singleton families: 856.
- Cross-class families: 28; these are similarity families, not exact-bytecode conflicts.
- Exact duplicate hash groups: 233, covering 787 retained rows.
- Cross-class exact hash groups: 0.

Exact same-class duplicates remain because the unit of observation retains chain/address rows. Their related-bytecode dependence remains controlled by the preserved global family split.

## Outer-fold preservation

The original primary family-to-test-fold mapping is reconstructed once by running the unchanged original `GroupKFold(5)` on all original `malicious` and `benign_cleared` rows in original row order. Each retained primary family keeps that test-fold ID in `outer_fold_primary`.

The original secondary mapping is reconstructed analogously on the original `malicious`, `benign_cleared`, and `benign_general` population and stored as `outer_fold_secondary`.

Reruns must index folds from these stored columns. They must not call `GroupKFold` on the reduced rows, because doing so would rebalance family assignments and violate fold preservation.

For G-ADV outer fold `f`, the validation fold remains `(f + 1) mod 5`, and train-fit remains all other families not in test or validation.

## Frozen rerun rules

Unchanged:

- bytecode normalization and feature extraction;
- feature column set and banned features;
- model hyperparameters and estimator seeds;
- five original outer fold identities;
- G-DET/G-MUT in-sample max-F1 threshold procedure;
- G-ADV clean-validation max-F1 threshold procedure;
- mutation and flooding recipes;
- augmentation conditions and source-balanced weighting;
- test/train mutation RNG domains;
- metrics and aggregation as fold means with population SD.

Minimum mechanical adjustments:

1. Recompute features for the v1 manifest because three retained rows have recovered runtime bytecode.
2. Select fixed test folds from the stored original fold IDs rather than allowing `GroupKFold` to rebalance after removals.
3. For the random-split diagnostic, retain `KFold(5, shuffle=True, random_state=7702)` on retained row order. Exact row assignments necessarily change because rows were removed; no result-dependent stratification or tuning is allowed.
4. Build mutations only for the 727 retained positives, with unchanged recipes and seeds.
5. Write every output below `paper_build/data_hygiene`; never overwrite original outputs.

## Pre-outcome predictions and decision rule

No direction or magnitude of metric change is assumed. The original values remain the historical audit baseline until the task-aligned comparison is reviewed. The final gate will use task validity and protocol compliance, not whether performance improves.

This file must not be edited after the first task-aligned model fit. Any future policy change requires `task_alignment_protocol_v2.md`, a new hash, a new manifest, and a complete rerun.
