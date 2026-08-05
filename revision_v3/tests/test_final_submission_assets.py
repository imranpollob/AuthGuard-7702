from __future__ import annotations

import copy

import pytest

from revision_v3.experiments.reporting.generate_final_submission_assets import build_latex_macros


def _reports(ci_low=0.01):
    counts = {
        "UNSAFE": 60,
        "NO_CONCRETE_UNSAFE_BEHAVIOR_FOUND": 80,
        "INDETERMINATE": 8,
        "NOT_BYTECODE_SCREENABLE": 2,
    }
    reliability = {"raw_agreement_rate": 0.82, "cohens_kappa": 0.63}
    primary = {
        "status": "HUMAN_FINAL_EVALUATION",
        "sample_set": "postcutoff",
        "n_manifest_items": 150,
        "n_finalized_items": 150,
        "n_scored_finalized_items": 149,
        "n_binary_items": 139,
        "final_label_counts": counts,
        "inter_rater_reliability": reliability,
        "dcrg_evaluation": {"models": {
            "sequence": {"mean_across_seeds": {"auprc": 0.75, "auroc": 0.74}},
            "hist_ngram_xgb": {"mean_across_seeds": {"auprc": 0.78, "auroc": 0.77}},
            "dcrg_project_balanced": {
                "mean_across_seeds": {"auprc": 0.80, "auroc": 0.79}
            },
        }},
        "dcrg_representation_ablation": {
            "models": {
                "dcrg_full": {"mean_across_seeds": {"auprc": 0.81, "auroc": 0.80}},
                "cfg_capability_only": {
                    "mean_across_seeds": {"auprc": 0.76, "auroc": 0.75}
                },
                "dcrg_untyped_guards": {
                    "mean_across_seeds": {"auprc": 0.78, "auroc": 0.77}
                },
                "dcrg_without_protocol_actors": {
                    "mean_across_seeds": {"auprc": 0.80, "auroc": 0.79}
                },
            },
            "paired_family_bootstrap": [{
                "candidate": "dcrg_full",
                "baseline": "dcrg_untyped_guards",
                "auprc": {"point_delta": 0.03, "ci_low": ci_low, "ci_high": 0.05},
            }],
        },
    }
    decisions = {
        "status": "FROZEN_POSTCUTOFF_DECISION_CONTRACT_EVALUATED_ON_HUMAN_LABELS",
        "n_scored_items": 149,
        "n_binary_scored_items": 139,
        "final_label_counts": counts,
        "agreement": reliability,
        "models": {"dcrg_full": {
            "defer_rate": 0.24,
            "defer_rate_wilson_95ci": [0.18, 0.31],
            "warning_recall": 0.81,
            "warning_recall_wilson_95ci": [0.72, 0.88],
            "warning_observed_fpr": 0.12,
            "warning_observed_fpr_wilson_95ci": [0.07, 0.20],
            "warning_precision": 0.84,
            "warning_precision_wilson_95ci": [0.75, 0.90],
            "unsafe_rate_within_no_model_warning": 0.08,
            "unsafe_rate_within_no_model_warning_wilson_95ci": [0.03, 0.17],
        }},
    }
    return primary, decisions


def test_generated_macros_select_method_branch_and_bind_artifact_hashes():
    primary, decisions = _reports()
    rendered = build_latex_macros(
        primary, decisions, primary_sha256="a" * 64, decisions_sha256="b" * 64
    )
    assert "\\resultsreadytrue" in rendered
    assert "\\renewcommand{\\PaperBranch}{METHOD}" in rendered
    assert "\\renewcommand{\\FinalBinaryN}{139}" in rendered
    assert "\\renewcommand{\\FinalIndeterminateN}{10}" in rendered
    assert "a" * 64 in rendered and "b" * 64 in rendered


def test_generated_macros_select_measurement_branch_when_primary_interval_crosses_zero():
    primary, decisions = _reports(ci_low=-0.01)
    rendered = build_latex_macros(
        primary, decisions, primary_sha256="a", decisions_sha256="b"
    )
    assert "\\renewcommand{\\PaperBranch}{MEASUREMENT}" in rendered


def test_generated_macros_fail_on_cross_artifact_label_disagreement():
    primary, decisions = _reports()
    broken = copy.deepcopy(decisions)
    broken["final_label_counts"]["UNSAFE"] = 61
    with pytest.raises(ValueError, match="disagree on final label counts"):
        build_latex_macros(primary, broken, primary_sha256="a", decisions_sha256="b")
