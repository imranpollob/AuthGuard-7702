#!/usr/bin/env python3
"""External-control transfer and CPU latency for the promoted 30K attention model."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
import time

import numpy as np
import pandas as pd
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
RV2 = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import run_long_context_ablation_v3 as lca  # noqa: E402

RESULT_ROOT = os.path.join(RV2, "results", "long_context_ablation_v3")
DEFAULT_OUT = os.path.join(RESULT_ROOT, "operational_controls")
MODEL = "chunk_attention_control_16384"
SPEC = lca.SPECS[MODEL]


def encode_rows(frame):
    rows = []
    for position, bytecode in enumerate(frame["runtime_bytecode"].astype(str)):
        chunks, _ = lca.opcode_chunks(bytecode, lca.CHUNK_SIZE, max_chunks=None)
        tokens = chunks.reshape(-1)
        tokens = tokens[tokens != lca.PAD_ID].astype(np.uint16, copy=False)
        rows.append(tokens if len(tokens) else np.asarray([1], dtype=np.uint16))
        if (position + 1) % 250 == 0:
            print(f"[operational] encoded {position + 1}/{len(frame)}", flush=True)
    offsets = np.zeros(len(rows) + 1, dtype=np.int64)
    offsets[1:] = np.cumsum([len(row) for row in rows])
    return lca.RaggedTokenStore(np.concatenate(rows), offsets)


def save_store(store, path, sids):
    temporary = path + ".tmp.npz"
    np.savez_compressed(
        temporary,
        tokens=store.tokens,
        offsets=store.offsets,
        sids=np.asarray(sids, dtype=str),
    )
    os.replace(temporary, path)


def get_control_store(frame, path):
    sids = frame["sample_id"].astype(str).tolist()
    if os.path.exists(path):
        data = np.load(path, allow_pickle=False)
        if data["sids"].tolist() != sids:
            raise RuntimeError(f"control token cache mismatch: {path}")
        return lca.RaggedTokenStore(data["tokens"], data["offsets"])
    store = encode_rows(frame)
    save_store(store, path, sids)
    return store


def load_model(checkpoint_path):
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    model = lca.ControlledSequenceCNN("attention")
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    policy_data = checkpoint["warning_policy"]
    policy = lca.WarningPolicy(
        policy_data["fpr_01"], policy_data["fpr_05"], policy_data["fpr_10"])
    return model, checkpoint, policy


def score_controls(frame, store, result_root, batch_size):
    labels = np.zeros(len(frame), dtype=int)
    indices = np.arange(len(frame))
    rows = []
    for seed in lca.SEEDS:
        for fold in lca.FOLDS:
            path = os.path.join(
                result_root, "models", f"{MODEL}_seed{seed}_fold{fold}.pt")
            model, checkpoint, policy = load_model(path)
            loader = lca.make_loader(
                indices, store, labels, SPEC, batch_size, shuffle=False)
            scored_indices, _, logits = lca.predict(model, loader, torch.device("cpu"))
            scores = lca.fusion.probabilities(logits, checkpoint["temperature"])
            for local, index in enumerate(scored_indices):
                rows.append({
                    "model": MODEL,
                    "seed": seed,
                    "fold": fold,
                    "sid": frame.iloc[index]["sample_id"],
                    "family_id": frame.iloc[index]["family_id"],
                    "population": frame.iloc[index]["population"],
                    "score": float(scores[local]),
                    "flag_01": bool(scores[local] >= policy.threshold_01),
                    "flag_05": bool(scores[local] >= policy.threshold_05),
                    "flag_10": bool(scores[local] >= policy.threshold_10),
                    "opcode_count": int(len(store.row(int(index)))),
                    "retained_token_count": lca.retained_token_count(
                        store.row(int(index)), SPEC),
                    "token_budget": SPEC.token_budget,
                })
    return pd.DataFrame(rows)


def aggregate_external(predictions):
    external = predictions[
        predictions["population"] == "EXTERNAL_BENIGN_CONTROL"]
    fold_rows = (
        external.groupby(["model", "seed", "fold"], as_index=False)
        .agg(
            n=("sid", "size"),
            FPR_01=("flag_01", "mean"),
            FPR_05=("flag_05", "mean"),
            FPR_10=("flag_10", "mean"),
            score_mean=("score", "mean"),
            score_median=("score", "median"),
        )
    )
    per_seed = (
        fold_rows.groupby(["model", "seed"], as_index=False)
        [["FPR_01", "FPR_05", "FPR_10", "score_mean", "score_median"]]
        .mean()
    )
    row = {"model": MODEL, "n": int(external["sid"].nunique())}
    for metric in ("FPR_01", "FPR_05", "FPR_10", "score_mean", "score_median"):
        row[f"{metric}_mean"] = float(per_seed[metric].mean())
        row[f"{metric}_sd"] = float(per_seed[metric].std(ddof=0))
    return fold_rows, per_seed, pd.DataFrame([row])


def aggregate_qualitative(predictions):
    qualitative = predictions[
        predictions["population"] == "QUALITATIVE_CONTROL"]
    return (
        qualitative.groupby(["sid", "family_id"], as_index=False)
        .agg(
            models=("score", "size"),
            score_mean=("score", "mean"),
            score_min=("score", "min"),
            score_max=("score", "max"),
            fraction_flagged_05=("flag_05", "mean"),
            opcode_count=("opcode_count", "first"),
        )
    )


def raw_view(bytecode):
    chunks, _ = lca.opcode_chunks(bytecode, lca.CHUNK_SIZE, max_chunks=None)
    tokens = chunks.reshape(-1)
    tokens = tokens[tokens != lca.PAD_ID].astype(np.int64, copy=False)
    representation = lca.select_representation(tokens, SPEC)
    return {
        "chunks": torch.from_numpy(representation[None]),
        "chunk_mask": torch.ones((1, len(representation)), dtype=torch.bool),
        "dense": torch.zeros((1, 261), dtype=torch.float32),
        "ngram": torch.zeros((1, 512), dtype=torch.float32),
    }


def deterministic_latency_sample(primary, count):
    frame = primary.copy()
    frame["latency_key"] = frame["sample_id"].astype(str).map(
        lambda sid: hashlib.sha256(
            f"AUTHGUARD_30K_LATENCY_V1:{sid}".encode()).hexdigest())
    return frame.sort_values("latency_key").head(count).reset_index(drop=True)


def percentile_summary(values):
    values = np.asarray(values, dtype=float)
    return {
        "mean_ms": float(values.mean()),
        "median_ms": float(np.median(values)),
        "p90_ms": float(np.percentile(values, 90)),
        "p95_ms": float(np.percentile(values, 95)),
        "max_ms": float(values.max()),
    }


def measure_latency(primary, result_root, sample_count):
    checkpoint_path = os.path.join(
        result_root, "models", f"{MODEL}_seed7702_fold0.pt")
    model, checkpoint, policy = load_model(checkpoint_path)
    torch.set_num_threads(1)
    sample = deterministic_latency_sample(primary, sample_count)
    prepared = [raw_view(bytecode) for bytecode in sample["runtime_bytecode"].astype(str)]
    with torch.no_grad():
        for view in prepared[:20]:
            model(**view)

    model_times, checksum = [], 0.0
    with torch.no_grad():
        for view in prepared:
            started = time.perf_counter_ns()
            logit = model(**view)["risk_logit"]
            score = float(lca.fusion.probabilities(
                logit.numpy(), checkpoint["temperature"])[0])
            checksum += score
            model_times.append((time.perf_counter_ns() - started) / 1_000_000.0)

    end_to_end, levels = [], []
    with torch.no_grad():
        for bytecode in sample["runtime_bytecode"].astype(str):
            started = time.perf_counter_ns()
            view = raw_view(bytecode)
            logit = model(**view)["risk_logit"]
            score = float(lca.fusion.probabilities(
                logit.numpy(), checkpoint["temperature"])[0])
            levels.append(policy.level(score))
            end_to_end.append((time.perf_counter_ns() - started) / 1_000_000.0)

    return {
        "model": MODEL,
        "checkpoint": os.path.relpath(checkpoint_path, lca.ROOT),
        "checkpoint_bytes": os.path.getsize(checkpoint_path),
        "trainable_params": int(sum(p.numel() for p in model.parameters())),
        "sample_rows": len(sample),
        "sample_opcode_count": {
            "median": float(sample["opcode_count"].median()),
            "p95": float(sample["opcode_count"].quantile(0.95)),
            "max": int(sample["opcode_count"].max()),
        },
        "model_only": percentile_summary(model_times),
        "complete_local_path": percentile_summary(end_to_end),
        "complete_path_includes": [
            "normalization_and_linear_disassembly",
            "full_stream_budget_selection",
            "tensor_construction",
            "model_forward",
            "temperature_calibration",
            "warning_tier",
        ],
        "torch_threads": torch.get_num_threads(),
        "torch_version": torch.__version__,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "processor": platform.processor(),
        "score_checksum": checksum,
        "tier_counts": pd.Series(levels).value_counts().to_dict(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=DEFAULT_OUT)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--latency-sample", type=int, default=500)
    args = parser.parse_args()
    output = os.path.abspath(args.output_dir)
    os.makedirs(output, exist_ok=True)
    if lca.verify_frozen() != 0:
        raise RuntimeError("frozen-artifact verification failed")

    bench = pd.read_csv(lca.BENCH_PATH)
    external = bench[bench["population"] == "EXTERNAL_BENIGN_CONTROL"].reset_index(drop=True)
    qualitative = bench[bench["population"] == "QUALITATIVE_CONTROL"].reset_index(drop=True)
    controls = pd.concat([external, qualitative], ignore_index=True)
    primary = bench[bench["population"] == "PRIMARY_EVALUATION"].reset_index(drop=True)
    cache = os.path.join(output, "control_tokens.npz")
    store = get_control_store(controls, cache)
    predictions = score_controls(
        controls, store, RESULT_ROOT, args.batch_size)
    lca.atomic_csv(
        predictions,
        os.path.join(output, "control_predictions.csv.gz"),
        compression="gzip",
    )
    fold_rows, per_seed, summary = aggregate_external(predictions)
    lca.atomic_csv(fold_rows, os.path.join(output, "external_fold_metrics.csv"))
    lca.atomic_csv(per_seed, os.path.join(output, "external_seed_metrics.csv"))
    lca.atomic_csv(summary, os.path.join(output, "external_summary.csv"))
    qualitative_summary = aggregate_qualitative(predictions)
    lca.atomic_csv(
        qualitative_summary,
        os.path.join(output, "qualitative_summary.csv"),
    )
    runtime = measure_latency(primary, RESULT_ROOT, args.latency_sample)
    lca.atomic_json(runtime, os.path.join(output, "runtime.json"))
    if lca.verify_frozen() != 0:
        raise RuntimeError("frozen-artifact verification failed after operational run")
    print(summary.to_string(index=False), flush=True)
    print(
        f"[operational] latency median="
        f"{runtime['complete_local_path']['median_ms']:.3f}ms "
        f"checkpoint={runtime['checkpoint_bytes']} bytes",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

