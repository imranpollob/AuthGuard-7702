#!/usr/bin/env python3
"""Run the frozen, staged Gigahorse cost experiment.

The expensive stages are intended to be invoked by the detached launcher.  This
module owns provenance validation, container lifecycle evidence, and resumable
stage markers; it does not analyze or summarize the scientific results.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any, Iterable


HERE = Path(__file__).resolve().parent
RV2 = HERE.parent.parent
REPO = RV2.parent
MANIFEST = HERE / "sample" / "sample_manifest.csv"
INPUT_DIR = HERE / "sample" / "inputs"
BENCHMARK = RV2 / "data" / "authguardbench_7702_v2.csv.gz"
DEFAULT_OUTPUT = RV2 / "results" / "reference_analyzer_cost_v1"
EXPECTED_MANIFEST_SHA256 = (
    "26dbccb92a8de05e1b0e57440acbfd2e6f7a36b202eed71aa9b11d994bd1a794"
)
IMAGE_REPOSITORY = "ghcr.io/nevillegrech/gigahorse-toolchain"
IMAGE_DIGEST = "sha256:f676ca8aaf88acd47be27ed1967acddc9c99acdd041b34e79472cfb028910743"
IMAGE_CONFIG_ID = "sha256:9c1e6a36fa9fa80e756f67897c4b7003f455bb1e9a7a86233d619555aa20848f"
IMAGE = f"{IMAGE_REPOSITORY}@{IMAGE_DIGEST}"
COLD_SAMPLE = "sample_021.hex"
SMOKE_SAMPLE = "sample_048.hex"
TIMING_COMPONENTS = (
    "disassemble_time",
    "decomp_time",
    "inline_time",
    "client_time",
)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(temporary, path)


def run_checked(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, text=True, **kwargs)


def normalize_hex(value: str) -> str:
    text = value.strip().lower()
    if text.startswith("0x"):
        text = text[2:]
    if not text or len(text) % 2:
        raise ValueError("bytecode is empty or has odd length")
    try:
        bytes.fromhex(text)
    except ValueError as exc:
        raise ValueError("bytecode is not hexadecimal") from exc
    return text


def load_manifest() -> list[dict[str, str]]:
    if sha256_file(MANIFEST) != EXPECTED_MANIFEST_SHA256:
        raise RuntimeError("frozen sample manifest SHA-256 mismatch")
    with MANIFEST.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    names = [row["sample_file"] for row in rows]
    families = [row["family_id"] for row in rows]
    if len(rows) != 60 or len(set(names)) != 60 or len(set(families)) != 60:
        raise RuntimeError("frozen sample must contain 60 unique files and families")
    if COLD_SAMPLE not in names or SMOKE_SAMPLE not in names:
        raise RuntimeError("frozen cold or smoke sample missing")
    return rows


def selected_benchmark_rows(sample_ids: set[str]) -> dict[str, dict[str, str]]:
    found: dict[str, dict[str, str]] = {}
    with gzip.open(BENCHMARK, "rt", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            sample_id = row.get("sample_id", "")
            if sample_id in sample_ids:
                if sample_id in found:
                    raise RuntimeError(f"duplicate benchmark sample_id: {sample_id}")
                found[sample_id] = row
    missing = sorted(sample_ids - set(found))
    if missing:
        raise RuntimeError(f"sample IDs missing from benchmark: {missing[:3]}")
    return found


def validate_and_record_inputs(output_root: Path) -> list[dict[str, str]]:
    rows = load_manifest()
    benchmark = selected_benchmark_rows({row["sample_id"] for row in rows})
    evidence: list[dict[str, str]] = []
    for row in rows:
        input_path = INPUT_DIR / row["sample_file"]
        if not input_path.is_file():
            raise RuntimeError(f"missing frozen input: {input_path}")
        file_bytes = input_path.read_bytes()
        input_hex = normalize_hex(file_bytes.decode("ascii"))
        benchmark_hex = normalize_hex(benchmark[row["sample_id"]]["runtime_bytecode"])
        if input_hex != benchmark_hex:
            raise RuntimeError(f"input/benchmark bytecode mismatch: {row['sample_file']}")
        raw = bytes.fromhex(input_hex)
        if int(row["code_bytes"]) != len(raw):
            raise RuntimeError(f"manifest byte length mismatch: {row['sample_file']}")
        evidence.append({
            "sample_file": row["sample_file"],
            "sample_id": row["sample_id"],
            "file_sha256": sha256_bytes(file_bytes),
            "decoded_bytecode_sha256": sha256_bytes(raw),
            "decoded_bytes": str(len(raw)),
            "benchmark_runtime_exact_match": "1",
        })

    setup = output_root / "setup"
    setup.mkdir(parents=True, exist_ok=True)
    hashes_path = setup / "input_hashes.csv"
    temporary = hashes_path.with_suffix(".csv.tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(evidence[0]))
        writer.writeheader()
        writer.writerows(evidence)
    os.replace(temporary, hashes_path)
    atomic_json(setup / "frozen_configuration.json", {
        "benchmark": str(BENCHMARK.relative_to(REPO)),
        "cold_sample": COLD_SAMPLE,
        "image": IMAGE,
        "image_config_id": IMAGE_CONFIG_ID,
        "image_digest": IMAGE_DIGEST,
        "input_count": len(rows),
        "input_hashes_sha256": sha256_file(hashes_path),
        "jobs": 1,
        "manifest": str(MANIFEST.relative_to(REPO)),
        "manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "smoke_sample": SMOKE_SAMPLE,
        "timeout_seconds": {"smoke": 30, "cold": 120, "warm": 120},
    })
    return rows


def verify_local_image(output_root: Path) -> dict[str, Any]:
    completed = run_checked(
        ["docker", "image", "inspect", IMAGE], capture_output=True)
    inspected = json.loads(completed.stdout)
    if len(inspected) != 1:
        raise RuntimeError("pinned image inspect did not return exactly one object")
    image = inspected[0]
    if image.get("Id") != IMAGE_CONFIG_ID:
        raise RuntimeError(f"local image ID mismatch: {image.get('Id')}")
    if IMAGE not in image.get("RepoDigests", []):
        raise RuntimeError("pinned repository digest missing from local image")
    atomic_json(output_root / "setup" / "image_inspect_runtime.json", inspected)
    return image


def capture_help(output_root: Path) -> None:
    completed = run_checked(
        ["docker", "run", "--rm", IMAGE, "--help"], capture_output=True)
    help_text = completed.stdout + completed.stderr
    required = (
        "--results_file", "--working_dir", "--cache_dir", "--jobs",
        "--timeout_secs", "--restart", "--reuse_datalog_bin",
    )
    missing = [flag for flag in required if flag not in help_text]
    if missing:
        raise RuntimeError(f"pinned image interface missing flags: {missing}")
    help_path = output_root / "setup" / "gigahorse_help.txt"
    help_path.write_text(help_text, encoding="utf-8")
    atomic_json(output_root / "setup" / "interface_check.json", {
        "help_sha256": sha256_file(help_path),
        "required_flags": list(required),
        "status": "PASS",
    })


def directory_size(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def directory_file_count(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for item in path.rglob("*") if item.is_file())


def directory_executable_count(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(
        1 for item in path.rglob("*")
        if item.is_file() and item.stat().st_mode & 0o111
    )


def ensure_new_stage(stage_dir: Path) -> bool:
    marker = stage_dir / "complete.json"
    if marker.is_file():
        results_path = stage_dir / "results.json"
        if not results_path.is_file():
            raise RuntimeError(f"stage marker exists without results: {stage_dir}")
        print(f"REFERENCE_ANALYZER_STAGE_RESUMED stage={stage_dir.name}")
        return False
    if stage_dir.exists() and any(stage_dir.iterdir()):
        raise RuntimeError(
            f"refusing to overwrite incomplete stage directory: {stage_dir}")
    stage_dir.mkdir(parents=True, exist_ok=True)
    return True


def write_stream(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", errors="replace")


def docker_stage(
    *,
    stage: str,
    output_root: Path,
    cache_dir: Path,
    input_argument: str,
    timeout_seconds: int,
    reuse_datalog_bin: bool,
) -> None:
    stage_dir = output_root / stage
    if not ensure_new_stage(stage_dir):
        return

    if stage == "cold" and directory_file_count(cache_dir) != 0:
        raise RuntimeError("cold stage requires an initially empty persistent cache")
    if stage == "warm" and directory_executable_count(cache_dir) == 0:
        raise RuntimeError("warm stage requires executable Datalog binaries from cold")
    cache_dir.mkdir(parents=True, exist_ok=True)

    name = f"authguard-gh-{stage}-{os.getpid()}-{time.time_ns()}"
    command = [
        "docker", "create", "--name", name,
        "--user", f"{os.getuid()}:{os.getgid()}",
        "--mount", f"type=bind,src={INPUT_DIR},dst=/inputs,readonly",
        "--mount", f"type=bind,src={cache_dir},dst=/cache",
        "--mount", f"type=bind,src={stage_dir},dst=/run_output",
        IMAGE,
        "-j", "1",
        "-T", str(timeout_seconds),
        "-r", "/run_output/results.json",
        "-w", "/run_output/work",
        "--cache_dir", "/cache",
        "--restart",
    ]
    if reuse_datalog_bin:
        command.append("--reuse_datalog_bin")
    command.append(input_argument)

    started_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    started_ns = time.time_ns()
    wall_start = time.perf_counter()
    container_id = ""
    exit_code: int | None = None
    stats_process: subprocess.Popen[str] | None = None
    stats_handle = None
    stats_error_handle = None
    inspect_after: list[dict[str, Any]] = []
    failure: str | None = None
    try:
        created = run_checked(command, capture_output=True)
        container_id = created.stdout.strip()
        if not container_id:
            raise RuntimeError("docker create returned an empty container ID")
        run_checked(["docker", "start", name], capture_output=True)
        stats_handle = (stage_dir / "resource_stats.jsonl").open("w", encoding="utf-8")
        stats_error_handle = (stage_dir / "resource_stats.stderr.log").open(
            "w", encoding="utf-8")
        stats_process = subprocess.Popen(
            ["docker", "stats", "--format", "{{json .}}", name],
            stdout=stats_handle,
            stderr=stats_error_handle,
            text=True,
        )
        waited = subprocess.run(
            ["docker", "wait", name], capture_output=True, text=True, check=False)
        write_stream(stage_dir / "docker_wait.stdout.log", waited.stdout)
        write_stream(stage_dir / "docker_wait.stderr.log", waited.stderr)
        logs = subprocess.run(
            ["docker", "logs", name], capture_output=True, text=True, check=False)
        write_stream(stage_dir / "stdout.log", logs.stdout)
        write_stream(stage_dir / "stderr.log", logs.stderr)
        inspected = run_checked(["docker", "inspect", name], capture_output=True)
        inspect_after = json.loads(inspected.stdout)
        atomic_json(stage_dir / "container_inspect.json", inspect_after)
        if len(inspect_after) != 1:
            raise RuntimeError("container inspect did not return exactly one object")
        exit_code = int(inspect_after[0]["State"]["ExitCode"])
        wait_values = [line.strip() for line in waited.stdout.splitlines() if line.strip()]
        wait_reported_exit = int(wait_values[-1]) if wait_values else None
        if wait_reported_exit is not None and wait_reported_exit != exit_code:
            raise RuntimeError(
                f"docker wait/inspect exit mismatch: {wait_reported_exit} != {exit_code}")
    except Exception as exc:  # retain lifecycle evidence before propagating
        failure = f"{type(exc).__name__}: {exc}"
    finally:
        if stats_process is not None:
            stats_process.terminate()
            try:
                stats_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                stats_process.kill()
                stats_process.wait(timeout=5)
        if stats_handle is not None:
            stats_handle.close()
        if stats_error_handle is not None:
            stats_error_handle.close()
        if container_id:
            subprocess.run(
                ["docker", "rm", name], capture_output=True, text=True, check=False)

    finished_ns = time.time_ns()
    metadata = {
        "cache_bytes_after": directory_size(cache_dir),
        "cache_files_after": directory_file_count(cache_dir),
        "cache_executables_after": directory_executable_count(cache_dir),
        "container_id": container_id,
        "container_name": name,
        "docker_command": command,
        "docker_exit_code": exit_code,
        "docker_wait_cli_exit_code": (
            waited.returncode if "waited" in locals() else None),
        "failure": failure,
        "finished_unix_ns": finished_ns,
        "image": IMAGE,
        "input_argument": input_argument,
        "jobs": 1,
        "output_bytes_after": directory_size(stage_dir),
        "reuse_datalog_bin": reuse_datalog_bin,
        "stage": stage,
        "started_unix_ns": started_ns,
        "started_utc": started_utc,
        "timeout_seconds": timeout_seconds,
        "wall_seconds": time.perf_counter() - wall_start,
    }
    atomic_json(stage_dir / "run_meta.json", metadata)
    if failure is not None:
        raise RuntimeError(f"{stage} container lifecycle failed: {failure}")
    if exit_code != 0:
        raise RuntimeError(f"{stage} container exited with status {exit_code}")
    results_path = stage_dir / "results.json"
    if not results_path.is_file():
        raise RuntimeError(f"{stage} did not produce results.json")
    try:
        results = json.loads(results_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RuntimeError(f"{stage} results.json is invalid") from exc
    expected_count = 60 if stage == "warm" else 1
    if not isinstance(results, list) or len(results) != expected_count:
        raise RuntimeError(
            f"{stage} returned {len(results) if isinstance(results, list) else 'non-list'} "
            f"records, expected {expected_count}")
    atomic_json(stage_dir / "complete.json", {
        "results_count": len(results),
        "results_sha256": sha256_file(results_path),
        "run_meta_sha256": sha256_file(stage_dir / "run_meta.json"),
        "status": "PASS",
    })
    print(
        f"REFERENCE_ANALYZER_STAGE_COMPLETE stage={stage} records={len(results)} "
        f"wall_seconds={metadata['wall_seconds']:.3f}")


def run_stage(stage: str, output_root: Path) -> None:
    validate_and_record_inputs(output_root)
    verify_local_image(output_root)
    capture_help(output_root)
    if stage == "smoke":
        docker_stage(
            stage="smoke",
            output_root=output_root,
            cache_dir=output_root / "smoke_cache",
            input_argument=f"/inputs/{SMOKE_SAMPLE}",
            timeout_seconds=30,
            reuse_datalog_bin=False,
        )
    elif stage == "cold":
        docker_stage(
            stage="cold",
            output_root=output_root,
            cache_dir=output_root / "cache",
            input_argument=f"/inputs/{COLD_SAMPLE}",
            timeout_seconds=120,
            reuse_datalog_bin=False,
        )
    elif stage == "warm":
        docker_stage(
            stage="warm",
            output_root=output_root,
            cache_dir=output_root / "cache",
            input_argument="/inputs",
            timeout_seconds=120,
            reuse_datalog_bin=True,
        )
    else:
        raise ValueError(stage)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--stage", choices=("smoke", "cold", "warm", "all"), default="all")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output_root = args.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    stages: Iterable[str] = ("smoke", "cold", "warm") if args.stage == "all" else (args.stage,)
    for stage in stages:
        run_stage(stage, output_root)
    print(f"REFERENCE_ANALYZER_RUN_COMPLETE stages={','.join(stages)} output={output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
