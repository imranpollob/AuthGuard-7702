# Operational Evaluation Report

## Artifact identity

The timing artifact is `revision_v2/experiments/robustness_operational_v2/models/model_authguard_seq_s7702_f0.pt`. It is a **fold-specific cross-validation artifact for timing only**, trained on folds [2, 3, 4], calibrated on fold 1, and tested on fold 0 (seed 7702). It is not a final retrained deployment model and is not used to alter cross-validation results.

## Latency

Full local screening was measured over 300 representative contracts × 5 repeats = 1,500 calls. It includes strict input validation, disassembly/tokenization, preprocessing, chunking, inference, temperature calibration, warning-tier assignment, local evidence extraction, hashing, and response construction. It excludes RPC/network, node, UI, and external-service latency.

| Measurement | Mean ms | Median ms | p95 ms | p99 ms |
|---|---:|---:|---:|---:|
| Full local screening | 5.183 | 4.121 | 14.547 | 21.429 |
| Model load | 7.958 | 7.690 | 9.716 | 10.574 |
| Model-forward reference | 1.009 | 0.950 | 1.585 | — |

The artifact contains 181,877 parameters and occupies 725.2 KiB. Hardware: AMD Ryzen 5 3600 6-Core Processor; Python 3.12.12; PyTorch 2.9.0+cu128; one CPU intra-op thread for full-pipeline timing. Model-forward reference timing comes from the completed baseline experiment and remains separate from full-pipeline timing.
