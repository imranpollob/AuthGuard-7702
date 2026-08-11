#!/usr/bin/env bash
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RV2="$(cd "${HERE}/../.." && pwd)"
LOG_DIR="${RV2}/logs/reference_analyzer_cost_v1"
while [[ ! -f "${LOG_DIR}/image_pull.done" ]]; do
  sleep 10
done
status="$(tr -d '[:space:]' < "${LOG_DIR}/image_pull.status")"
finished="$(tr -d '[:space:]' < "${LOG_DIR}/image_pull.done")"
echo "REFERENCE_ANALYZER_IMAGE_PULL_COMPLETE status=${status} finished=${finished} log=${LOG_DIR}/image_pull.log"
exit "${status}"
