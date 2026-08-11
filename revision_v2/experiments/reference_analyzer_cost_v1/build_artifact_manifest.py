#!/usr/bin/env python3
"""Hash the compact reproducibility packet after scientific verification."""
from __future__ import annotations

import json
import os
from pathlib import Path

from run_reference_analyzer_cost_v1 import HERE, REPO, RV2, DEFAULT_OUTPUT, sha256_file


OUTPUT = DEFAULT_OUTPUT.resolve()
PROTOCOL = RV2 / "protocols" / "reference_analyzer_cost_v1.md"
LOG_ROOT = RV2 / "logs" / "reference_analyzer_cost_v1"


def include_result(path: Path) -> bool:
    relative = path.relative_to(OUTPUT)
    if relative.name == "ARTIFACT_MANIFEST.json":
        return False
    if any(part in {"cache", "smoke_cache", "failed_attempts", "work"} for part in relative.parts):
        return False
    return path.is_file()


def include_log(path: Path) -> bool:
    return path.is_file() and path.suffix != ".pid"


def main() -> int:
    verification = OUTPUT / "VERIFICATION.json"
    if not verification.is_file():
        raise RuntimeError("verification packet is missing")
    verified = json.loads(verification.read_text(encoding="utf-8"))
    if verified.get("status") != "PASS":
        raise RuntimeError("verification packet did not pass")

    files = {PROTOCOL}
    files.update(path for path in HERE.rglob("*") if path.is_file() and "__pycache__" not in path.parts)
    files.update(path for path in OUTPUT.rglob("*") if include_result(path))
    files.update(path for path in LOG_ROOT.rglob("*") if include_log(path))
    records = []
    for path in sorted(files):
        records.append({
            "bytes": path.stat().st_size,
            "path": str(path.relative_to(REPO)),
            "sha256": sha256_file(path),
        })
    payload = {
        "excluded_heavy_or_transient_paths": [
            "revision_v2/results/reference_analyzer_cost_v1/cache",
            "revision_v2/results/reference_analyzer_cost_v1/smoke_cache",
            "revision_v2/results/reference_analyzer_cost_v1/*/work",
            "revision_v2/results/reference_analyzer_cost_v1/failed_attempts",
            "*.pid",
        ],
        "file_count": len(records),
        "files": records,
        "status": "PASS",
        "total_bytes": sum(record["bytes"] for record in records),
    }
    destination = OUTPUT / "ARTIFACT_MANIFEST.json"
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, destination)
    print(
        f"REFERENCE_ANALYZER_MANIFEST_COMPLETE files={len(records)} "
        f"bytes={payload['total_bytes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
