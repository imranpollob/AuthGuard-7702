#!/usr/bin/env python3
"""Frozen local scorer-core timing benchmark."""
import hashlib
import json
import os
import platform
import sys
import time

import numpy as np
import pandas as pd
import sklearn
import xgboost
from xgboost import XGBClassifier

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "paper_build", "runtime")
PIPE = os.path.join(ROOT, "pipeline")
sys.path.insert(0, PIPE)
from ag_common import SEED  # noqa: E402
from ag_features import featurize, build_sensitive_selector_set  # noqa: E402

SENS = build_sensitive_selector_set()
HP = dict(n_estimators=300, max_depth=6, learning_rate=0.1, subsample=0.9,
          colsample_bytree=0.8, eval_metric="logloss", random_state=SEED,
          n_jobs=4, tree_method="hist")


def stats(a):
    a = np.asarray(a, dtype=float)
    return {"n": len(a), "mean": float(a.mean()), "std_population": float(a.std()),
            "p50": float(np.percentile(a, 50)), "p95": float(np.percentile(a, 95)),
            "p99": float(np.percentile(a, 99)), "min": float(a.min()), "max": float(a.max())}


def main():
    dataset = os.path.join(ROOT, "paper_build", "data_hygiene", "task_aligned_dataset_v1.csv")
    df = pd.read_csv(dataset)
    mask = df["class"].isin(["malicious", "benign_cleared"]).to_numpy()
    xd = np.load(os.path.join(ROOT, "paper_build", "data_hygiene",
                              "task_aligned_features_dense.npz"))["X"]
    xn = np.load(os.path.join(ROOT, "paper_build", "data_hygiene",
                              "task_aligned_features_ngram.npz"))["X"]
    y = (df.loc[mask, "class"] == "malicious").astype(int).to_numpy()
    model = XGBClassifier(**HP)
    model.fit(np.hstack([xd[mask], xn[mask]]), y)

    sample = df.sample(300, random_state=SEED)
    bytecodes = sample["bytecode"].tolist()
    sample_ids = (sample["chain"].astype(str) + ":" + sample["address"].astype(str)).tolist()
    sample_hash = hashlib.sha256("\n".join(sample_ids).encode()).hexdigest()

    for i in range(30):
        fx, fn, _ = featurize([bytecodes[i % len(bytecodes)]], sens=SENS)
        model.predict_proba(np.hstack([fx, fn]))[:, 1]

    single_ms = []
    for _ in range(10):
        for bc in bytecodes:
            t0 = time.perf_counter_ns()
            fx, fn, _ = featurize([bc], sens=SENS)
            model.predict_proba(np.hstack([fx, fn]))[:, 1]
            single_ms.append((time.perf_counter_ns() - t0) / 1_000_000.0)

    for _ in range(3):
        fx, fn, _ = featurize(bytecodes, sens=SENS)
        model.predict_proba(np.hstack([fx, fn]))[:, 1]

    batch_ms = []
    for _ in range(10):
        t0 = time.perf_counter_ns()
        fx, fn, _ = featurize(bytecodes, sens=SENS)
        model.predict_proba(np.hstack([fx, fn]))[:, 1]
        batch_ms.append((time.perf_counter_ns() - t0) / 1_000_000.0)

    result = {
        "scope": "local bytecode feature extraction plus XGBoost model prediction",
        "excludes": ["RPC", "authorization parsing", "cache/network", "model training",
                     "model loading", "process startup", "threshold/UI warning", "wallet integration"],
        "environment": {"cpu": "Apple M1", "memory_bytes": 8589934592,
                        "os": "macOS 26.5.1 build 25F80", "architecture": platform.machine(),
                        "python": sys.version.split()[0], "xgboost": xgboost.__version__,
                        "numpy": np.__version__, "scikit_learn": sklearn.__version__,
                        "pandas": pd.__version__},
        "seed": SEED,
        "sample_size": 300,
        "sample_id_sha256": sample_hash,
        "bytecode_preloaded_in_memory": True,
        "model_training_excluded": True,
        "model_loading_excluded": True,
        "single_contract": {"batch_size": 1, "warmup_calls": 30, "timed_passes": 10,
                            "timed_calls": 3000, "milliseconds": stats(single_ms)},
        "batched": {"batch_size": 300, "warmup_batches": 3, "timed_batches": 10,
                    "batch_milliseconds": stats(batch_ms),
                    "milliseconds_per_contract": stats(np.asarray(batch_ms) / 300.0)},
        "raw_single_contract_ms": single_ms,
        "raw_batch_ms": batch_ms,
    }
    with open(os.path.join(OUT, "runtime_results.json"), "w") as f:
        json.dump(result, f, indent=2)
    print(json.dumps({"single_contract_ms": result["single_contract"]["milliseconds"],
                      "batch_ms_per_contract": result["batched"]["milliseconds_per_contract"]},
                     indent=2))


if __name__ == "__main__":
    main()
