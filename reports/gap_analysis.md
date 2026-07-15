# Gap Analysis — demonstrated vs motivated vs unevaluated

Separates weaknesses by evidentiary status so the paper never presents a literature-motivated
gap as an experimental finding.

## A. Weaknesses DEMONSTRATED by our experiments (cite directly)
| Gap | Evidence | Artifact |
|--|--|--|
| Blocklist/signature fails on unseen families | recall 0.000 LFO; AUPRC 0.324 | `detection_results.json` |
| Random-split inflation / clone leakage | AuthGuard 0.856→0.961; blocklist 0.324→0.558 | `detection_results.json` |
| Name-match rule trivially evaded | 0.038→0.000 at M3 | `mutation_curve.json` |
| Structural rule non-discriminative | flags 88–92% benign | `independent_detection.json` |
| Learned model heavy-flood weakness (M0) | +200% 0.624 (pure-M0) / 0.139 (M3-base) | `advtrain_results.json` / `mutation_volume.json` |
| Residual padded-benign FP after augmentation | 27.5% @+200% | `advtrain_results.json` |
| Weak-negative contamination | ≤8.1% | `supporting.json` |

## B. Weaknesses MOTIVATED ONLY by prior literature (cite as motivation)
| Gap | Status |
|--|--|
| Post-hoc detection needs observed transactions | LITERATURE-VERIFIED |
| Heavy decompiler deployment burden | PROVISIONAL (runtime `[NOT MEASURED]`) |
| Prior phishing-bytecode detectors omit adversarial-robustness evaluation | LITERATURE-VERIFIED (as a gap) |
| Prior work rarely uses family-grouped splits | PROVISIONAL (not exhaustively surveyed) |

## C. Weaknesses NOT YET EVALUATED (do not claim; future work)
| Gap | Why unevaluated |
|--|--|
| Signer-context / relational risk | no victim data (stripped); synthetic only |
| Selective escalation / calibration | not implemented |
| Independent EIP-7702 ground truth at scale | INSUFFICIENT DATA (N=1) |
| Cross-chain leave-one-chain-out generalization | not run |
| Temporal / time-based generalization | not run |
| Robustness to control-flow obfuscation / recompilation | mutation set is data/pad/rename only |
| Compound M3 + heavy-flood robustness | excluded by leakage-safe design |

## Why this is not "XGBoost on blockchain data"
The estimator is deliberately standard; the contributions are (1) the pre-signing problem
formulation and bytecode-only information set, (2) the frozen leakage-safe family-grouped
evaluation that measures and removes near-duplicate inflation, and (3) the verified
structure-preserving mutation benchmark plus source-balanced augmentation with paired-statistical
robustness evidence. Swapping XGBoost for another classifier would not change any of these.
