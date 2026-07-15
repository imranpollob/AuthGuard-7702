# Task-Aligned Result Provenance

## Protocol identity

- Frozen task-alignment protocol SHA-256: `6368be0b35c5b4aca6e067b3fb57aabf7db90a18b4bc6d43c9e969abae16083b`.
- Original family IDs retained without reclustering.
- Original primary and secondary outer family-to-fold identities stored in the manifest.
- Random diagnostic mechanically reruns the same seeded KFold on the reduced row order.
- Feature extraction, estimators, seeds, thresholds, mutations, augmentation, and weighting are unchanged.

## Output fingerprints

| artifact | SHA-256 |
|---|---|
| `task_aligned_dataset_v1.csv` | `147f86754bd2a01da1a21d78cce21a4710855a5eff3f6788ab6c3e58b4a8ac5f` |
| `designator_audit.csv` | `2c217960d901ba8827276344c1bc2b0678cda4f4115f9f54b11a137916443d66` |
| `conflicting_bytecodes.csv` | `73e389713157d6c30c863f3acfed627974f89fe11682b993b0b0c6fb9ae66a1d` |
| `task_alignment_protocol.md` | `6368be0b35c5b4aca6e067b3fb57aabf7db90a18b4bc6d43c9e969abae16083b` |
| `task_alignment_protocol.sha256` | `4a12747ba4980d39a7367b27e85e1fa0f3045b52f56a116a05530bbbbb889e24` |
| `task_aligned_detection_results.json` | `38a812ce13b81516811d43607edff2d291516193e2410966f403f9a60ef77520` |
| `task_aligned_mutation_curve.json` | `45a76cf8babc74a3b3554446daefcf4c3f5c957a3f0cc614201f1c77dfc1da47` |
| `task_aligned_mutation_preservation.json` | `3f1ae231a07c16331c2e7ffb08dc7cb6e1b0ba317cedd746fead4600fceb4723` |
| `task_aligned_mutation_volume.json` | `ae7984fbab0d4462978c298cd80b64ab852a929c4ab55f24d52ebe215d8cb0fd` |
| `task_aligned_advtrain_results.json` | `3e030136dedca890558698939d06f47e8d0f5fa8026b9641bc85bdf101fe7106` |
| `task_aligned_paired_results.csv` | `f4c22e370503244e3907c4c0c0950ee9e1f07b1b21289775059c89d3389f7e84` |
| `task_aligned_results.json` | `f78ca60cc23e31d17b0d753efdbc6dbb0c474e47132bc8d9a8bd88f94c01dd6f` |
| `task_aligned_advtrain_leakage_assertions.txt` | `a49c50cda7cd61663b3fc2a01df890f9bcb7c3715a50402ce441bd0c8f4b105b` |

## Group provenance

- **G-DET:** imported the frozen detector implementation; fixed family tests come from stored original fold IDs; in-sample training thresholds unchanged.
- **G-MUT:** learned models fit on retained M0 training folds; only retained held-out positives mutated; all variants inherit original families.
- **G-VOL:** unchanged compound metadata/address/selector transformation with variable appended dead code.
- **G-ADV:** original test fold `f`, validation fold `(f+1) mod 5`, and remaining train-fit folds; unchanged seen/held-out conditions and source weights.

## Integrity assertions

- Zero cross-class exact hashes after cleaning.
- Zero retained exact hashes spanning frozen families.
- Zero families spanning primary or secondary stored outer folds.
- All task-aligned G-ADV source/family/train-test-hash and mutant-inheritance assertions passed.
- G-MUT preservation checks cover all 727 retained positives at M1, M2, and M3.

## Aggregation

Main tables use arithmetic means over the five preserved outer test folds and population SD. Paired analyses pool each contract’s one outer-test prediction and preserve model pairing. Family-clustered uncertainty is separately recorded under `paper_build/statistics/`.
