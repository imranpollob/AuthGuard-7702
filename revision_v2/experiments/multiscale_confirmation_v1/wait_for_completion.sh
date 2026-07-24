#!/usr/bin/env bash
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RV2="$(cd "${HERE}/../.." && pwd)"
LOG_DIR="${RV2}/logs/multiscale_confirmation_v1"
STATUS_FILE="${LOG_DIR}/full.status"
DONE_FILE="${LOG_DIR}/full.done"
LOG_FILE="${LOG_DIR}/full.log"

while [[ ! -f "${DONE_FILE}" ]]; do
  sleep 10
done
status="$(tr -d '[:space:]' < "${STATUS_FILE}")"
finished="$(tr -d '[:space:]' < "${DONE_FILE}")"
echo "MULTISCALE_CONFIRMATION_V1_COMPLETE status=${status} finished=${finished} log=${LOG_FILE}"
[[ "${status}" == "0" ]]
