#!/usr/bin/env bash
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RV2="$(cd "${HERE}/../.." && pwd)"
LOG_DIR="${RV2}/logs/reference_analyzer_cost_v1"
STAGE="${1:-full}"
PID_FILE="${LOG_DIR}/${STAGE}.pid"
STATUS_FILE="${LOG_DIR}/${STAGE}.status"
DONE_FILE="${LOG_DIR}/${STAGE}.done"
LOG_FILE="${LOG_DIR}/${STAGE}.log"

if [[ ! -f "${PID_FILE}" ]]; then
  echo "missing worker PID file: ${PID_FILE}" >&2
  exit 2
fi
worker_pid="$(tr -d '[:space:]' < "${PID_FILE}")"
while kill -0 "${worker_pid}" 2>/dev/null; do
  sleep 5
done

for _ in $(seq 1 12); do
  [[ -f "${STATUS_FILE}" && -f "${DONE_FILE}" ]] && break
  sleep 1
done
if [[ ! -f "${STATUS_FILE}" || ! -f "${DONE_FILE}" ]]; then
  echo "REFERENCE_ANALYZER_${STAGE^^}_INCOMPLETE worker=${worker_pid} log=${LOG_FILE}" >&2
  exit 3
fi
status="$(tr -d '[:space:]' < "${STATUS_FILE}")"
finished="$(tr -d '[:space:]' < "${DONE_FILE}")"
echo "REFERENCE_ANALYZER_${STAGE^^}_COMPLETE status=${status} finished=${finished} log=${LOG_FILE}"
exit "${status}"
