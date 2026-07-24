#!/usr/bin/env bash
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RV2="$(cd "${HERE}/../.." && pwd)"
LOG_DIR="${RV2}/logs/long_context_ablation_v3"
STATUS_FILE="${LOG_DIR}/operational.status"
DONE_FILE="${LOG_DIR}/operational.done"
PID_FILE="${LOG_DIR}/operational.pid"
LOG_FILE="${LOG_DIR}/operational.log"

if [[ -f "${PID_FILE}" ]] && kill -0 "$(tr -d '[:space:]' < "${PID_FILE}")" 2>/dev/null; then
  echo "operational controls are already running"
  exit 2
fi
: > "${LOG_FILE}"
rm -f "${STATUS_FILE}" "${DONE_FILE}"
nohup setsid bash -c '
  base="$1"
  status_file="$2"
  done_file="$3"
  python3 -u "${base}/evaluate_operational_controls.py"
  rc=$?
  if [[ "${rc}" == "0" ]]; then
    python3 -u "${base}/verify_operational_controls.py"
    rc=$?
  fi
  printf "%s\n" "${rc}" > "${status_file}"
  date -u +"%Y-%m-%dT%H:%M:%SZ" > "${done_file}"
  exit "${rc}"
' _ "${HERE}" "${STATUS_FILE}" "${DONE_FILE}" \
  >> "${LOG_FILE}" 2>&1 < /dev/null &
worker_pid=$!
printf "%s\n" "${worker_pid}" > "${PID_FILE}"
echo "launched operational controls: pid=${worker_pid} log=${LOG_FILE}"

