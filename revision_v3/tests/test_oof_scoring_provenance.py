"""Validity tests for human-reference checkpoint provenance.

Benchmark members must be scored only by the checkpoint whose outer test fold contains their
family.  An all-fold ensemble is allowed solely for families independently verified external
to the canonical training population.
"""
from __future__ import annotations

import numpy as np
import pytest
import torch

from data.loader import canonical_family_ids, family_to_fold_map, fold_ids_for_families
from evaluation import model_runtime
from evaluation.metrics import metrics_at_threshold
from evaluation.metrics_extra import confusion_matrix


def test_every_canonical_family_maps_to_exactly_one_fold():
    mapping = family_to_fold_map()
    assert len(mapping) == 790
    assert set(mapping.values()) == {0, 1, 2, 3, 4}
    sample = list(mapping)[:8]
    assert fold_ids_for_families(sample) == [mapping[family_id] for family_id in sample]
    assert set(mapping).issubset(canonical_family_ids())
    assert "F00217" in canonical_family_ids() and "F00217" not in mapping


def test_unknown_family_cannot_silently_be_treated_as_external():
    with pytest.raises(KeyError, match="not in the canonical primary population"):
        fold_ids_for_families(["F_DOES_NOT_EXIST"])


def test_oof_scoring_loads_only_each_items_held_out_checkpoint(monkeypatch):
    model_name = "test_model"
    monkeypatch.setitem(model_runtime.MODEL_REGISTRY, model_name, {"kind": "test"})
    monkeypatch.setattr(model_runtime, "SEEDS", (101, 102))
    loaded = []

    def fake_load(name, seed, test_fold, device):
        assert name == model_name
        loaded.append((seed, test_fold))
        checkpoint = {
            "seed": seed,
            "test_fold": test_fold,
            "temperature": 1.0,
            "threshold_5pct": test_fold / 10 + seed / 10000,
        }
        return {"kind": "test"}, (seed, test_fold), checkpoint

    def fake_score(spec, model, device, bytecode):
        seed, fold = model
        return float(int(bytecode) + seed + 100 * fold)

    monkeypatch.setattr(model_runtime, "_load_checkpoint_model", fake_load)
    monkeypatch.setattr(model_runtime, "score_one", fake_score)
    monkeypatch.setattr(model_runtime, "apply_temperature", lambda value, temperature: value)

    scores, thresholds = model_runtime.score_dataset_out_of_fold(
        model_name, ["10", "20", "30", "40"], [3, 1, 3, 0], device=torch.device("cpu")
    )

    assert loaded == [(101, 0), (101, 1), (101, 3), (102, 0), (102, 1), (102, 3)]
    np.testing.assert_allclose(scores[101], [411, 221, 431, 141])
    np.testing.assert_allclose(scores[102], [412, 222, 432, 142])
    np.testing.assert_allclose(thresholds[101], [0.3101, 0.1101, 0.3101, 0.0101])


def test_all_fold_ensemble_requires_explicit_external_provenance():
    with pytest.raises(ValueError, match="verified external families"):
        model_runtime.score_dataset_with_ensemble(
            "authguard_reference_v3", ["00"], device=torch.device("cpu")
        )


def test_metrics_accept_item_specific_oof_thresholds():
    y_true = np.array([1, 1, 0, 0])
    scores = np.array([0.8, 0.4, 0.7, 0.2])
    thresholds = np.array([0.7, 0.3, 0.8, 0.1])
    assert confusion_matrix(y_true, scores, thresholds) == {"tp": 2, "fp": 1, "tn": 1, "fn": 0}
    report = metrics_at_threshold(y_true, scores, thresholds)
    assert report["recall"] == 1.0
    assert report["observed_fpr"] == 0.5


def test_mixed_provenance_scoring_uses_oof_and_checkpoint_votes(monkeypatch):
    model_name = "test_model"
    monkeypatch.setitem(model_runtime.MODEL_REGISTRY, model_name, {"kind": "test"})
    monkeypatch.setattr(model_runtime, "SEEDS", (101,))
    monkeypatch.setattr(model_runtime, "family_to_fold_map", lambda: {"F1": 2})
    monkeypatch.setattr(model_runtime, "canonical_family_ids", lambda: {"F1"})

    def fake_oof(name, bytecodes, folds, device=None):
        assert name == model_name
        assert bytecodes == ["known"]
        assert folds == [2]
        return {101: np.array([0.9])}, {101: np.array([0.7])}

    def fake_load(name, seed, test_fold, device):
        return {"kind": "test"}, test_fold, {
            "temperature": 1.0, "threshold_5pct": 0.25
        }

    monkeypatch.setattr(model_runtime, "score_dataset_out_of_fold", fake_oof)
    monkeypatch.setattr(model_runtime, "_load_checkpoint_model", fake_load)
    monkeypatch.setattr(
        model_runtime, "score_one", lambda spec, model, device, bytecode: model / 10
    )
    monkeypatch.setattr(model_runtime, "apply_temperature", lambda value, temperature: value)

    result = model_runtime.score_dataset_provenance_aware(
        model_name, ["known", "external"], ["F1", None], device=torch.device("cpu")
    )

    np.testing.assert_allclose(result["scores_by_seed"][101], [0.9, 0.2])
    np.testing.assert_allclose(result["thresholds_by_seed"][101], [0.7, 0.25])
    np.testing.assert_allclose(result["decision_fraction"], [1.0, 0.4])
    assert result["score_source_by_item"] == [
        "canonical_family_oof:test_fold=2", "verified_external:five_fold_ensemble"
    ]
    assert result["n_canonical_family_items"] == 1
    assert result["n_verified_external_items"] == 1


def test_mixed_provenance_rejects_unknown_nonempty_family(monkeypatch):
    monkeypatch.setattr(model_runtime, "family_to_fold_map", lambda: {"F1": 2})
    monkeypatch.setattr(model_runtime, "canonical_family_ids", lambda: {"F1", "CONTROL"})
    with pytest.raises(KeyError, match="not in the canonical primary population"):
        model_runtime.score_dataset_provenance_aware(
            "authguard_reference_v3", ["00"], ["TYPO_FAMILY"],
            device=torch.device("cpu")
        )


def test_canonical_non_primary_family_is_valid_external(monkeypatch):
    model_name = "test_model"
    monkeypatch.setitem(model_runtime.MODEL_REGISTRY, model_name, {"kind": "test"})
    monkeypatch.setattr(model_runtime, "SEEDS", (101,))
    monkeypatch.setattr(model_runtime, "family_to_fold_map", lambda: {"F1": 2})
    monkeypatch.setattr(model_runtime, "canonical_family_ids", lambda: {"F1", "CONTROL"})
    monkeypatch.setattr(
        model_runtime, "_load_checkpoint_model",
        lambda name, seed, test_fold, device: (
            {"kind": "test"}, test_fold,
            {"temperature": 1.0, "threshold_5pct": 0.25},
        ),
    )
    monkeypatch.setattr(
        model_runtime, "score_one", lambda spec, model, device, bytecode: model / 10
    )
    monkeypatch.setattr(model_runtime, "apply_temperature", lambda value, temperature: value)

    result = model_runtime.score_dataset_provenance_aware(
        model_name, ["control"], ["CONTROL"], device=torch.device("cpu")
    )
    assert result["score_source_by_item"] == [
        "canonical_non_primary:five_fold_ensemble"
    ]
    assert result["n_canonical_non_primary_items"] == 1
    assert result["n_verified_external_items"] == 0
