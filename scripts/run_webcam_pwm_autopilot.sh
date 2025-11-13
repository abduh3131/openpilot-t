#!/bin/bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
ENV_DIR="${PROJECT_ROOT}/pwm-env"

if [[ ! -d "${ENV_DIR}" ]]; then
  echo "Virtual environment not found. Run ./scripts/setup_pwm_bridge.sh first." >&2
  exit 1
fi

source "${ENV_DIR}/bin/activate"

OUTPUT_DIR="${PWM_OUTPUT_DIR:-${HOME}/openpilot_pwm}"
OUTPUT_FILE="${OUTPUT_DIR}/pwm_capture.csv"

mkdir -p "${OUTPUT_DIR}"

cleanup() {
  for pid in ${PIDS[@]:-}; do
    kill "${pid}" >/dev/null 2>&1 || true
  done
}

trap cleanup EXIT INT TERM

USE_WEBCAM=1 ./tools/sim/launch_openpilot.sh &
PIDS=($!)

sleep 10

USE_WEBCAM=1 SIMULATOR=1 python -m openpilot.tools.sim.run_bridge &
PIDS+=($!)

sleep 5

python -m openpilot.selfdrive.pwm_bridge.bridge "${OUTPUT_FILE}"

