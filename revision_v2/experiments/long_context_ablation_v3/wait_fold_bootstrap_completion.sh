#!/usr/bin/env bash
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RV2="$(cd "${HERE}/../.." && pwd)"
LOG_DIR="${RV2}/logs/long_context_ablation_v3"
while [[ ! -f "${LOG_DIR}/fold_bootstrap.done" ]]; do
  sleep 10
done
status="$(tr -d '[:space:]' < "${LOG_DIR}/fold_bootstrap.status")"
finished="$(tr -d '[:space:]' < "${LOG_DIR}/fold_bootstrap.done")"
echo "V3_FOLD_BOOTSTRAP_COMPLETE status=${status} finished=${finished} log=${LOG_DIR}/fold_bootstrap.log"
exit "${status}"
