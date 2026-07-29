"""Parameter/complexity accounting: total instantiated, trainable, and forward-ACTIVE
parameter counts (active = parameters that actually receive a nonzero gradient from one
forward+backward pass on a real dummy batch -- not just requires_grad=True), checkpoint
size, model-state size, and forward latency, for every Revision v3 model plus the frozen
Revision v2 AuthGuardFusion for direct comparison.
"""
from __future__ import annotations

import io
import os
import time

import numpy as np
import torch
from torch import nn


def total_and_trainable_params(model: nn.Module) -> tuple[int, int]:
    total = sum(p.numel() for p in model.parameters())
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    return total, trainable


def active_params(model: nn.Module, forward_call, loss_fn=None) -> int:
    """Runs forward_call() -> logits, backward()s a BCE loss against random labels, and
    sums numel() over every parameter whose .grad is not None and has any nonzero entry."""
    model.zero_grad(set_to_none=True)
    logits = forward_call()
    labels = torch.randint(0, 2, logits.shape, dtype=torch.float32, device=logits.device)
    loss = (loss_fn or nn.BCEWithLogitsLoss())(logits, labels)
    loss.backward()
    active = 0
    for p in model.parameters():
        if p.grad is not None and torch.any(p.grad != 0):
            active += p.numel()
    return active


def state_dict_size_bytes(model: nn.Module) -> int:
    buffer = io.BytesIO()
    torch.save(model.state_dict(), buffer)
    return buffer.getbuffer().nbytes


def checkpoint_size_bytes(model: nn.Module, config: dict) -> int:
    buffer = io.BytesIO()
    torch.save({"model_state_dict": model.state_dict(), "config": config}, buffer)
    return buffer.getbuffer().nbytes


def peak_inference_memory_bytes(forward_call, device: torch.device) -> int | None:
    if device.type != "cuda":
        return None
    torch.cuda.reset_peak_memory_stats(device)
    with torch.no_grad():
        forward_call()
    return int(torch.cuda.max_memory_allocated(device))


def median_forward_latency_ms(forward_call, device: torch.device, n_calls: int = 100, warmup: int = 10) -> float:
    with torch.no_grad():
        for _ in range(warmup):
            forward_call()
        if device.type == "cuda":
            torch.cuda.synchronize()
        timings = []
        for _ in range(n_calls):
            t0 = time.perf_counter()
            forward_call()
            if device.type == "cuda":
                torch.cuda.synchronize()
            timings.append((time.perf_counter() - t0) * 1000.0)
    return float(np.median(timings))
