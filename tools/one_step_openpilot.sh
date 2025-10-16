#!/usr/bin/env bash
# Bootstrap, update, and launch openpilot in a single command.
set -euo pipefail

REPO_URL=${OPENPILOT_REPO_URL:-"https://github.com/commaai/openpilot"}
TARGET_DIR=${OPENPILOT_DIR:-"$HOME/openpilot"}
BRANCH=${OPENPILOT_BRANCH:-"master"}
SESSION_NAME=${OPENPILOT_TMUX_SESSION:-"openpilot"}

log() {
  printf '\n[%s] %s\n' "$(date '+%H:%M:%S')" "$*"
}

ensure_directory() {
  local dir="$1"
  if [[ ! -d "$dir" ]]; then
    log "Creating workspace directory $dir"
    mkdir -p "$dir"
  fi
}

clone_or_update_repo() {
  if [[ ! -d "$TARGET_DIR/.git" ]]; then
    log "Cloning $REPO_URL into $TARGET_DIR"
    git clone --branch "$BRANCH" --single-branch --recursive "$REPO_URL" "$TARGET_DIR"
  else
    log "Updating existing repository in $TARGET_DIR"
    git -C "$TARGET_DIR" fetch --tags --prune
    git -C "$TARGET_DIR" checkout "$BRANCH"
    git -C "$TARGET_DIR" pull --ff-only
    git -C "$TARGET_DIR" submodule update --init --recursive
  fi
}

fetch_large_files() {
  if command -v git >/dev/null 2>&1 && command -v git-lfs >/dev/null 2>&1; then
    log "Ensuring Git LFS objects are available"
    git -C "$TARGET_DIR" lfs install --local
    git -C "$TARGET_DIR" lfs pull
  else
    log "Skipping Git LFS fetch (git-lfs not installed)"
  fi
}

install_dependencies() {
  if [[ -x "$TARGET_DIR/tools/ubuntu_setup.sh" ]]; then
    log "Installing Ubuntu and Python dependencies"
    "$TARGET_DIR/tools/ubuntu_setup.sh"
  else
    log "Dependency script tools/ubuntu_setup.sh not found or not executable"
  fi
}

launch_openpilot() {
  if ! command -v tmux >/dev/null 2>&1; then
    log "tmux not found; launching openpilot in the foreground"
    log "Tip: open another terminal and run '$TARGET_DIR/tools/actuators/monitor_actuators.py'"
    exec "$TARGET_DIR/launch_openpilot.sh"
  fi

  log "Starting openpilot inside tmux session '$SESSION_NAME'"
  tmux new-session -d -s "$SESSION_NAME" "cd '$TARGET_DIR' && ./launch_openpilot.sh"
  tmux new-window -t "$SESSION_NAME" "cd '$TARGET_DIR' && tools/actuators/monitor_actuators.py"
  log "Attach to the tmux session with: tmux attach -t $SESSION_NAME"
  log "The first window runs openpilot; switch to the second window (Ctrl+b then n) to watch actuator values."
  exec tmux attach -t "$SESSION_NAME"
}

main() {
  ensure_directory "$TARGET_DIR"
  clone_or_update_repo
  fetch_large_files()
  install_dependencies
  launch_openpilot
}

main "$@"
