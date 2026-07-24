#!/usr/bin/env bash
set -u

MODE="${1:-full}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RV2="$(cd "${HERE}/../.." && pwd)"
LOG_DIR="${RV2}/logs/long_context_ablation_v3"
STATUS_FILE="${LOG_DIR}/${MODE}.status"
DONE_FILE="${LOG_DIR}/${MODE}.done"
LOG_FILE="${LOG_DIR}/${MODE}.log"

while [[ ! -f "${DONE_FILE}" ]]; do
  sleep 10
done

status="$(tr -d '[:space:]' < "${STATUS_FILE}")"
finished="$(tr -d '[:space:]' < "${DONE_FILE}")"
echo "LONG_CONTEXT_ABLATION_V3_${MODE^^}_COMPLETE status=${status} finished=${finished} log=${LOG_FILE}"
exit "${status}"
