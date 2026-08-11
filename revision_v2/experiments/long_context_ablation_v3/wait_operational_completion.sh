#!/usr/bin/env bash
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RV2="$(cd "${HERE}/../.." && pwd)"
LOG_DIR="${RV2}/logs/long_context_ablation_v3"
while [[ ! -f "${LOG_DIR}/operational.done" ]]; do
  sleep 10
done
status="$(tr -d '[:space:]' < "${LOG_DIR}/operational.status")"
finished="$(tr -d '[:space:]' < "${LOG_DIR}/operational.done")"
echo "OPERATIONAL_CONTROLS_COMPLETE status=${status} finished=${finished} log=${LOG_DIR}/operational.log"
exit "${status}"
