#!/usr/bin/env python3
"""Generate hash-bound LaTeX macros from label-free frozen artifacts."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = ROOT / "revision_v3/paper_submission/generated/prelabel_results_macros.tex"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load(relative: str) -> tuple[Path, dict]:
    path = ROOT / relative
    return path, json.loads(path.read_text())


def _csv_shape(path: Path) -> tuple[int, list[str]]:
    opener = gzip.open if path.suffix == ".gz" else path.open
    with opener(path, "rt", newline="") as handle:
        reader = csv.reader(handle)
        columns = next(reader)
        rows = sum(1 for _ in reader)
    return rows, columns


def build_prelabel_macros() -> tuple[str, dict]:
    relative_paths = {
        "base_coverage": "revision_v3/results/delegation_context/dcrg_extraction_report.json",
        "intermediate_coverage": "revision_v3/results/delegation_context_coverage_v2/dcrg_extraction_report.json",
        "final_coverage": "revision_v3/results/delegation_context_coverage_v3/dcrg_extraction_report.json",
        "snapshot": "revision_v3/results/postcutoff_snapshot/ethereum_snapshot_report.json",
        "authority": "revision_v3/results/postcutoff_snapshot/postcutoff_authority_dcrg_report.json",
        "dependence": "revision_v3/results/postcutoff_snapshot/postcutoff_dependence_clusters_report.json",
        "holds": "revision_v3/results/postcutoff_snapshot/postcutoff_conservative_family_hold_report.json",
        "training": "revision_v3/results/postcutoff_retraining/postcutoff_training_manifest.json",
        "decisions": "revision_v3/results/postcutoff_retraining/postcutoff_decision_contract_lock.json",
        "external": "revision_v3/results/external_legitimate_controls_final/external_legitimate_control_evaluation_report.json",
    }
    loaded = {name: _load(relative) for name, relative in relative_paths.items()}
    data = {name: value for name, (_, value) in loaded.items()}
    required_statuses = {
        "base_coverage": "COMPLETE",
        "intermediate_coverage": "COMPLETE",
        "final_coverage": "COMPLETE",
        "snapshot": "FROZEN_POSTCUTOFF_CANDIDATE_SNAPSHOT_UNLABELED",
        "authority": "UNLABELED_AUTHORITY_AWARE_DCRG_EXTRACTION",
        "dependence": "SCORE_BLIND_DEPENDENCE_CLUSTERS_COMPLETE",
        "holds": "SCORE_BLIND_CONSERVATIVE_FAMILY_HOLD_AUDIT_MATERIALIZED",
        "training": "FROZEN_POSTCUTOFF_RETRAINING_COMPLETE",
        "decisions": "FROZEN_POSTCUTOFF_DECISION_CONTRACT_BEFORE_HUMAN_LABELS",
        "external": "FROZEN_EXTERNAL_LEGITIMATE_CONTROL_EVALUATION_COMPLETE",
    }
    for name, status in required_statuses.items():
        if data[name].get("status") != status:
            raise ValueError(f"{name} does not have the required frozen status")
    if data["training"].get("postcutoff_labels_accessed") is not False:
        raise ValueError("training manifest does not prove labels remained unopened")
    if int(data["decisions"].get("n_postcutoff_annotations_at_freeze", -1)) != 0:
        raise ValueError("decision contract was not frozen at zero annotations")
    if data["external"].get("postcutoff_human_annotations_accessed") is not False:
        raise ValueError("external evaluation accessed post-cutoff annotations")

    prediction_path = ROOT / data["training"]["predictions_path"]
    prediction_rows, prediction_columns = _csv_shape(prediction_path)
    forbidden = [
        column for column in prediction_columns
        if any(token in column.lower() for token in ("label", "judgment", "outcome"))
    ]
    if forbidden:
        raise ValueError(f"prediction artifact contains label-like columns: {forbidden}")

    base = data["base_coverage"]
    intermediate = data["intermediate_coverage"]
    final = data["final_coverage"]
    snapshot = data["snapshot"]
    authority = data["authority"]
    dependence = data["dependence"]
    holds = data["holds"]
    training = data["training"]
    decisions = data["decisions"]
    external = data["external"]
    macros: dict[str, int] = {
        "CanonicalRows": int(final["n_primary_samples"]),
        "CanonicalRuntimes": int(final["n_unique_runtimes"]),
        "BaseCompleteRows": int(base["coverage_primary_samples"]["COMPLETE"]),
        "BaseCompleteRuntimes": int(base["coverage_unique_runtimes"]["COMPLETE"]),
        "IntermediateCompleteRows": int(intermediate["coverage_primary_samples"]["COMPLETE"]),
        "IntermediateCompleteRuntimes": int(intermediate["coverage_unique_runtimes"]["COMPLETE"]),
        "FinalCompleteRows": int(final["coverage_primary_samples"]["COMPLETE"]),
        "FinalCompleteRuntimes": int(final["coverage_unique_runtimes"]["COMPLETE"]),
        "SnapshotBlocks": int(snapshot["checkpoint"]["n_blocks_scanned"]),
        "SnapshotTypeFourTxs": int(snapshot["checkpoint"]["n_type4_txs"]),
        "SnapshotAuthorizations": int(snapshot["checkpoint"]["n_authorization_entries"]),
        "SnapshotNonzeroDelegates": int(snapshot["n_unique_nonzero_delegates"]),
        "SnapshotUsablePairs": int(snapshot["n_with_historical_runtime"]),
        "SnapshotUnseenFamilies": int(snapshot["n_candidate_unseen_exact_runtime_families"]),
        "AuthoritySenderDifferences": int(snapshot["n_authorities_distinct_from_transaction_sender"]),
        "DependenceClusters": int(dependence["n_dependence_clusters"]),
        "DependenceMultiClusters": int(dependence["n_multi_item_clusters"]),
        "DependenceMultiItems": int(dependence["n_items_in_multi_item_clusters"]),
        "HeldCanonicalFamilies": int(holds["n_distinct_canonical_families_held"]),
        "FrozenTrainRows": int(training["n_training_rows"]),
        "FrozenValidationRows": int(training["n_validation_rows"]),
        "FrozenCheckpoints": len(training["checkpoints"]),
        "FrozenPredictionRows": prediction_rows,
        "FrozenScoredItems": int(decisions["n_scored_items"]),
        "ExternalWarn": int(external["principal_decision_counts"]["WARN"]),
        "ExternalNoWarning": int(external["principal_decision_counts"]["NO_MODEL_WARNING"]),
        "ExternalDefer": int(external["principal_decision_counts"]["DEFER"]),
    }
    model_macro = {
        "sequence": "Sequence",
        "hist_ngram_xgb": "Histogram",
        "cfg_capability_only": "Capability",
        "dcrg_untyped_guards": "Untyped",
        "dcrg_without_protocol_actors": "ActorRemoved",
        "dcrg_full": "FullDCRG",
        "dcrg_project_balanced": "ProjectBalanced",
    }
    for model, prefix in model_macro.items():
        counts = decisions["decision_counts_by_model"][model]
        macros[f"{prefix}PreWarn"] = int(counts["WARN"])
        macros[f"{prefix}PreNoWarning"] = int(counts["NO_MODEL_WARNING"])
        macros[f"{prefix}PreDefer"] = int(counts["DEFER"])

    input_hashes = {relative_paths[name]: sha256_file(path) for name, (path, _) in loaded.items()}
    input_hashes[str(prediction_path.relative_to(ROOT))] = sha256_file(prediction_path)
    lines = ["% AUTO-GENERATED FROM LABEL-FREE FROZEN ARTIFACTS. DO NOT EDIT."]
    lines.extend(f"% {path} sha256: {digest}" for path, digest in sorted(input_hashes.items()))
    lines.extend(f"\\newcommand{{\\{name}}}{{{value:,}}}" for name, value in macros.items())
    report = {
        "status": "PRELABEL_SUBMISSION_ASSETS_GENERATED",
        "n_macros": len(macros),
        "input_hashes": input_hashes,
        "postcutoff_annotations_accessed": False,
    }
    return "\n".join(lines) + "\n", report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=(
        ROOT / "revision_v3/paper_submission/generated/prelabel_results_macros_report.json"
    ))
    args = parser.parse_args()
    rendered, report = build_prelabel_macros()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered)
    report["output"] = str(args.output.relative_to(ROOT))
    report["output_sha256"] = sha256_file(args.output)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
