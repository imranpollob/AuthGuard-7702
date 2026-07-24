#!/usr/bin/env bash
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RV2="$(cd "${HERE}/.." && pwd)"
LOG_DIR="${RV2}/logs/paper_final_v3"
BUILD_DIR="${HERE}/build_v3"
PID_FILE="${LOG_DIR}/build.pid"
STATUS_FILE="${LOG_DIR}/build.status"
DONE_FILE="${LOG_DIR}/build.done"
LOG_FILE="${LOG_DIR}/build.log"

mkdir -p "${LOG_DIR}" "${BUILD_DIR}"
if [[ -f "${PID_FILE}" ]] &&
   kill -0 "$(tr -d '[:space:]' < "${PID_FILE}")" 2>/dev/null; then
  echo "paper v3 build is already running"
  exit 2
fi

: > "${LOG_FILE}"
rm -f "${STATUS_FILE}" "${DONE_FILE}"
nohup setsid bash -c '
  source_dir="$1"
  build_dir="$2"
  status_file="$3"
  done_file="$4"

  image="authguard-paper-tex:2022"
  if ! docker image inspect "${image}" >/dev/null 2>&1; then
    docker build --tag "${image}" --file "${source_dir}/Dockerfile.paper" \
      "${source_dir}"
    image_rc=$?
    if [[ "${image_rc}" != "0" ]]; then
      printf "%s\n" "${image_rc}" > "${status_file}"
      date -u +"%Y-%m-%dT%H:%M:%SZ" > "${done_file}"
      exit "${image_rc}"
    fi
  fi

  docker run --rm \
    --volume "${source_dir}:/src:ro" \
    --volume "${build_dir}:/build" \
    --workdir /build \
    "${image}" bash -lc "
      set -e
      cp /src/main_final.tex /src/hierarchical_encoder_v3.tex \
        /src/eip_7702_authorization_risk_flowchart.png \
        /src/figure-1-bak.png /build/
      pdflatex -interaction=nonstopmode -halt-on-error \
        -jobname=AuthGuard_7702_v3 main_final.tex
      pdflatex -interaction=nonstopmode -halt-on-error \
        -jobname=AuthGuard_7702_v3 main_final.tex
    "
  rc=$?
  if [[ "${rc}" == "0" ]]; then
    cp "${build_dir}/AuthGuard_7702_v3.pdf" \
      "${source_dir}/AuthGuard_7702_v3.pdf"
  fi
  printf "%s\n" "${rc}" > "${status_file}"
  date -u +"%Y-%m-%dT%H:%M:%SZ" > "${done_file}"
  exit "${rc}"
' _ "${HERE}" "${BUILD_DIR}" "${STATUS_FILE}" "${DONE_FILE}" \
  >> "${LOG_FILE}" 2>&1 < /dev/null &
worker_pid=$!
printf "%s\n" "${worker_pid}" > "${PID_FILE}"
echo "launched paper v3 build: pid=${worker_pid} log=${LOG_FILE}"
