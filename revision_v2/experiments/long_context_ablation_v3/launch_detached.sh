#!/usr/bin/env bash
set -u

MODE="${1:-full}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RV2="$(cd "${HERE}/../.." && pwd)"
LOG_DIR="${RV2}/logs/long_context_ablation_v3"
mkdir -p "${LOG_DIR}"

if [[ "${MODE}" == "smoke" ]]; then
  NAME="smoke"
else
  NAME="full"
fi

PID_FILE="${LOG_DIR}/${NAME}.pid"
STATUS_FILE="${LOG_DIR}/${NAME}.status"
DONE_FILE="${LOG_DIR}/${NAME}.done"
LOG_FILE="${LOG_DIR}/${NAME}.log"

if [[ -f "${PID_FILE}" ]] && kill -0 "$(tr -d '[:space:]' < "${PID_FILE}")" 2>/dev/null; then
  echo "${NAME} is already running with PID $(tr -d '[:space:]' < "${PID_FILE}")"
  exit 2
fi

: > "${LOG_FILE}"
rm -f "${STATUS_FILE}" "${DONE_FILE}"
nohup setsid bash -c '
  script="$1"
  mode="$2"
  status_file="$3"
  done_file="$4"
  if [[ "${mode}" == "smoke" ]]; then
    python3 -u "${script}" --smoke
  else
    python3 -u "${script}" --resume
  fi
  rc=$?
  printf "%s\n" "${rc}" > "${status_file}"
  date -u +"%Y-%m-%dT%H:%M:%SZ" > "${done_file}"
  exit "${rc}"
' _ "${HERE}/run_long_context_ablation_v3.py" "${MODE}" \
  "${STATUS_FILE}" "${DONE_FILE}" >> "${LOG_FILE}" 2>&1 < /dev/null &
worker_pid=$!
printf "%s\n" "${worker_pid}" > "${PID_FILE}"
echo "launched ${NAME}: pid=${worker_pid} log=${LOG_FILE}"
