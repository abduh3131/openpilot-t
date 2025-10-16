#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR=$(cd "$(dirname "$0")" && pwd)
source "$ROOT_DIR/install/setup.bash"
ros2 launch scootpilot_bringup bringup_launch.py use_sim:=false gui:=true
