#!/bin/bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
ENV_DIR="${PROJECT_ROOT}/pwm-env"

if [[ ! -d "${ENV_DIR}" ]]; then
  echo "[pwm-bridge] Creating virtual environment at ${ENV_DIR}" >&2
  python3 -m venv "${ENV_DIR}"
fi

source "${ENV_DIR}/bin/activate"

python -m pip install --upgrade pip
python -m pip install -e "${PROJECT_ROOT}"
python -m pip install opencv-python

echo "[pwm-bridge] Environment ready. Activate it with:"
echo "  source ${ENV_DIR}/bin/activate"

