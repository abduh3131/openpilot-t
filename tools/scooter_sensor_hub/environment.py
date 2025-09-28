from __future__ import annotations

import os
import platform
from pathlib import Path

from .types import HostEnvironment

__all__ = ["detect_host_environment"]


def _default_launch_prefix() -> tuple[str, ...]:
  bash_path = Path("/bin/bash")
  if bash_path.exists():
    return (str(bash_path),)
  return ()


def detect_host_environment() -> HostEnvironment:
  """Infer how the start button should launch openpilot.

  The routine distinguishes between native Ubuntu hosts, Windows Subsystem for Linux
  (WSL), Visual Studio Code terminals, and a generic fallback. Each profile carries a
  command prefix that ensures ``launch_openpilot.sh`` executes correctly in that
  environment as well as some user-facing notes for the menu and documentation.
  """

  env = os.environ
  prefix = _default_launch_prefix()

  if env.get("WSL_DISTRO_NAME"):
    distro = env.get("WSL_DISTRO_NAME", "WSL")
    notes = (
      "Windows Subsystem for Linux detected; the Start command will run the launch "
      "script through bash so Linux-style paths and permissions are honoured."
    )
    return HostEnvironment(
      identifier="wsl",
      description=f"Windows Subsystem for Linux ({distro})",
      launch_prefix=prefix,
      notes=notes,
    )

  if env.get("VSCODE_GIT_IPC_HANDLE") or env.get("TERM_PROGRAM") == "vscode" or env.get("VSCODE_NLS_CONFIG"):
    notes = (
      "Visual Studio Code terminal detected; the Start button works from the "
      "integrated terminal or debugger and uses bash when available."
    )
    if env.get("VSCODE_WSL_EXT_LOCATION"):
      notes += " WSL integration is enabled, so the bash launcher keeps working."
    return HostEnvironment(
      identifier="vscode",
      description="Visual Studio Code terminal",
      launch_prefix=prefix,
      notes=notes,
    )

  os_release = Path("/etc/os-release")
  distro_id = ""
  pretty_name = ""
  if os_release.exists():
    for line in os_release.read_text(encoding="utf-8", errors="ignore").splitlines():
      if line.startswith("ID="):
        distro_id = line.split("=", 1)[1].strip().strip('"')
      elif line.startswith("PRETTY_NAME="):
        pretty_name = line.split("=", 1)[1].strip().strip('"')
    if distro_id == "ubuntu":
      notes = "Native Ubuntu environment detected; launch scripts run through bash."
      description = pretty_name or "Ubuntu"
      return HostEnvironment(
        identifier="ubuntu",
        description=description,
        launch_prefix=prefix,
        notes=notes,
      )

  system = platform.system()
  release = platform.release()
  description = f"{system} {release}".strip()
  notes = "Generic environment detected; falling back to the repository launch script."
  if not prefix:
    notes += " Install bash if openpilot's launch script requires it."
  return HostEnvironment(
    identifier=(system or "unknown").lower(),
    description=description or "unknown host",
    launch_prefix=prefix,
    notes=notes,
  )

