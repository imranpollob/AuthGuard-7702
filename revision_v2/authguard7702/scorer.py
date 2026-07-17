"""Operational AuthGuard-7702 scorer for trained AuthGuard-Fusion artifacts."""
from __future__ import annotations

import hashlib
import json
import time
import urllib.request

import numpy as np
import torch

from .features import (AUXILIARY_FACTORS, encode_bytecode, encode_sequence_bytecode,
                       normalize_bytecode)
from .model import AuthGuardFusion, FusionConfig
from .policy import WarningPolicy


def _json_rpc(url: str, method: str, params: list, timeout: float = 20.0):
    request = urllib.request.Request(
        url,
        data=json.dumps({"jsonrpc": "2.0", "id": 7702,
                         "method": method, "params": params}).encode(),
        headers={"Content-Type": "application/json",
                 "User-Agent": "AuthGuard-7702 research scorer"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode())
    if "error" in payload:
        raise RuntimeError(f"RPC error: {payload['error']}")
    return payload["result"]


class AuthGuardScorer:
    def __init__(self, artifact_path: str, device: str = "cpu"):
        self.device = torch.device(device)
        artifact = torch.load(artifact_path, map_location=self.device, weights_only=True)
        self.config = FusionConfig(**artifact["config"])
        self.model = AuthGuardFusion(self.config).to(self.device)
        self.model.load_state_dict(artifact["model"])
        self.model.eval()
        self.dense_mean = artifact["dense_mean"].cpu().numpy()
        self.dense_scale = artifact["dense_scale"].cpu().numpy()
        self.temperature = float(artifact["temperature"])
        policy = artifact["policy"]
        self.policy = WarningPolicy(policy["fpr_01"], policy["fpr_05"], policy["fpr_10"])
        preprocessing = artifact.get("preprocessing", {})
        self.chunk_size = int(preprocessing.get("chunk_size", 256))
        self.max_chunks = int(preprocessing.get("max_chunks", 64))
        self.factor_order = tuple(artifact.get("factor_order", AUXILIARY_FACTORS))
        self.auxiliary_trained = bool(artifact.get("auxiliary_trained", False))
        self.artifact_path = artifact_path

    def score_bytecode(self, bytecode: str, target: str | None = None) -> dict:
        started = time.perf_counter_ns()
        normalized = normalize_bytecode(bytecode)
        if not normalized:
            raise ValueError("delegate runtime bytecode is empty")
        if self.config.active_views == (True, False, False):
            encoded = encode_sequence_bytecode(normalized, self.chunk_size, self.max_chunks)
        else:
            encoded = encode_bytecode(normalized, self.chunk_size, self.max_chunks)
        chunks = torch.from_numpy(encoded.chunks).unsqueeze(0).to(self.device)
        mask = torch.ones((1, len(encoded.chunks)), dtype=torch.bool, device=self.device)
        dense = torch.from_numpy(
            ((encoded.dense - self.dense_mean) / self.dense_scale).astype(np.float32)
        ).unsqueeze(0).to(self.device)
        ngram = torch.from_numpy(encoded.ngram).unsqueeze(0).to(self.device)
        with torch.no_grad():
            output = self.model(chunks, mask, dense, ngram)
            risk = torch.sigmoid(output["risk_logit"] / self.temperature).item()
            factors = torch.sigmoid(output["auxiliary_logits"])[0].cpu().numpy()
            view_weights = output["view_weights"][0].cpu().numpy()
            chunk_attention = output["chunk_attention"][0].cpu().numpy()
        elapsed_ms = (time.perf_counter_ns() - started) / 1e6
        top_chunks = np.argsort(-chunk_attention)[:min(3, len(chunk_attention))]
        result = {
            "schema_version": "authguard-7702-score-v1",
            "target": target,
            "bytecode_sha256": hashlib.sha256(normalized.encode()).hexdigest(),
            "risk_score": float(risk),
            "warning_level": self.policy.level(risk),
            "warning_policy": self.policy.to_dict(),
            "observed_evidence": encoded.evidence,
            "model_view_weights": {
                "opcode_sequence": float(view_weights[0]),
                "hashed_4gram": float(view_weights[1]),
                "structural": float(view_weights[2]),
            },
            "top_opcode_chunks": [int(index) for index in top_chunks],
            "local_scorer_ms": float(elapsed_ms),
            "scope_notice": (
                "A low score is not a safety guarantee. Observed factors are static bytecode "
                "surfaces and do not establish reachability or malicious intent."
            ),
        }
        if self.auxiliary_trained:
            result["predicted_risk_factors"] = {
                name: float(value) for name, value in zip(self.factor_order, factors)
            }
        return result

    def score_address(self, address: str, rpc_url: str, block: str = "latest") -> dict:
        code = _json_rpc(rpc_url, "eth_getCode", [address, block])
        result = self.score_bytecode(code, target=address)
        result["input_mode"] = "delegate_address"
        result["block"] = block
        return result

    def score_authorization(self, authorization: dict, rpc_url: str,
                            block: str = "latest") -> dict:
        candidate = authorization
        if "authorizationList" in candidate:
            values = candidate["authorizationList"]
            if len(values) != 1:
                raise ValueError("score one authorization entry at a time")
            candidate = values[0]
        address = candidate.get("address") or candidate.get("delegate")
        if not address:
            raise ValueError("authorization object does not contain a delegate address")
        result = self.score_address(address, rpc_url, block)
        result["input_mode"] = "eip7702_authorization"
        result["authorization_context"] = {
            key: candidate.get(key) for key in ("chainId", "chain_id", "nonce")
            if key in candidate
        }
        return result
