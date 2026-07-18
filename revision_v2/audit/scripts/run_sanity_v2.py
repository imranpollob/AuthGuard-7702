#!/usr/bin/env python3
"""Part 8 — signal sanity check on the corrected AuthGuardBench-7702 v2 primary task.

Trains, per stored family-disjoint outer fold (seed 7702):
  1. hist_ngram_xgb — opcode histogram + hashed 4-gram XGBoost (strongest traditional
     baseline, identical hyperparameters to the original run), and
  2. sequence_only AuthGuard-Seq — identical architecture, protocol, and training
     configuration to revision_v2/experiments/authguard_fusion/run_authguard_fusion.py.

The protocol matches the original: validation fold = (fold+1)%5, temperature scaling on
validation, warning thresholds from validation negatives, metrics on the test fold.

Outputs under revision_v2/audit/sanity_v2/:
  features_v2.npz (cache), metrics_v2.csv, predictions_v2.csv.gz, comparison.json
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
AUDIT = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(AUDIT, "..", ".."))
RV2 = os.path.join(ROOT, "revision_v2")
OUT = os.path.join(AUDIT, "sanity_v2")
BENCH = os.path.join(RV2, "data", "authguardbench_7702_v2.csv.gz")

sys.path.insert(0, RV2)
sys.path.insert(0, os.path.join(RV2, "experiments", "common"))

SPEC = importlib.util.spec_from_file_location(
    "fusion_run", os.path.join(RV2, "experiments", "authguard_fusion",
                               "run_authguard_fusion.py"))
fusion = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fusion)

from authguard7702.features import encode_bytecode  # noqa: E402
from authguard7702.model import AuthGuardFusion, FusionConfig  # noqa: E402
from authguard7702.policy import WarningPolicy  # noqa: E402

SEED = 7702


def _encode(payload):
    index, bytecode = payload
    encoded = encode_bytecode(bytecode)  # full token stream; chunking happens later
    tokens = encoded.chunks.reshape(-1)
    tokens = tokens[tokens != 0].astype(np.uint16)
    if not len(tokens):
        tokens = np.asarray([1], dtype=np.uint16)
    return index, encoded.dense.astype(np.float32), encoded.ngram.astype(np.float32), \
        tokens, encoded.auxiliary.astype(np.float32)


def build_features(frame: pd.DataFrame, cache_path: str) -> dict:
    row_hash = pd.util.hash_pandas_object(frame["bytecode_sha256"]).sum().item()
    if os.path.exists(cache_path):
        data = np.load(cache_path, allow_pickle=False)
        stored = json.loads(str(data["meta"]))
        if stored["row_hash"] == row_hash:
            return {key: data[key] for key in
                    ("dense", "ngram", "tokens", "offsets", "auxiliary")}
    payloads = list(enumerate(frame["runtime_bytecode"].tolist()))
    dense = np.zeros((len(frame), 261), dtype=np.float32)
    ngram = np.zeros((len(frame), 512), dtype=np.float32)
    auxiliary = np.zeros((len(frame), 6), dtype=np.float32)
    token_rows: list = [None] * len(frame)
    import multiprocessing
    context = multiprocessing.get_context("fork")
    with ProcessPoolExecutor(max_workers=10, mp_context=context) as pool:
        for count, (index, d, g, tokens, aux) in enumerate(
                pool.map(_encode, payloads, chunksize=16)):
            dense[index], ngram[index], auxiliary[index] = d, g, aux
            token_rows[index] = tokens
            if count % 250 == 0:
                print(f"[featurize] {count}/{len(frame)}", flush=True)
    offsets = np.zeros(len(frame) + 1, dtype=np.int64)
    offsets[1:] = np.cumsum([len(t) for t in token_rows])
    tokens = np.concatenate(token_rows)
    meta = json.dumps({"row_hash": row_hash})
    np.savez_compressed(cache_path, dense=dense, ngram=ngram, tokens=tokens,
                        offsets=offsets, auxiliary=auxiliary, meta=np.str_(meta))
    return dict(dense=dense, ngram=ngram, tokens=tokens, offsets=offsets,
                auxiliary=auxiliary)


class LocalTokenStore:
    def __init__(self, tokens, offsets, auxiliary):
        self.tokens = tokens
        self.offsets = offsets
        self.auxiliary = auxiliary

    def row(self, source_index: int) -> np.ndarray:
        return self.tokens[self.offsets[source_index]:
                           self.offsets[source_index + 1]].astype(np.int64)


def main() -> int:
    import torch
    from dataclasses import replace
    from sklearn.metrics import average_precision_score
    from xgboost import XGBClassifier

    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--patience", type=int, default=5)
    parser.add_argument("--folds", nargs="+", type=int, default=list(range(5)))
    args = parser.parse_args()

    os.makedirs(OUT, exist_ok=True)
    bench = pd.read_csv(BENCH)
    frame = bench[bench["population"] == "PRIMARY_EVALUATION"].reset_index(drop=True)
    assert not frame["bytecode_repaired"].any()
    print(f"[sanity] v2 primary rows={len(frame)} "
          f"pos={int(frame['label'].sum())}", flush=True)
    features = build_features(frame, os.path.join(OUT, "features_v2.npz"))
    tokens = LocalTokenStore(features["tokens"], features["offsets"],
                             features["auxiliary"])
    Xd = features["dense"]
    Xn = features["ngram"]
    y = frame["label"].to_numpy(dtype=int)
    folds = frame["fold_id"].to_numpy(dtype=int)
    hist_ngram = np.hstack([Xd[:, :225], Xn]).astype(np.float32)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[sanity] device={device}", flush=True)

    metrics_rows, prediction_rows = [], []
    for fold in args.folds:
        val_fold = (fold + 1) % 5
        train_idx = np.flatnonzero((folds != fold) & (folds != val_fold))
        val_idx = np.flatnonzero(folds == val_fold)
        test_idx = np.flatnonzero(folds == fold)
        mean = Xd[train_idx].mean(0)
        scale = Xd[train_idx].std(0)
        scale[scale < 1e-6] = 1.0

        # --- strongest traditional baseline
        model = XGBClassifier(random_state=SEED, **fusion.XGB_HP)
        model.fit(hist_ngram[train_idx], y[train_idx])
        val_scores = model.predict_proba(hist_ngram[val_idx])[:, 1]
        test_scores = model.predict_proba(hist_ngram[test_idx])[:, 1]
        policy = WarningPolicy.from_validation_negatives(val_scores[y[val_idx] == 0])
        result = fusion.evaluate(y[test_idx], test_scores, policy)
        metrics_rows.append({"seed": SEED, "fold": fold, "model": "hist_ngram_xgb",
                             "condition": "cleanM0", **result, **policy.to_dict()})
        for local, index in enumerate(test_idx):
            prediction_rows.append({"seed": SEED, "fold": fold,
                                    "model": "hist_ngram_xgb",
                                    "sid": frame.loc[index, "sample_id"],
                                    "family_id": frame.loc[index, "family_id"],
                                    "y": int(y[index]),
                                    "score": float(test_scores[local])})
        print(f"[sanity] fold={fold} hist_ngram_xgb AUPRC={result['AUPRC']:.4f} "
              f"R@5 {result['Recall_05']:.3f}", flush=True)

        # --- AuthGuard-Seq (sequence_only)
        source_indices = np.arange(len(frame))
        train_loader = fusion.make_loaders(
            train_idx, source_indices, tokens, Xd, Xn, y, mean, scale,
            256, 64, 16, shuffle=True)
        val_loader = fusion.make_loaders(val_idx, source_indices, tokens, Xd, Xn, y,
                                         mean, scale, 256, 64, 16)
        test_loader = fusion.make_loaders(test_idx, source_indices, tokens, Xd, Xn, y,
                                          mean, scale, 256, 64, 16)
        config = replace(FusionConfig(), active_views=(True, False, False))
        net, history, best_ap = fusion.train_model(
            config, train_loader, val_loader, device, SEED + fold, args.epochs,
            args.patience, 1e-3, 0.0, 0.0)
        _, y_val, val_logits, _, _ = fusion.predict_logits(net, val_loader, device)
        test_indices, y_test, test_logits, _, _ = fusion.predict_logits(
            net, test_loader, device)
        temperature = fusion.fit_temperature(val_logits, y_val)
        val_probs = fusion.probabilities(val_logits, temperature)
        test_probs = fusion.probabilities(test_logits, temperature)
        policy = WarningPolicy.from_validation_negatives(val_probs[y_val == 0])
        result = fusion.evaluate(y_test, test_probs, policy)
        metrics_rows.append({"seed": SEED, "fold": fold, "model": "sequence_only",
                             "condition": "cleanM0", "temperature": temperature,
                             "best_val_AUPRC": best_ap, **result, **policy.to_dict()})
        for local, index in enumerate(test_indices):
            prediction_rows.append({"seed": SEED, "fold": fold,
                                    "model": "sequence_only",
                                    "sid": frame.loc[int(index), "sample_id"],
                                    "family_id": frame.loc[int(index), "family_id"],
                                    "y": int(y[int(index)]),
                                    "score": float(test_probs[local])})
        print(f"[sanity] fold={fold} sequence_only AUPRC={result['AUPRC']:.4f} "
              f"R@5 {result['Recall_05']:.3f} (val {best_ap:.4f})", flush=True)
        pd.DataFrame(metrics_rows).to_csv(os.path.join(OUT, "metrics_v2.csv"),
                                          index=False)
        pd.DataFrame(prediction_rows).to_csv(
            os.path.join(OUT, "predictions_v2.csv.gz"), index=False)

    # ---------------------------------------------------------- comparison
    original = pd.read_csv(os.path.join(RV2, "results", "authguard_fusion",
                                        "metrics.csv"))
    original = original[(original["seed"] == SEED)
                        & (original["condition"] == "cleanM0")
                        & original["model"].isin(["sequence_only", "hist_ngram_xgb"])]
    v2 = pd.DataFrame(metrics_rows)
    columns = ["AUPRC", "Brier", "Recall_01", "FPR_01", "Recall_05", "FPR_05"]
    summary = {}
    for model_name in ("hist_ngram_xgb", "sequence_only"):
        summary[model_name] = {
            "original_benchmark": original[original["model"] == model_name][columns]
            .mean().round(4).to_dict(),
            "revision_v2_benchmark": v2[v2["model"] == model_name][columns]
            .mean().round(4).to_dict(),
        }
    with open(os.path.join(OUT, "comparison.json"), "w") as fh:
        json.dump(summary, fh, indent=2)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
