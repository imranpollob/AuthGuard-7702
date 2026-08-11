#!/usr/bin/env bash
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RV2="$(cd "${HERE}/../.." && pwd)"
LOG_DIR="${RV2}/logs/reference_analyzer_cost_v1"
OUT_DIR="${RV2}/results/reference_analyzer_cost_v1/setup"
IMAGE="ghcr.io/nevillegrech/gigahorse-toolchain@sha256:f676ca8aaf88acd47be27ed1967acddc9c99acdd041b34e79472cfb028910743"
mkdir -p "${LOG_DIR}" "${OUT_DIR}"

PID_FILE="${LOG_DIR}/image_pull.pid"
STATUS_FILE="${LOG_DIR}/image_pull.status"
DONE_FILE="${LOG_DIR}/image_pull.done"
LOG_FILE="${LOG_DIR}/image_pull.log"
if [[ -f "${PID_FILE}" ]] &&
   kill -0 "$(tr -d '[:space:]' < "${PID_FILE}")" 2>/dev/null; then
  echo "reference analyzer image pull is already running"
  exit 2
fi

: > "${LOG_FILE}"
rm -f "${STATUS_FILE}" "${DONE_FILE}"
nohup setsid bash -c '
  image="$1"
  out_dir="$2"
  status_file="$3"
  done_file="$4"
  started_ns="$(date +%s%N)"
  docker pull "${image}"
  rc=$?
  finished_ns="$(date +%s%N)"
  if [[ "${rc}" == "0" ]]; then
    docker image inspect "${image}" > "${out_dir}/image_inspect.json"
    rc=$?
  fi
  python3 - "${out_dir}/image_pull_timing.json" "${started_ns}" "${finished_ns}" "${rc}" <<'PY'
import json
import sys
path, started, finished, status = sys.argv[1:]
with open(path + ".tmp", "w", encoding="utf-8") as handle:
    json.dump({
        "started_unix_ns": int(started),
        "finished_unix_ns": int(finished),
        "wall_seconds": (int(finished) - int(started)) / 1e9,
        "status": int(status),
    }, handle, indent=2, sort_keys=True)
    handle.write("\n")
import os
os.replace(path + ".tmp", path)
PY
  printf "%s\n" "${rc}" > "${status_file}"
  date -u +"%Y-%m-%dT%H:%M:%SZ" > "${done_file}"
  exit "${rc}"
' _ "${IMAGE}" "${OUT_DIR}" "${STATUS_FILE}" "${DONE_FILE}" \
  >> "${LOG_FILE}" 2>&1 < /dev/null &
worker_pid=$!
printf '%s\n' "${worker_pid}" > "${PID_FILE}"
echo "launched image pull: pid=${worker_pid} log=${LOG_FILE}"
