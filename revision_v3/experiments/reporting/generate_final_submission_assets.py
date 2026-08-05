#!/usr/bin/env python3
"""Generate final LaTeX macros from the two locked post-cutoff evaluations.

This script is intentionally unusable before complete human evaluation. It does not compute
statistics; it validates agreement between the primary and operating reports and formats their
already-computed results without manual transcription.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


PRIMARY_STATUS = "HUMAN_FINAL_EVALUATION"
DECISION_STATUS = "FROZEN_POSTCUTOFF_DECISION_CONTRACT_EVALUATED_ON_HUMAN_LABELS"
ROOT = Path(__file__).resolve().parents[3]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require(mapping: dict, *keys: str):
    value = mapping
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            raise ValueError(f"missing required final-result field: {'.'.join(keys)}")
        value = value[key]
    return value


def _comparison(primary: dict, baseline: str) -> dict:
    comparisons = _require(
        primary, "dcrg_representation_ablation", "paired_family_bootstrap"
    )
    matches = [
        row for row in comparisons
        if row.get("candidate") == "dcrg_full" and row.get("baseline") == baseline
    ]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one full-DCRG comparison against {baseline}")
    return _require(matches[0], "auprc")


def _fmt(value, digits: int = 3) -> str:
    if value is None:
        return "undefined"
    return f"{float(value):.{digits}f}"


def _interval(values) -> tuple[str, str]:
    if not isinstance(values, list) or len(values) != 2:
        raise ValueError("expected a two-endpoint final-result interval")
    return _fmt(values[0]), _fmt(values[1])


def build_latex_macros(
    primary: dict,
    decisions: dict,
    *,
    primary_sha256: str,
    decisions_sha256: str,
) -> str:
    if primary.get("status") != PRIMARY_STATUS or primary.get("sample_set") != "postcutoff":
        raise ValueError("primary artifact is not a completed post-cutoff human evaluation")
    if decisions.get("status") != DECISION_STATUS:
        raise ValueError("operating artifact is not the frozen post-cutoff decision evaluation")
    if int(primary.get("n_manifest_items", -1)) != 150:
        raise ValueError("primary report does not cover the frozen 150-item manifest")
    if int(primary.get("n_finalized_items", -1)) != 150:
        raise ValueError("primary report is not a complete 150-item human release")
    if int(primary.get("n_scored_finalized_items", -1)) != int(decisions.get("n_scored_items", -2)):
        raise ValueError("primary and operating reports use different scored populations")
    if int(primary.get("n_binary_items", -1)) != int(decisions.get("n_binary_scored_items", -2)):
        raise ValueError("primary and operating reports use different binary populations")
    primary_counts = _require(primary, "final_label_counts")
    decision_counts = _require(decisions, "final_label_counts")
    if primary_counts != decision_counts:
        raise ValueError("primary and operating reports disagree on final label counts")
    reliability = _require(primary, "inter_rater_reliability")
    decision_agreement = _require(decisions, "agreement")
    for key in ("raw_agreement_rate", "cohens_kappa"):
        if reliability.get(key) != decision_agreement.get(key):
            raise ValueError(f"primary and operating reports disagree on {key}")

    primary_test = _comparison(primary, "dcrg_untyped_guards")
    delta = float(_require(primary_test, "point_delta"))
    lower = float(_require(primary_test, "ci_low"))
    upper = float(_require(primary_test, "ci_high"))
    branch = "METHOD" if lower > 0.0 else "MEASUREMENT"
    full_metrics = _require(
        primary, "dcrg_representation_ablation", "models", "dcrg_full", "mean_across_seeds"
    )
    capability_metrics = _require(
        primary, "dcrg_representation_ablation", "models", "cfg_capability_only",
        "mean_across_seeds"
    )
    untyped_metrics = _require(
        primary, "dcrg_representation_ablation", "models", "dcrg_untyped_guards",
        "mean_across_seeds"
    )
    actor_removed_metrics = _require(
        primary, "dcrg_representation_ablation", "models", "dcrg_without_protocol_actors",
        "mean_across_seeds"
    )
    sequence_metrics = _require(primary, "dcrg_evaluation", "models", "sequence", "mean_across_seeds")
    histogram_metrics = _require(
        primary, "dcrg_evaluation", "models", "hist_ngram_xgb", "mean_across_seeds"
    )
    project_balanced_metrics = _require(
        primary, "dcrg_evaluation", "models", "dcrg_project_balanced", "mean_across_seeds"
    )
    full_decisions = _require(decisions, "models", "dcrg_full")
    warn_recall_ci = _interval(_require(full_decisions, "warning_recall_wilson_95ci"))
    warn_fpr_ci = _interval(_require(full_decisions, "warning_observed_fpr_wilson_95ci"))
    warn_precision_ci = _interval(_require(full_decisions, "warning_precision_wilson_95ci"))
    defer_ci = _interval(_require(full_decisions, "defer_rate_wilson_95ci"))
    no_warning_unsafe_ci = _interval(_require(
        full_decisions, "unsafe_rate_within_no_model_warning_wilson_95ci"
    ))
    unsafe = int(primary_counts.get("UNSAFE", 0))
    bounded_negative = int(primary_counts.get("NO_CONCRETE_UNSAFE_BEHAVIOR_FOUND", 0))
    excluded_binary = int(primary_counts.get("INDETERMINATE", 0)) + int(
        primary_counts.get("NOT_BYTECODE_SCREENABLE", 0)
    )
    macros = {
        "FinalBinaryN": str(int(primary["n_binary_items"])),
        "FinalUnsafeN": str(unsafe),
        "FinalNegativeN": str(bounded_negative),
        "FinalIndeterminateN": str(excluded_binary),
        "FinalAgreement": _fmt(reliability.get("raw_agreement_rate")),
        "FinalKappa": _fmt(reliability.get("cohens_kappa")),
        "PrimaryDelta": _fmt(delta),
        "PrimaryLower": _fmt(lower),
        "PrimaryUpper": _fmt(upper),
        "FullAUPRC": _fmt(_require(full_metrics, "auprc")),
        "HistAUPRC": _fmt(_require(histogram_metrics, "auprc")),
        "SequenceAUPRC": _fmt(_require(sequence_metrics, "auprc")),
        "CapabilityAUPRC": _fmt(_require(capability_metrics, "auprc")),
        "UntypedAUPRC": _fmt(_require(untyped_metrics, "auprc")),
        "ActorRemovedAUPRC": _fmt(_require(actor_removed_metrics, "auprc")),
        "ProjectBalancedAUPRC": _fmt(_require(project_balanced_metrics, "auprc")),
        "FullAUROC": _fmt(_require(full_metrics, "auroc")),
        "HistAUROC": _fmt(_require(histogram_metrics, "auroc")),
        "SequenceAUROC": _fmt(_require(sequence_metrics, "auroc")),
        "CapabilityAUROC": _fmt(_require(capability_metrics, "auroc")),
        "UntypedAUROC": _fmt(_require(untyped_metrics, "auroc")),
        "ActorRemovedAUROC": _fmt(_require(actor_removed_metrics, "auroc")),
        "ProjectBalancedAUROC": _fmt(_require(project_balanced_metrics, "auroc")),
        "FinalDeferRate": _fmt(_require(full_decisions, "defer_rate")),
        "FullWarnRecall": _fmt(_require(full_decisions, "warning_recall")),
        "FullWarnRecallLower": warn_recall_ci[0],
        "FullWarnRecallUpper": warn_recall_ci[1],
        "FullWarnFPR": _fmt(_require(full_decisions, "warning_observed_fpr")),
        "FullWarnFPRLower": warn_fpr_ci[0],
        "FullWarnFPRUpper": warn_fpr_ci[1],
        "FullWarnPrecision": _fmt(_require(full_decisions, "warning_precision")),
        "FullWarnPrecisionLower": warn_precision_ci[0],
        "FullWarnPrecisionUpper": warn_precision_ci[1],
        "FullDeferLower": defer_ci[0],
        "FullDeferUpper": defer_ci[1],
        "FullNoWarnUnsafeRate": _fmt(
            _require(full_decisions, "unsafe_rate_within_no_model_warning")
        ),
        "FullNoWarnUnsafeLower": no_warning_unsafe_ci[0],
        "FullNoWarnUnsafeUpper": no_warning_unsafe_ci[1],
        "PaperBranch": branch,
    }
    lines = [
        "% AUTO-GENERATED. DO NOT EDIT.",
        f"% primary evaluation sha256: {primary_sha256}",
        f"% operating evaluation sha256: {decisions_sha256}",
        "\\resultsreadytrue",
    ]
    lines.extend(f"\\renewcommand{{\\{name}}}{{{value}}}" for name, value in macros.items())
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=(
        ROOT / "revision_v3/paper_submission/generated/final_results_macros.tex"
    ))
    args = parser.parse_args()
    primary = json.loads(args.primary.read_text())
    decisions = json.loads(args.decisions.read_text())
    rendered = build_latex_macros(
        primary,
        decisions,
        primary_sha256=sha256_file(args.primary),
        decisions_sha256=sha256_file(args.decisions),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered)
    print(json.dumps({
        "status": "FINAL_SUBMISSION_MACROS_GENERATED",
        "output": str(args.output),
        "output_sha256": sha256_file(args.output),
    }, indent=2))


if __name__ == "__main__":
    main()
