# Deployment Evaluation Report

**Real measurements on this machine, repeated calls with warm-up (200 forward calls, 20
warm-up; 100 preprocessing/e2e calls, 10 warm-up).** Script: `run_deployment_evaluation.py`.
Full output: `results/deployment/deployment_report.json`.

## Environment (record for reproducibility; do not compare across different hardware without
this context)

- GPU: NVIDIA GeForce RTX 2080 SUPER
- CPU: x86_64, 6 threads (torch default)
- OS: Linux 7.0.0-28-generic
- Python 3.12.12, PyTorch 2.9.0+cu128, onnxruntime 1.28.0
- Batch used for throughput: 20 items (Pilot sample, 167-15,227 bytes, mean 3,633.5 bytes)

## Results

| Model | Device | Params | Checkpoint (bytes) | Forward p50/p99 (ms) | E2E p50/p99 (ms) | Peak GPU mem (bytes) | Throughput (items/s) |
|---|---|---|---|---|---|---|---|
| authguard_sequence_dense | CPU | 97,646 | 397,988 | 2.83 / 3.44 | 2.72 / 3.20 | — | 125.7 |
| authguard_sequence_dense | GPU | 97,646 | 398,180 | 3.50 / 4.04 | 3.43 / 4.09 | 35,893,248 | 116.7 |
| authguard_sequence_dense | ONNX (CPU) | — | 404,727 | 4.99 / 8.31 | — | — | — |
| authguard_reference_v3 | CPU | 38,562 | 159,100 | 1.07 / 1.36 | 1.07 / 1.19 | — | 432.0 |
| authguard_reference_v3 | GPU | 38,562 | 159,228 | 1.18 / 1.81 | 1.20 / 1.77 | 35,416,576 | 411.2 |

## ONNX export

- `authguard_sequence_dense`: export succeeded (404,727-byte ONNX file), numerical parity
  confirmed against the PyTorch model (max absolute difference **4.17e-7** across all output
  logits on a dummy batch) — numerically equivalent. ONNX Runtime CPU latency (4.99ms median)
  was *slower* than native PyTorch CPU (2.83ms) on this machine/opset — reported as measured,
  not assumed; ONNX is not automatically faster for small models with this graph shape.
- `authguard_reference_v3`: export succeeded (162,994 bytes), but the numerical-parity check
  in this benchmark script failed with `'tuple' object has no attribute 'numpy'` — a bug in
  the benchmark script's output-handling (ChunkModel's forward returns a `(logits, fused)`
  tuple, which the script's parity-check code didn't unwrap for the non-hybrid branch), not a
  failure of the export itself. Recorded honestly as an unresolved measurement gap rather than
  silently omitted or assumed to have passed.

## Not measured in this pass

- CPU-only (no GPU present) machine numbers — this environment has a GPU; a CPU-only
  measurement would need separate hardware.
- Batch sizes other than 20.
- `provisional_final_model` and the sequence-only reference under a dedicated GPU-memory
  profiling pass beyond the single peak-allocation snapshot taken here.

## CPU preprocessing latency

Reported separately from forward latency in the raw JSON (`preprocessing_latency_ms` per
model) — encode_bytecode (tokenization + histogram + structural features) dominates for
`authguard_sequence_dense`'s CPU path; not summarized in the table above for brevity, see the
JSON for exact per-model preprocessing timings.
