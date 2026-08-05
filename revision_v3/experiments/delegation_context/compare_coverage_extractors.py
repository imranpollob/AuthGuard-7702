#!/usr/bin/env python3
"""Compare versioned DCRG extraction artifacts without reading labels or model scores."""
from __future__ import annotations

import argparse
from collections import Counter
import json
import os


def load(path: str) -> dict[str, dict]:
    with open(path) as handle:
        return {row["bytecode_sha256"]: row for row in map(json.loads, handle)}


def summarize(records: dict[str, dict]) -> dict:
    coverage = Counter()
    findings = Counter()
    gap_flags = Counter()
    widened_functions = 0
    for record in records.values():
        graph = record["dcrg"]
        coverage[graph["coverage"]] += 1
        findings.update(graph["findings"])
        widened_functions += int(
            (record.get("cfg_summary") or {}).get("n_functions_using_state_widening") or 0
        )
        for node in graph["nodes"]:
            if node.get("kind") != "COVERAGE_GAP" or ":coverage-gap" not in node.get("node_id", ""):
                continue
            for key, value in node.get("attributes", {}).items():
                gap_flags[key] += int(bool(value))
    return {
        "coverage_unique_runtimes": dict(sorted(coverage.items())),
        "finding_contract_counts": dict(sorted(findings.items())),
        "function_gap_flag_counts": dict(sorted(gap_flags.items())),
        "n_functions_using_state_widening": widened_functions,
    }


def compare(before: dict[str, dict], after: dict[str, dict]) -> dict:
    if set(before) != set(after):
        raise ValueError("extractors do not cover the same unique runtime hashes")
    transitions = Counter()
    feature_changes = Counter()
    findings_added = Counter()
    findings_removed = Counter()
    for bytecode_hash, old in before.items():
        old_graph = old["dcrg"]
        new_graph = after[bytecode_hash]["dcrg"]
        transitions[f"{old_graph['coverage']}->{new_graph['coverage']}"] += 1
        for name, value in old_graph["features"].items():
            if value != new_graph["features"][name]:
                feature_changes[name] += 1
        findings_added.update(set(new_graph["findings"]) - set(old_graph["findings"]))
        findings_removed.update(set(old_graph["findings"]) - set(new_graph["findings"]))
    return {
        "coverage_transitions": dict(sorted(transitions.items())),
        "feature_changed_runtime_counts": dict(sorted(feature_changes.items())),
        "findings_added_runtime_counts": dict(sorted(findings_added.items())),
        "findings_removed_runtime_counts": dict(sorted(findings_removed.items())),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--metadata-only", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    artifacts = {
        "baseline": load(args.baseline),
        "metadata_only": load(args.metadata_only),
        "candidate": load(args.candidate),
    }
    report = {
        "status": "LABEL_FREE_EXTRACTOR_VALIDITY_COMPARISON",
        "summaries": {name: summarize(records) for name, records in artifacts.items()},
        "baseline_to_metadata_only": compare(
            artifacts["baseline"], artifacts["metadata_only"]
        ),
        "baseline_to_candidate": compare(artifacts["baseline"], artifacts["candidate"]),
        "interpretation_boundary": (
            "Coverage transitions and newly reached capabilities are extractor-validity "
            "results. They do not establish improved predictive performance or security labels."
        ),
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
