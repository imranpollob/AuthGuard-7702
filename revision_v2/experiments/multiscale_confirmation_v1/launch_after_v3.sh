#!/usr/bin/env bash
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RV2="$(cd "${HERE}/../.." && pwd)"
UPSTREAM_LOG="${RV2}/logs/long_context_ablation_v3"
LOG_DIR="${RV2}/logs/multiscale_confirmation_v1"
mkdir -p "${LOG_DIR}"

PID_FILE="${LOG_DIR}/full.pid"
STATUS_FILE="${LOG_DIR}/full.status"
DONE_FILE="${LOG_DIR}/full.done"
LOG_FILE="${LOG_DIR}/full.log"

if [[ -f "${PID_FILE}" ]] && kill -0 "$(tr -d '[:space:]' < "${PID_FILE}")" 2>/dev/null; then
  echo "multiscale confirmation is already queued/running"
  exit 2
fi

: > "${LOG_FILE}"
rm -f "${STATUS_FILE}" "${DONE_FILE}"
nohup setsid bash -c '
  script="$1"
  upstream_status="$2"
  upstream_done="$3"
  status_file="$4"
  done_file="$5"
  while [[ ! -f "${upstream_done}" ]]; do
    sleep 10
  done
  upstream_rc="$(tr -d "[:space:]" < "${upstream_status}")"
  if [[ "${upstream_rc}" != "0" ]]; then
    printf "upstream_failed:%s\n" "${upstream_rc}" > "${status_file}"
    date -u +"%Y-%m-%dT%H:%M:%SZ" > "${done_file}"
    exit 1
  fi
  base="$(dirname "${script}")"
  python3 -u "${base}/../long_context_ablation_v3/verify_outputs.py"
  verify_rc=$?
  if [[ "${verify_rc}" != "0" ]]; then
    printf "upstream_verification_failed:%s\n" "${verify_rc}" > "${status_file}"
    date -u +"%Y-%m-%dT%H:%M:%SZ" > "${done_file}"
    exit 1
  fi
  python3 -u "${script}" --resume
  rc=$?
  if [[ "${rc}" == "0" ]]; then
    python3 -u "${base}/analyze_confirmation.py"
    rc=$?
  fi
  if [[ "${rc}" == "0" ]]; then
    python3 -u "${base}/verify_outputs.py"
    rc=$?
  fi
  printf "%s\n" "${rc}" > "${status_file}"
  date -u +"%Y-%m-%dT%H:%M:%SZ" > "${done_file}"
  exit "${rc}"
' _ "${HERE}/run_multiscale_confirmation_v1.py" \
  "${UPSTREAM_LOG}/full.status" "${UPSTREAM_LOG}/full.done" \
  "${STATUS_FILE}" "${DONE_FILE}" >> "${LOG_FILE}" 2>&1 < /dev/null &
worker_pid=$!
printf "%s\n" "${worker_pid}" > "${PID_FILE}"
echo "queued multiscale confirmation: pid=${worker_pid} log=${LOG_FILE}"
