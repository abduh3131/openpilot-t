#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

function log_step() {
  echo -e "\n\033[1m==> $1\033[0m"
}

function ensure_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Required command '$1' is not available. Install it and re-run the setup." >&2
    exit 1
  fi
}

log_step "Preparing Ubuntu environment"
if [[ $(id -u) -ne 0 ]]; then
  if command -v sudo >/dev/null 2>&1; then
    export SUDO="sudo"
  else
    echo "This script installs system packages and must be run as root or with sudo available." >&2
    exit 1
  fi
else
  export SUDO=""
fi

log_step "Installing system dependencies"
"${ROOT_DIR}/tools/install_ubuntu_dependencies.sh"

log_step "Ensuring Git LFS assets are available"
ensure_command git
if ! git lfs env >/dev/null 2>&1; then
  git lfs install
fi
git lfs pull

log_step "Initializing git submodules"
git submodule update --init --recursive

log_step "Installing Python tooling and packages"
"${ROOT_DIR}/tools/install_python_dependencies.sh"

log_step "Setup complete"
echo "openpilot can now be launched with ./launch_openpilot.sh or via the desktop GUI at tools/gui/openpilot_desktop.py"
