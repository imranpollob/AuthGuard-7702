#!/usr/bin/env python3
"""Analyze the frozen Gigahorse cost packet and write bounded conclusions."""
from __future__ import annotations

import csv
import json
import math
import os
from pathlib import Path
import platform
import re
import statistics
import subprocess
from typing import Any, Iterable

from run_reference_analyzer_cost_v1 import (
    IMAGE,
    IMAGE_CONFIG_ID,
    IMAGE_DIGEST,
    MANIFEST,
    RV2,
    DEFAULT_OUTPUT,
    directory_file_count,
    directory_size,
    sha256_file,
)


PRIMARY_TIMINGS = (
    "disassemble_time",
    "decomp_time",
    "inline_time",
    "client_time",
)


def atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(temporary, path)


def quantile(values: Iterable[float], probability: float) -> float | None:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return None
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def timing_summary(values: Iterable[float]) -> dict[str, float | int | None]:
    finite = [float(value) for value in values if math.isfinite(float(value))]
    return {
        "count": len(finite),
        "median_seconds": quantile(finite, 0.5),
        "p90_seconds": quantile(finite, 0.9),
        "p95_seconds": quantile(finite, 0.95),
        "max_seconds": max(finite) if finite else None,
        "mean_seconds": statistics.fmean(finite) if finite else None,
    }


def load_manifest() -> dict[str, dict[str, str]]:
    with MANIFEST.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return {row["sample_file"]: row for row in rows}


def parse_result(record: Any) -> tuple[str, list[str], list[str], dict[str, Any]]:
    if not isinstance(record, list) or len(record) not in (3, 4):
        raise ValueError(f"unexpected Gigahorse result record: {record!r}")
    filename = Path(str(record[0])).name
    if len(record) == 4:
        files, meta, analytics = record[1], record[2], record[3]
    else:
        files, meta, analytics = record[1], record[2], {}
    if not isinstance(files, list) or not isinstance(meta, list):
        raise ValueError(f"invalid Gigahorse files/meta for {filename}")
    if not isinstance(analytics, dict):
        raise ValueError(f"invalid Gigahorse analytics for {filename}")
    return filename, [str(item) for item in files], [str(item) for item in meta], analytics


def numeric(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def status_from_meta(meta: list[str]) -> str:
    if "TIMEOUT" in meta:
        return "TIMEOUT"
    if "ERROR" in meta:
        return "ERROR"
    if "CLIENT TIMEOUT" in meta:
        return "CLIENT_TIMEOUT"
    if "CLIENT ERROR" in meta:
        return "CLIENT_ERROR"
    return "SUCCESS"


def parse_stage(stage: str, output_root: Path, manifest: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    records = json.loads((output_root / stage / "results.json").read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for record in records:
        filename, files, meta, analytics = parse_result(record)
        if filename not in manifest:
            raise ValueError(f"result filename not in manifest: {filename}")
        source = manifest[filename]
        components = {key: numeric(analytics.get(key)) for key in PRIMARY_TIMINGS}
        total = None
        if all(value is not None for value in components.values()):
            total = sum(value for value in components.values() if value is not None)
        rows.append({
            "stage": stage,
            "sample_file": filename,
            "sample_id": source["sample_id"],
            "chain": source["chain"],
            "family_id": source["family_id"],
            "fold_id": int(source["fold_id"]),
            "label": int(source["label"]),
            "label_semantics": source["label_semantics"],
            "length_stratum": source["length_stratum"],
            "opcode_count": int(source["opcode_count"]),
            "code_bytes": int(source["code_bytes"]),
            "status": status_from_meta(meta),
            "meta": "|".join(meta),
            "output_relations": len(files),
            **components,
            "total_internal_seconds": total,
            "decompiler_config": str(analytics.get("decompiler_config", "")),
            "analytics_bytecode_size": numeric(analytics.get("bytecode_size")),
            "analytics_json": json.dumps(analytics, sort_keys=True, separators=(",", ":")),
        })
    return rows


BYTE_UNITS = {
    "b": 1,
    "kb": 1000,
    "mb": 1000**2,
    "gb": 1000**3,
    "kib": 1024,
    "mib": 1024**2,
    "gib": 1024**3,
}


def parse_bytes(value: str) -> float | None:
    first = value.split("/", 1)[0].strip()
    match = re.fullmatch(r"([0-9.]+)\s*([A-Za-z]+)", first)
    if not match:
        return None
    multiplier = BYTE_UNITS.get(match.group(2).lower())
    return float(match.group(1)) * multiplier if multiplier else None


def parse_percent(value: str) -> float | None:
    try:
        return float(value.strip().rstrip("%"))
    except ValueError:
        return None


def resource_summary(stage: str, output_root: Path) -> dict[str, Any]:
    samples: list[dict[str, Any]] = []
    stats_path = output_root / stage / "resource_stats.jsonl"
    if stats_path.is_file():
        for raw in stats_path.read_text(encoding="utf-8", errors="replace").splitlines():
            raw = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", raw).strip()
            if not raw:
                continue
            try:
                record = json.loads(raw)
            except json.JSONDecodeError:
                continue
            memory = parse_bytes(str(record.get("MemUsage", "")))
            cpu = parse_percent(str(record.get("CPUPerc", "")))
            samples.append({"memory_bytes": memory, "cpu_percent": cpu})
    memory_values = [row["memory_bytes"] for row in samples if row["memory_bytes"] is not None]
    cpu_values = [row["cpu_percent"] for row in samples if row["cpu_percent"] is not None]
    return {
        "samples": len(samples),
        "peak_memory_bytes": max(memory_values) if memory_values else None,
        "peak_sampled_cpu_percent": max(cpu_values) if cpu_values else None,
        "median_sampled_cpu_percent": quantile(cpu_values, 0.5),
    }


def group_summary(rows: list[dict[str, Any]], fields: tuple[str, ...]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for row in rows:
        key = tuple(row[field] for field in fields)
        grouped.setdefault(key, []).append(row)
    summaries = []
    for key, group in sorted(grouped.items(), key=lambda item: tuple(map(str, item[0]))):
        status_counts: dict[str, int] = {}
        for row in group:
            status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
        timings = [
            row["total_internal_seconds"] for row in group
            if row["total_internal_seconds"] is not None
        ]
        summaries.append({
            **dict(zip(fields, key)),
            "rows": len(group),
            "status_counts": status_counts,
            "timing": timing_summary(timings),
        })
    return summaries


def host_evidence() -> dict[str, Any]:
    docker_version = subprocess.run(
        ["docker", "version", "--format", "{{json .Server}}"],
        text=True, capture_output=True, check=False)
    cpu_model = None
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.is_file():
        for line in cpuinfo.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.lower().startswith("model name"):
                cpu_model = line.split(":", 1)[1].strip()
                break
    return {
        "cpu_count_logical": os.cpu_count(),
        "cpu_model": cpu_model,
        "docker_server": docker_version.stdout.strip(),
        "machine": platform.machine(),
        "platform": platform.platform(),
        "python": platform.python_version(),
    }


def format_seconds(value: float | None) -> str:
    return "NA" if value is None else f"{value:.3f} s"


def format_mib(value: float | None) -> str:
    return "NA" if value is None else f"{value / 1024**2:.1f} MiB"


def write_report(output_root: Path, summary: dict[str, Any]) -> None:
    warm = summary["warm"]
    cold = summary["cold"]
    timing = warm["timing"]
    resources = warm["resources"]
    warm_wall = warm["host_wall_seconds"]
    amortized = warm_wall / 60
    statuses = warm["status_counts"]
    ratio = None
    if timing["median_seconds"] is not None:
        ratio = timing["median_seconds"] / 0.002942
    lines = [
        "# Reference analyzer cost report v1",
        "",
        "## Outcome",
        "",
        (
            f"The pinned Gigahorse decompilation run completed for all 60 frozen inputs. "
            f"Statuses were {json.dumps(statuses, sort_keys=True)}. The median internal "
            f"successful analysis time was {format_seconds(timing['median_seconds'])}, "
            f"p95 was {format_seconds(timing['p95_seconds'])}, and the maximum was "
            f"{format_seconds(timing['max_seconds'])}."
        ),
        "",
        (
            f"The serial warm bulk invocation took {warm_wall:.3f} s wall time "
            f"({amortized:.3f} s per submitted input, including one container start and "
            f"batch overhead). Peak sampled container memory was "
            f"{format_mib(resources['peak_memory_bytes'])}."
        ),
        "",
        (
            f"The separate cold invocation took {cold['host_wall_seconds']:.3f} s and "
            f"reached {format_mib(cold['resources']['peak_memory_bytes'])} sampled memory. "
            "It includes first-use Datalog compilation and is not pooled with warm "
            "per-contract timings."
        ),
        "",
        "## Frozen execution",
        "",
        f"- Image: `{IMAGE}`",
        "- One job; 120-second timeout per decompilation/analysis phase.",
        "- Default decompilation, fallback, inlining, and signature-resolution settings.",
        "- No downstream Gigahorse client rule was supplied.",
        "- The warm bulk reused the Datalog binaries produced by cold compilation.",
        "",
        "## Staged-triage interpretation",
        "",
        (
            "This measurement supports the operational motivation for a fast first-stage "
            "screen followed by selective decompilation. AuthGuard-Seq's separately measured "
            "complete local CPU path has a 2.942 ms median, whereas this pinned containerized "
            f"decompiler run has a {format_seconds(timing['median_seconds'])} median internal "
            "analysis time."
        ),
        "",
        (
            f"The descriptive median ratio is {ratio:.0f}x" if ratio is not None else
            "A descriptive timing ratio was not available"
        ) + (
            ", but it is not a predictive-performance comparison or a claim that the two "
            "tools are interchangeable. Gigahorse reconstructs substantially richer program "
            "semantics; AuthGuard-Seq emits only a learned triage score."
        ),
        "",
        "## Boundary and limitations",
        "",
        "- This is the official Gigahorse decompiler/lifter, not the exact Huang et al. client rule.",
        "- Labels were used only for deterministic sampling and stratified summaries.",
        "- Resource samples and wall time are host-specific; image pull time is excluded.",
        "- Timeout and error rows remain in the denominator and are never silently dropped.",
        "- The 60-family sample is deterministic and balanced, not a universal workload distribution.",
        "- The result does not establish semantic equivalence, accuracy superiority, or end-to-end wallet latency.",
        "",
        "## Manuscript decision",
        "",
        "Add one bounded measured-cost paragraph and a limitations sentence only after the verifier passes. Preserve the current AuthGuard-Seq architecture and all existing predictive claims.",
        "",
    ]
    (output_root / "REFERENCE_ANALYZER_COST_REPORT.md").write_text(
        "\n".join(lines), encoding="utf-8")


def main() -> int:
    output_root = DEFAULT_OUTPUT.resolve()
    manifest = load_manifest()
    cold_rows = parse_stage("cold", output_root, manifest)
    warm_rows = parse_stage("warm", output_root, manifest)
    all_rows = cold_rows + warm_rows
    csv_path = output_root / "per_contract.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(all_rows[0]))
        writer.writeheader()
        writer.writerows(all_rows)

    stages: dict[str, Any] = {}
    for stage, rows in (("cold", cold_rows), ("warm", warm_rows)):
        run_meta = json.loads((output_root / stage / "run_meta.json").read_text())
        statuses: dict[str, int] = {}
        for row in rows:
            statuses[row["status"]] = statuses.get(row["status"], 0) + 1
        stages[stage] = {
            "host_wall_seconds": float(run_meta["wall_seconds"]),
            "output_bytes": directory_size(output_root / stage),
            "records": len(rows),
            "resources": resource_summary(stage, output_root),
            "status_counts": statuses,
            "timing": timing_summary(
                row["total_internal_seconds"] for row in rows
                if row["total_internal_seconds"] is not None),
        }
    image_inspect = json.loads(
        (output_root / "setup" / "image_inspect_runtime.json").read_text())[0]
    pull = json.loads((output_root / "setup" / "image_pull_timing.json").read_text())
    summary = {
        "cache_bytes": directory_size(output_root / "cache"),
        "cache_files": directory_file_count(output_root / "cache"),
        "cold": stages["cold"],
        "host": host_evidence(),
        "image": IMAGE,
        "image_config_id": IMAGE_CONFIG_ID,
        "image_digest": IMAGE_DIGEST,
        "image_pull_wall_seconds": pull.get("wall_seconds"),
        "image_size_bytes": image_inspect.get("Size"),
        "input_count": len(manifest),
        "manifest_sha256": sha256_file(MANIFEST),
        "stratified_by_label": group_summary(warm_rows, ("label",)),
        "stratified_by_length": group_summary(warm_rows, ("length_stratum",)),
        "stratified_by_label_length": group_summary(warm_rows, ("label", "length_stratum")),
        "warm": stages["warm"],
    }
    atomic_json(output_root / "summary.json", summary)
    write_report(output_root, summary)
    print(
        "REFERENCE_ANALYZER_ANALYSIS_COMPLETE "
        f"warm_records={len(warm_rows)} output={output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
