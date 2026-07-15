# Runtime Protocol — Scorer Core Only

Freeze date: 2026-07-15, before the documented timing run.

## Scope

Measure only AuthGuard bytecode feature extraction plus XGBoost `predict_proba`. This is local scorer-core latency, not end-to-end wallet or network latency.

Excluded:

- RPC and `eth_getCode`;
- EIP-7702 authorization parsing;
- network/cache lookup;
- model training and model loading;
- process startup and dependency import;
- threshold/UI/warning presentation;
- wallet integration.

## Frozen environment

- CPU: Apple M1.
- Memory: 8,589,934,592 bytes (8 GiB).
- OS: macOS 26.5.1, build 25F80, arm64.
- Python: 3.13.9.
- XGBoost: 3.3.0.
- NumPy: 2.3.4.
- scikit-learn: 1.9.0.
- pandas: 3.0.3.
- Global seed: 7702.
- Model thread setting: `n_jobs=4`, matching the frozen estimator.

## Data and model

- Dataset: `task_aligned_dataset_v1.csv`, SHA-256 `147f86754bd2a01da1a21d78cce21a4710855a5eff3f6788ab6c3e58b4a8ac5f`.
- Training population: all task-aligned `malicious` and `benign_cleared` samples.
- Estimator: unchanged AuthGuard XGBoost hyperparameters.
- Timing sample: 300 rows sampled from the complete task-aligned manifest with `random_state=7702`.
- Bytecode strings are loaded into memory before warm-up and timing.

## Timing procedure

- Clock: `time.perf_counter_ns`.
- Single-contract warm-up: 30 feature-extraction-plus-prediction calls.
- Single-contract timed repetitions: 10 complete passes over the fixed 300-row sample, for 3,000 timed calls at batch size 1.
- Report mean, population SD, p50, p95, p99, minimum, and maximum in milliseconds per contract.
- Batched warm-up: 3 complete 300-contract batches.
- Batched timed repetitions: 10 complete batches of 300 contracts.
- Report batch latency and milliseconds per contract.
- Garbage collection remains under the normal Python runtime policy; no result-dependent outlier removal is allowed.
- The machine is not claimed to be load-isolated or benchmark-dedicated.

The result must be described as “local feature extraction plus model prediction,” never “end-to-end wallet latency.”
