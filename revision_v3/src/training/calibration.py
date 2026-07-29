"""Single-scalar temperature scaling fit on VALIDATION logits only. Independent implementation."""
from __future__ import annotations

import torch


def fit_temperature(val_logits: torch.Tensor, val_labels: torch.Tensor, max_iter: int = 100) -> float:
    temperature = torch.nn.Parameter(torch.ones(1, dtype=torch.float32))
    optimizer = torch.optim.LBFGS([temperature], lr=0.05, max_iter=max_iter)
    loss_fn = torch.nn.BCEWithLogitsLoss()

    def closure():
        optimizer.zero_grad()
        loss = loss_fn(val_logits / temperature.clamp(min=1e-3), val_labels)
        loss.backward()
        return loss

    optimizer.step(closure)
    return float(temperature.detach().clamp(min=1e-3).item())


def apply_temperature(logits: torch.Tensor, temperature: float) -> torch.Tensor:
    return torch.sigmoid(logits / max(temperature, 1e-3))
