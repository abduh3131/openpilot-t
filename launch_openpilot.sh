#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CAMERA_SOURCE="${OPENPILOT_CAMERA:-0}"
CSV_TARGET="${OPENPILOT_ACTUATOR_CSV:-${ROOT_DIR}/actuators.csv}"
FPS="${OPENPILOT_CAMERA_FPS:-20}"

exec "${ROOT_DIR}/tools/camera/camera_openpilot.py" \
  --camera "${CAMERA_SOURCE}" \
  --csv "${CSV_TARGET}" \
  --fps "${FPS}"
