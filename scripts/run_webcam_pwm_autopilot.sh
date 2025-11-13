#!/bin/bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
ENV_DIR="${PROJECT_ROOT}/pwm-env"

if [[ ! -d "${ENV_DIR}" ]]; then
  echo "Virtual environment not found. Run ./scripts/setup_pwm_bridge.sh first." >&2
  exit 1
fi

echo "[pwm-bridge] Activating virtual environment at ${ENV_DIR}" >&2
source "${ENV_DIR}/bin/activate"

OUTPUT_DIR="${PWM_OUTPUT_DIR:-${HOME}/openpilot_pwm}"
OUTPUT_FILE="${OUTPUT_DIR}/pwm_capture.csv"

mkdir -p "${OUTPUT_DIR}"
echo "[pwm-bridge] Writing PWM CSV to ${OUTPUT_FILE}" >&2

cleanup() {
  for pid in ${PIDS[@]:-}; do
    kill "${pid}" >/dev/null 2>&1 || true
  done
}

trap cleanup EXIT INT TERM

echo "[pwm-bridge] Starting openpilot in webcam simulator mode" >&2
USE_WEBCAM=1 ./tools/sim/launch_openpilot.sh &
PIDS=($!)

sleep 10

echo "[pwm-bridge] Spinning up simulator bridge" >&2
USE_WEBCAM=1 SIMULATOR=1 python -m openpilot.tools.sim.run_bridge &
PIDS+=($!)

sleep 5

echo "[pwm-bridge] Mirroring CAN traffic to PWM CSV" >&2
python -m openpilot.selfdrive.pwm_bridge.bridge "${OUTPUT_FILE}"

