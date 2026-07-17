#!/usr/bin/env python3
from __future__ import annotations

import os
import sys

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
RV2 = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, RV2)

from authguard7702.features import AUXILIARY_FACTORS, collate_encoded, encode_bytecode
from authguard7702.model import AuthGuardFusion
from authguard7702.policy import WarningPolicy, threshold_at_fpr
from authguard7702.scorer import AuthGuardScorer


def test_feature_shapes_and_factor_evidence():
    # PUSH4 transfer selector, SSTORE, CALL, STOP
    row = encode_bytecode("63a9059cbb55f100", chunk_size=4)
    assert row.dense.shape == (261,)
    assert row.ngram.shape == (512,)
    assert row.auxiliary.shape == (len(AUXILIARY_FACTORS),)
    assert row.evidence["observed_factors"]["external_call_surface"]
    assert row.evidence["observed_factors"]["state_write_surface"]
    assert row.evidence["observed_factors"]["token_movement_selector_surface"]


def test_model_forward_and_attention():
    rows = [encode_bytecode("6001600055f100", chunk_size=4),
            encode_bytecode("60006000f400", chunk_size=4)]
    batch = collate_encoded(rows)
    model = AuthGuardFusion().eval()
    with torch.no_grad():
        output = model(torch.from_numpy(batch["chunks"]),
                       torch.from_numpy(batch["chunk_mask"]),
                       torch.from_numpy(batch["dense"]),
                       torch.from_numpy(batch["ngram"]))
    assert output["risk_logit"].shape == (2,)
    assert output["auxiliary_logits"].shape == (2, len(AUXILIARY_FACTORS))
    assert output["view_weights"].shape == (2, 3)
    assert torch.allclose(output["view_weights"].sum(1), torch.ones(2), atol=1e-6)
    assert torch.allclose(output["chunk_attention"].sum(1), torch.ones(2), atol=1e-6)


def test_warning_policy_is_monotone_and_bounded():
    scores = np.linspace(0.0, 1.0, 101)
    policy = WarningPolicy.from_validation_negatives(scores)
    assert policy.threshold_01 >= policy.threshold_05 >= policy.threshold_10
    for target in (0.01, 0.05, 0.10):
        threshold = threshold_at_fpr(scores, target)
        assert float((scores >= threshold).mean()) <= target + 1e-12
    assert policy.level(1.1) == "high"
    assert policy.level(-0.1) == "low_observed_risk"


def test_operational_scorer_emits_structured_evidence(tmp_path):
    model = AuthGuardFusion()
    artifact = {
        "model": model.state_dict(),
        "config": model.config.to_dict(),
        "dense_mean": torch.zeros(261),
        "dense_scale": torch.ones(261),
        "temperature": torch.tensor(1.0),
        "policy": {"fpr_01": 0.9, "fpr_05": 0.7, "fpr_10": 0.5},
        "factor_order": list(AUXILIARY_FACTORS),
        "auxiliary_trained": True,
        "preprocessing": {"chunk_size": 4, "max_chunks": 8},
    }
    path = tmp_path / "model.pt"
    torch.save(artifact, path)
    result = AuthGuardScorer(str(path)).score_bytecode("63a9059cbb55f100")
    assert 0.0 <= result["risk_score"] <= 1.0
    assert result["warning_level"] in {"high", "warning", "caution", "low_observed_risk"}
    assert result["observed_evidence"]["observed_factors"]["external_call_surface"]
    assert set(result["predicted_risk_factors"]) == set(AUXILIARY_FACTORS)
    assert "scope_notice" in result
