#!/usr/bin/env bash
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RV2="$(cd "${HERE}/.." && pwd)"
LOG_DIR="${RV2}/logs/paper_final_v3"
STATUS_FILE="${LOG_DIR}/build.status"
DONE_FILE="${LOG_DIR}/build.done"
LOG_FILE="${LOG_DIR}/build.log"

while [[ ! -f "${DONE_FILE}" ]]; do
  sleep 10
done

status="$(tr -d '[:space:]' < "${STATUS_FILE}")"
finished="$(tr -d '[:space:]' < "${DONE_FILE}")"
echo "PAPER_FINAL_V3_BUILD_COMPLETE status=${status} finished=${finished} log=${LOG_FILE}"
exit "${status}"
