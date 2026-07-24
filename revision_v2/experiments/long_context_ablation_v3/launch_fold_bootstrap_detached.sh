#!/usr/bin/env bash
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RV2="$(cd "${HERE}/../.." && pwd)"
LOG_DIR="${RV2}/logs/long_context_ablation_v3"
STATUS_FILE="${LOG_DIR}/fold_bootstrap.status"
DONE_FILE="${LOG_DIR}/fold_bootstrap.done"
PID_FILE="${LOG_DIR}/fold_bootstrap.pid"
LOG_FILE="${LOG_DIR}/fold_bootstrap.log"
if [[ -f "${PID_FILE}" ]] && kill -0 "$(tr -d '[:space:]' < "${PID_FILE}")" 2>/dev/null; then
  echo "fold bootstrap is already running"
  exit 2
fi
: > "${LOG_FILE}"
rm -f "${STATUS_FILE}" "${DONE_FILE}"
nohup setsid bash -c '
  script="$1"
  status_file="$2"
  done_file="$3"
  python3 -u "${script}"
  rc=$?
  printf "%s\n" "${rc}" > "${status_file}"
  date -u +"%Y-%m-%dT%H:%M:%SZ" > "${done_file}"
  exit "${rc}"
' _ "${HERE}/analyze_fold_clustered_contrasts.py" \
  "${STATUS_FILE}" "${DONE_FILE}" >> "${LOG_FILE}" 2>&1 < /dev/null &
worker_pid=$!
printf "%s\n" "${worker_pid}" > "${PID_FILE}"
echo "launched fold bootstrap: pid=${worker_pid} log=${LOG_FILE}"

