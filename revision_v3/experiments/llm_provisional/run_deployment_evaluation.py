"""Part 14: deployment evaluation for the Phase 2 frozen model (authguard_sequence_dense),
the provisional selected model (same architecture, fine-tuned weights), and the sequence-only
reference (authguard_reference_v3). Real repeated-measurement latency/memory benchmarks on
this machine's actual CPU and GPU (if present), plus an ONNX export attempt.

Does not modify any Phase 1/2 checkpoint or config.

Usage:
    python3 revision_v3/experiments/llm_provisional/run_deployment_evaluation.py
"""
from __future__ import annotations

import io
import json
import os
import platform
import sys
import time

import numpy as np
import torch

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "revision_v3", "src"))

from evaluation import model_runtime  # noqa: E402
from features.disassembler import linear_sweep, normalize_hex  # noqa: E402
from features.encode import encode_bytecode  # noqa: E402
from reporting.model_complexity import (  # noqa: E402
    active_params, checkpoint_size_bytes, median_forward_latency_ms,
    peak_inference_memory_bytes, state_dict_size_bytes, total_and_trainable_params,
)

HUMAN_EVAL_DIR = os.path.join(REPO_ROOT, "revision_v3", "human_eval")
RESULTS_DIR = os.path.join(REPO_ROOT, "revision_v3", "results", "deployment")
os.makedirs(RESULTS_DIR, exist_ok=True)

MODELS_TO_EVALUATE = ["authguard_sequence_dense", "authguard_reference_v3"]
N_LATENCY_CALLS = 200
WARMUP = 20


def load_sample_bytecodes(n: int = 20) -> list[str]:
    import csv
    with open(os.path.join(HUMAN_EVAL_DIR, "pilot_manifest.csv"), newline="") as f:
        rows = list(csv.DictReader(f))
    return [r["runtime_bytecode"] for r in rows[:n]]


def percentiles(timings_ms: list[float]) -> dict:
    arr = np.asarray(timings_ms)
    return {"median_ms": float(np.median(arr)), "p95_ms": float(np.percentile(arr, 95)),
            "p99_ms": float(np.percentile(arr, 99)), "mean_ms": float(arr.mean())}


def time_calls(fn, n_calls=N_LATENCY_CALLS, warmup=WARMUP) -> dict:
    for _ in range(warmup):
        fn()
    timings = []
    for _ in range(n_calls):
        t0 = time.perf_counter()
        fn()
        timings.append((time.perf_counter() - t0) * 1000.0)
    return percentiles(timings)


def build_batch_for_hybrid(hex_bc: str, device):
    enc = encode_bytecode(hex_bc, chunk_size=256, max_chunks=64)
    chunks = torch.as_tensor(enc.chunks[None, :, :].astype(np.int64)).to(device)
    mask = torch.as_tensor(enc.chunk_mask[None, :]).to(device)
    dense = torch.as_tensor(enc.dense[None, :]).to(device)
    return chunks, mask, dense


def evaluate_model_on_device(model_name: str, device: torch.device, sample_bytecodes: list[str]) -> dict:
    spec = model_runtime.MODEL_REGISTRY[model_name]
    ckpt_path = os.path.join(spec["checkpoint_dir"], f"{model_name}_seed7702_fold0.pt")
    ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
    model = model_runtime.build_model(spec)
    model.load_state_dict(ckpt["model_state_dict"])
    model.to(device).eval()

    total, trainable = total_and_trainable_params(model)
    ckpt_bytes = checkpoint_size_bytes(model, {"model_name": model_name})
    state_bytes = state_dict_size_bytes(model)

    sample_hex = sample_bytecodes[0]

    def preprocess_only():
        return encode_bytecode(sample_hex, chunk_size=256, max_chunks=64)

    def forward_only():
        chunks, mask, dense = build_batch_for_hybrid(sample_hex, device) if spec["kind"] == "hybrid" else (None, None, None)
        with torch.no_grad():
            if spec["kind"] == "hybrid":
                return model(chunks.long(), mask.bool(), dense=dense)
            hex_norm = normalize_hex(sample_hex)
            tokens, _, _ = linear_sweep(hex_norm)
            from features.encode import tokens_to_ids, chunk_token_ids
            ids = tokens_to_ids(tokens)
            chunks_arr = chunk_token_ids(ids, 256, 64)
            mask_arr = np.ones(len(chunks_arr), dtype=np.bool_)
            c = torch.as_tensor(chunks_arr[None, :, :].astype(np.int64)).to(device)
            m = torch.as_tensor(mask_arr[None, :]).to(device)
            from models.forward_fns import chunk_forward
            return chunk_forward(model, {"chunks": c, "chunk_mask": m})

    def end_to_end(hex_bc: str = sample_hex):
        model_runtime.score_one(spec, model, device, hex_bc)

    preprocess_timing = time_calls(preprocess_only, n_calls=100, warmup=10)
    forward_timing = time_calls(forward_only, n_calls=N_LATENCY_CALLS, warmup=WARMUP)
    e2e_timing = time_calls(end_to_end, n_calls=100, warmup=10)

    peak_mem = None
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)
        forward_only()
        torch.cuda.synchronize()
        peak_mem = int(torch.cuda.max_memory_allocated(device))

    # batch throughput (batch of len(sample_bytecodes))
    t0 = time.perf_counter()
    for hex_bc in sample_bytecodes:
        model_runtime.score_one(spec, model, device, hex_bc)
    batch_elapsed = time.perf_counter() - t0
    throughput = len(sample_bytecodes) / batch_elapsed

    return {
        "device": str(device),
        "total_params": total, "trainable_params": trainable,
        "checkpoint_size_bytes": ckpt_bytes, "state_dict_size_bytes": state_bytes,
        "preprocessing_latency_ms": preprocess_timing,
        "forward_latency_ms": forward_timing,
        "end_to_end_latency_ms": e2e_timing,
        "peak_memory_bytes": peak_mem,
        "batch_throughput_items_per_sec": throughput,
        "batch_size_used_for_throughput": len(sample_bytecodes),
    }


def try_onnx_export(model_name: str, device: torch.device) -> dict:
    spec = model_runtime.MODEL_REGISTRY[model_name]
    ckpt_path = os.path.join(spec["checkpoint_dir"], f"{model_name}_seed7702_fold0.pt")
    ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    model = model_runtime.build_model(spec)
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()

    dummy_chunks = torch.zeros((1, 64, 256), dtype=torch.long)
    dummy_mask = torch.ones((1, 64), dtype=torch.bool)
    dummy_dense = torch.zeros((1, 261), dtype=torch.float32)

    buf = io.BytesIO()
    try:
        if spec["kind"] == "hybrid":
            torch.onnx.export(
                model, (dummy_chunks, dummy_mask, dummy_dense), buf,
                input_names=["chunks", "chunk_mask", "dense"], output_names=["logit"],
                opset_version=17, dynamo=False,
            )
        else:
            torch.onnx.export(model, (dummy_chunks, dummy_mask), buf,
                               input_names=["chunks", "chunk_mask"], output_names=["logit"],
                               opset_version=17, dynamo=False)
        onnx_bytes = buf.getbuffer().nbytes
    except Exception as e:  # noqa: BLE001
        return {"export_succeeded": False, "error": str(e)}

    result = {"export_succeeded": True, "onnx_size_bytes": onnx_bytes}
    try:
        import onnxruntime as ort  # noqa: F401
        buf.seek(0)
        sess = ort.InferenceSession(buf.read(), providers=["CPUExecutionProvider"])
        feed = {"chunks": dummy_chunks.numpy(), "chunk_mask": dummy_mask.numpy(),
                "dense": dummy_dense.numpy()} if spec["kind"] == "hybrid" else {
            "chunks": dummy_chunks.numpy(), "chunk_mask": dummy_mask.numpy()}
        with torch.no_grad():
            torch_out = model(dummy_chunks, dummy_mask, dense=dummy_dense) if spec["kind"] == "hybrid" \
                else model(dummy_chunks, dummy_mask)
        onnx_out = sess.run(None, feed)[0]
        max_abs_diff = float(np.max(np.abs(onnx_out.flatten() - torch_out.numpy().flatten())))
        result["onnxruntime_available"] = True
        result["numerical_parity_max_abs_diff"] = max_abs_diff

        def onnx_forward():
            sess.run(None, feed)
        result["onnx_cpu_latency_ms"] = time_calls(onnx_forward, n_calls=100, warmup=10)
    except ImportError:
        result["onnxruntime_available"] = False
        result["note"] = "onnxruntime not installed in this environment; export succeeded but inference-parity/latency not measured"
    except Exception as e:  # noqa: BLE001
        result["onnxruntime_available"] = True
        result["onnx_inference_error"] = str(e)
    return result


def main() -> int:
    sample_bytecodes = load_sample_bytecodes(20)
    report = {
        "environment": {
            "hardware_cpu": platform.processor() or platform.machine(),
            "os": f"{platform.system()} {platform.release()}",
            "python_version": platform.python_version(),
            "torch_version": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
            "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
            "thread_count": torch.get_num_threads(),
            "batch_size_for_throughput": len(sample_bytecodes),
            "input_length_distribution_bytes": {
                "min": min(len(b) // 2 for b in sample_bytecodes),
                "max": max(len(b) // 2 for b in sample_bytecodes),
                "mean": float(np.mean([len(b) // 2 for b in sample_bytecodes])),
            },
        },
        "models": {},
    }

    devices = [torch.device("cpu")]
    if torch.cuda.is_available():
        devices.append(torch.device("cuda"))

    for model_name in MODELS_TO_EVALUATE:
        report["models"][model_name] = {}
        for device in devices:
            print(f"[deployment] {model_name} on {device}...")
            report["models"][model_name][str(device)] = evaluate_model_on_device(model_name, device, sample_bytecodes)
        print(f"[deployment] {model_name} ONNX export attempt...")
        report["models"][model_name]["onnx"] = try_onnx_export(model_name, devices[0])

    out_path = os.path.join(RESULTS_DIR, "deployment_report.json")
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nWrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
