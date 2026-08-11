#!/usr/bin/env bash
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RV2="$(cd "${HERE}/../.." && pwd)"
LOG_DIR="${RV2}/logs/reference_analyzer_cost_v1"
OUT_DIR="${RV2}/results/reference_analyzer_cost_v1"
STAGE="${1:-full}"
if [[ "${STAGE}" != "smoke" && "${STAGE}" != "full" ]]; then
  echo "usage: $0 [smoke|full]" >&2
  exit 2
fi
mkdir -p "${LOG_DIR}" "${OUT_DIR}"

PID_FILE="${LOG_DIR}/${STAGE}.pid"
WAITER_PID_FILE="${LOG_DIR}/${STAGE}_waiter.pid"
STATUS_FILE="${LOG_DIR}/${STAGE}.status"
DONE_FILE="${LOG_DIR}/${STAGE}.done"
LOG_FILE="${LOG_DIR}/${STAGE}.log"
WAITER_LOG="${LOG_DIR}/${STAGE}_waiter.log"
if [[ -f "${PID_FILE}" ]] &&
   kill -0 "$(tr -d '[:space:]' < "${PID_FILE}")" 2>/dev/null; then
  echo "reference analyzer ${STAGE} job is already running"
  exit 2
fi

: > "${LOG_FILE}"
: > "${WAITER_LOG}"
rm -f "${STATUS_FILE}" "${DONE_FILE}"
nohup setsid bash -c '
  here="$1"
  stage="$2"
  status_file="$3"
  done_file="$4"
  if [[ "${stage}" == "smoke" ]]; then
    python3 "${here}/run_reference_analyzer_cost_v1.py" --stage smoke
    rc=$?
  else
    python3 "${here}/run_reference_analyzer_cost_v1.py" --stage all
    rc=$?
    if [[ "${rc}" == "0" ]]; then
      python3 "${here}/analyze_reference_analyzer_cost_v1.py"
      rc=$?
    fi
    if [[ "${rc}" == "0" ]]; then
      python3 "${here}/verify_reference_analyzer_cost_v1.py"
      rc=$?
    fi
    if [[ "${rc}" == "0" ]]; then
      python3 "${here}/build_artifact_manifest.py"
      rc=$?
    fi
  fi
  printf "%s\n" "${rc}" > "${status_file}"
  date -u +"%Y-%m-%dT%H:%M:%SZ" > "${done_file}"
  exit "${rc}"
' _ "${HERE}" "${STAGE}" "${STATUS_FILE}" "${DONE_FILE}" \
  >> "${LOG_FILE}" 2>&1 < /dev/null &
worker_pid=$!
printf '%s\n' "${worker_pid}" > "${PID_FILE}"

nohup setsid "${HERE}/wait_cost_study_completion.sh" "${STAGE}" \
  >> "${WAITER_LOG}" 2>&1 < /dev/null &
waiter_pid=$!
printf '%s\n' "${waiter_pid}" > "${WAITER_PID_FILE}"
echo "launched reference analyzer ${STAGE}: worker_pid=${worker_pid} waiter_pid=${waiter_pid} log=${LOG_FILE}"
