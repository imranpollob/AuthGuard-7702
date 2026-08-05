"""Parameter/complexity accounting across the frozen Revision v2 AuthGuardFusion and every
Revision v3 model (reference, controlled ablation, exploratory hybrids). Read-only import of
revision_v2's model module for comparison purposes only.
"""
from __future__ import annotations

import json
import os
import sys

import pandas as pd
import torch

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "revision_v3", "src"))
sys.path.insert(0, os.path.join(REPO_ROOT, "revision_v2"))

from features.encode import VOCAB_SIZE  # noqa: E402
from models.chunk_model import ChunkModel, ChunkModelConfig  # noqa: E402
from models.flat_cnn import FlatCNN, FlatCNNConfig  # noqa: E402
from models.hybrid import HybridConfig, HybridModel  # noqa: E402
from reporting.model_complexity import (  # noqa: E402
    active_params, checkpoint_size_bytes, median_forward_latency_ms,
    peak_inference_memory_bytes, state_dict_size_bytes, total_and_trainable_params,
)

RESULTS_DIR = os.path.join(REPO_ROOT, "revision_v3", "results")
BATCH = 8


def measure(name: str, model: torch.nn.Module, forward_call, config: dict, device) -> dict:
    model.to(device)
    total, trainable = total_and_trainable_params(model)
    active = active_params(model, forward_call)
    ckpt = checkpoint_size_bytes(model, config)
    state = state_dict_size_bytes(model)
    peak_mem = peak_inference_memory_bytes(forward_call, device)
    latency = median_forward_latency_ms(forward_call, device, n_calls=100, warmup=10)
    return {
        "model": name,
        "total_instantiated_params": total,
        "trainable_params": trainable,
        "active_forward_params": active,
        "checkpoint_size_bytes": ckpt,
        "model_state_size_bytes": state,
        "peak_inference_memory_bytes": peak_mem,
        "median_forward_latency_ms": latency,
        "config": json.dumps(config),
    }


def main() -> int:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    rows = []

    # --- Revision v2 AuthGuardFusion, for direct comparison (read-only import) ---
    from authguard7702.model import AuthGuardFusion, FusionConfig

    v2_full_config = FusionConfig()
    v2_full = AuthGuardFusion(v2_full_config)

    def v2_full_forward():
        chunks = torch.randint(0, v2_full_config.vocab_size, (BATCH, 10, 256), device=device)
        mask = torch.ones(BATCH, 10, dtype=torch.bool, device=device)
        dense = torch.randn(BATCH, v2_full_config.dense_dim, device=device)
        ngram = torch.randn(BATCH, v2_full_config.ngram_dim, device=device)
        return v2_full(chunks, mask, dense, ngram)["risk_logit"]

    rows.append(measure("v2_authguardfusion_all_views_active", v2_full, v2_full_forward, v2_full_config.to_dict(), device))

    v2_seq_config = FusionConfig(active_views=(True, False, False))
    v2_seq = AuthGuardFusion(v2_seq_config)

    def v2_seq_forward():
        chunks = torch.randint(0, v2_seq_config.vocab_size, (BATCH, 10, 256), device=device)
        mask = torch.ones(BATCH, 10, dtype=torch.bool, device=device)
        dense = torch.randn(BATCH, v2_seq_config.dense_dim, device=device)
        ngram = torch.randn(BATCH, v2_seq_config.ngram_dim, device=device)
        return v2_seq(chunks, mask, dense, ngram)["risk_logit"]

    rows.append(measure("v2_authguard_seq_as_reported_181877", v2_seq, v2_seq_forward, v2_seq_config.to_dict(), device))

    # --- Revision v3 authguard_reference_v3 (standalone, no dead branches) ---
    ref_cfg = ChunkModelConfig(vocab_size=VOCAB_SIZE, chunk_size=256, max_chunks=64, aggregation="attention")
    ref_model = ChunkModel(ref_cfg)

    def chunk_forward_dummy(cfg, model):
        def _f():
            chunks = torch.randint(0, VOCAB_SIZE, (BATCH, cfg.max_chunks, cfg.chunk_size), device=device)
            mask = torch.ones(BATCH, cfg.max_chunks, dtype=torch.bool, device=device)
            logits, _ = model(chunks, mask)
            return logits
        return _f

    rows.append(measure("authguard_reference_v3_standalone", ref_model, chunk_forward_dummy(ref_cfg, ref_model),
                         ref_cfg.__dict__, device))

    # --- controlled ablation models ---
    for budget, max_chunks in [(2048, 8), (8192, 32), (16384, 64)]:
        flat_cfg = FlatCNNConfig(vocab_size=VOCAB_SIZE, max_len=budget)
        flat_model = FlatCNN(flat_cfg)

        def flat_forward_dummy(cfg=flat_cfg, model=flat_model):
            def _f():
                tokens = torch.randint(0, VOCAB_SIZE, (BATCH, cfg.max_len), device=device)
                return model(tokens)
            return _f

        rows.append(measure(f"flat_cnn_{budget}", flat_model, flat_forward_dummy(), flat_cfg.__dict__, device))

        for agg in ["mean", "max", "attention"]:
            if budget != 16384 and agg == "max":
                continue  # chunk_max only defined at 16384 in the controlled grid
            if budget != 2048 and budget != 8192 and agg not in ("mean", "attention", "max"):
                continue
            chunk_cfg = ChunkModelConfig(vocab_size=VOCAB_SIZE, chunk_size=256, max_chunks=max_chunks, aggregation=agg)
            chunk_model = ChunkModel(chunk_cfg)
            rows.append(measure(f"chunk_{agg}_{budget}", chunk_model, chunk_forward_dummy(chunk_cfg, chunk_model),
                                 chunk_cfg.__dict__, device))

    # --- exploratory hybrid candidates ---
    hybrid_specs = [
        ("authguard_multiscale", dict(use_multiscale=True)),
        ("authguard_sequence_dense", dict(use_dense=True)),
        ("authguard_sequence_ngram", dict(use_ngram=True)),
        ("authguard_all_views", dict(use_dense=True, use_ngram=True)),
    ]
    for name, kwargs in hybrid_specs:
        cfg = HybridConfig(vocab_size=VOCAB_SIZE, chunk_size=256, max_chunks=64, **kwargs)
        model = HybridModel(cfg)

        def hybrid_forward_dummy(cfg=cfg, model=model):
            def _f():
                chunks = torch.randint(0, VOCAB_SIZE, (BATCH, cfg.max_chunks, cfg.chunk_size), device=device)
                mask = torch.ones(BATCH, cfg.max_chunks, dtype=torch.bool, device=device)
                dense = torch.randn(BATCH, cfg.dense_dim, device=device) if cfg.use_dense else None
                ngram = torch.randn(BATCH, cfg.ngram_dim, device=device) if cfg.use_ngram else None
                return model(chunks, mask, dense=dense, ngram=ngram)
            return _f

        rows.append(measure(name, model, hybrid_forward_dummy(), cfg.__dict__, device))

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(RESULTS_DIR, "model_complexity.csv"), index=False)
    print(df[["model", "total_instantiated_params", "trainable_params", "active_forward_params",
              "checkpoint_size_bytes", "median_forward_latency_ms"]].to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
