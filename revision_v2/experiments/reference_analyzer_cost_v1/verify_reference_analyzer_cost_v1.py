#!/usr/bin/env python3
"""Fail closed on an incomplete or internally inconsistent cost packet."""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

from run_reference_analyzer_cost_v1 import (
    COLD_SAMPLE,
    DEFAULT_OUTPUT,
    EXPECTED_MANIFEST_SHA256,
    IMAGE,
    IMAGE_CONFIG_ID,
    IMAGE_DIGEST,
    MANIFEST,
    sha256_file,
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    root = DEFAULT_OUTPUT.resolve()
    require(sha256_file(MANIFEST) == EXPECTED_MANIFEST_SHA256, "manifest digest")
    with MANIFEST.open(newline="", encoding="utf-8") as handle:
        manifest = list(csv.DictReader(handle))
    expected = {row["sample_file"] for row in manifest}
    require(len(manifest) == len(expected) == 60, "manifest cardinality")
    require(len({row["family_id"] for row in manifest}) == 60, "family uniqueness")
    cell_counts: dict[tuple[str, str, str], int] = {}
    for row in manifest:
        key = (row["label"], row["length_stratum"], row["fold_id"])
        cell_counts[key] = cell_counts.get(key, 0) + 1
    require(len(cell_counts) == 30 and set(cell_counts.values()) == {2}, "balanced cells")

    inspected = json.loads((root / "setup" / "image_inspect_runtime.json").read_text())
    require(len(inspected) == 1, "image inspect cardinality")
    require(inspected[0].get("Id") == IMAGE_CONFIG_ID, "image configuration ID")
    require(IMAGE in inspected[0].get("RepoDigests", []), "repository digest")
    interface = json.loads((root / "setup" / "interface_check.json").read_text())
    require(interface.get("status") == "PASS", "interface check")
    pull = json.loads((root / "setup" / "image_pull_timing.json").read_text())
    require(pull.get("status") == 0 and float(pull.get("wall_seconds", -1)) >= 0,
            "successful image pull evidence")

    hashes_path = root / "setup" / "input_hashes.csv"
    with hashes_path.open(newline="", encoding="utf-8") as handle:
        hashes = list(csv.DictReader(handle))
    require(len(hashes) == 60, "input hashes cardinality")
    require({row["sample_file"] for row in hashes} == expected, "input hash filenames")
    require(all(row["benchmark_runtime_exact_match"] == "1" for row in hashes), "input benchmark match")

    for stage, count, names in (
        ("smoke", 1, None),
        ("cold", 1, {COLD_SAMPLE}),
        ("warm", 60, expected),
    ):
        stage_root = root / stage
        for filename in (
            "complete.json", "container_inspect.json", "results.json", "run_meta.json",
            "stdout.log", "stderr.log", "resource_stats.jsonl", "resource_stats.stderr.log",
        ):
            require((stage_root / filename).is_file(), f"{stage}/{filename}")
        complete = json.loads((stage_root / "complete.json").read_text())
        require(complete.get("status") == "PASS", f"{stage} completion status")
        results_path = stage_root / "results.json"
        require(complete.get("results_sha256") == sha256_file(results_path), f"{stage} results hash")
        require(
            complete.get("run_meta_sha256") == sha256_file(stage_root / "run_meta.json"),
            f"{stage} run metadata hash")
        results = json.loads(results_path.read_text())
        require(isinstance(results, list) and len(results) == count, f"{stage} result count")
        result_names = {Path(str(record[0])).name for record in results}
        require(len(result_names) == count, f"{stage} unique filenames")
        if names is not None:
            require(result_names == names, f"{stage} exact filenames")
        meta = json.loads((stage_root / "run_meta.json").read_text())
        require(meta.get("docker_exit_code") == 0, f"{stage} docker exit")
        require(meta.get("image") == IMAGE, f"{stage} image")
        require(meta.get("jobs") == 1, f"{stage} jobs")
        require(float(meta.get("wall_seconds", -1)) >= 0, f"{stage} wall time")

    with (root / "per_contract.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    require(len(rows) == 61, "per-contract row count")
    warm = [row for row in rows if row["stage"] == "warm"]
    require(len(warm) == 60, "warm joined row count")
    require({row["sample_file"] for row in warm} == expected, "warm joined filenames")
    allowed = {"SUCCESS", "TIMEOUT", "ERROR", "CLIENT_TIMEOUT", "CLIENT_ERROR"}
    require({row["status"] for row in warm} <= allowed, "status vocabulary")
    for row in rows:
        if row["status"] in {"SUCCESS", "CLIENT_TIMEOUT", "CLIENT_ERROR"}:
            for field in (
                "disassemble_time", "decomp_time", "inline_time", "client_time",
                "total_internal_seconds",
            ):
                value = float(row[field])
                require(math.isfinite(value) and value >= 0, f"finite timing {field}")

    summary = json.loads((root / "summary.json").read_text())
    require(summary.get("image") == IMAGE, "summary image")
    require(summary.get("image_config_id") == IMAGE_CONFIG_ID, "summary image config")
    require(summary.get("input_count") == 60, "summary input count")
    require(summary["warm"].get("records") == 60, "summary warm records")
    require(sum(summary["warm"]["status_counts"].values()) == 60, "summary statuses")
    for stage in ("cold", "warm"):
        resources = summary[stage]["resources"]
        require(resources.get("samples", 0) > 0, f"{stage} resource samples")
        require(resources.get("peak_memory_bytes") is not None, f"{stage} peak memory")
        require(resources.get("peak_sampled_cpu_percent") is not None, f"{stage} peak CPU")
    cold_meta = json.loads((root / "cold" / "run_meta.json").read_text())
    warm_meta = json.loads((root / "warm" / "run_meta.json").read_text())
    require(cold_meta.get("cache_executables_after", 0) > 0, "cold compiled executables")
    require(cold_meta.get("reuse_datalog_bin") is False, "cold binary compilation")
    require(cold_meta.get("timeout_seconds") == 120, "cold timeout")
    require(warm_meta.get("reuse_datalog_bin") is True, "warm binary reuse")
    require(warm_meta.get("timeout_seconds") == 120, "warm timeout")
    require(warm_meta.get("input_argument") == "/inputs", "warm complete input directory")
    require(summary["warm"]["timing"].get("count", 0) > 0, "warm internal timings")
    require((root / "REFERENCE_ANALYZER_COST_REPORT.md").is_file(), "report")

    verification = {
        "image": IMAGE,
        "manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "per_contract_sha256": sha256_file(root / "per_contract.csv"),
        "report_sha256": sha256_file(root / "REFERENCE_ANALYZER_COST_REPORT.md"),
        "status": "PASS",
        "summary_sha256": sha256_file(root / "summary.json"),
        "warm_records": 60,
    }
    temporary = root / "VERIFICATION.json.tmp"
    temporary.write_text(json.dumps(verification, indent=2, sort_keys=True) + "\n")
    temporary.replace(root / "VERIFICATION.json")
    print("REFERENCE_ANALYZER_VERIFICATION_PASS warm_records=60")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
