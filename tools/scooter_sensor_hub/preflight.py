from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Sequence

from .environment import detect_host_environment
from .types import HostEnvironment, PrepStepResult

__all__ = ["run_preflight_checks", "DEFAULT_SUBMODULES", "DEFAULT_PYTHON_DEPENDENCIES"]

DEFAULT_SUBMODULES: Sequence[str] = (
  "opendbc_repo",
  "rednose_repo",
  "tinygrad_repo",
)

DEFAULT_PYTHON_DEPENDENCIES = {
  "cv2": "opencv-python",
  "serial": "pyserial",
}


def _ensure_directory(path: Path, description: str) -> PrepStepResult:
  path.mkdir(parents=True, exist_ok=True)
  return PrepStepResult(step=description, status="ok", detail=str(path))


def _ensure_file(path: Path, description: str) -> PrepStepResult:
  path.parent.mkdir(parents=True, exist_ok=True)
  if not path.exists():
    path.touch()
  return PrepStepResult(step=description, status="ok", detail=str(path))


def _ensure_launch_script(script: Path) -> PrepStepResult:
  if script.exists():
    return PrepStepResult(step="Launch script", status="ok", detail=str(script))
  return PrepStepResult(step="Launch script", status="error", detail=f"Missing {script}")


def _ensure_submodule(repo_root: Path, submodule: str) -> PrepStepResult:
  path = repo_root / submodule
  try:
    has_content = path.exists() and any(path.iterdir())
  except OSError:
    has_content = False
  if has_content:
    return PrepStepResult(step=f"Submodule {submodule}", status="skipped", detail="already available")

  cmd = ["git", "submodule", "update", "--init", "--recursive", submodule]
  try:
    subprocess.run(cmd, cwd=repo_root, check=True, capture_output=True, text=True)
    return PrepStepResult(step=f"Submodule {submodule}", status="ok", detail="downloaded")
  except FileNotFoundError:
    return PrepStepResult(step=f"Submodule {submodule}", status="error", detail="git executable not found")
  except subprocess.CalledProcessError as exc:
    message = exc.stderr.strip() or exc.stdout.strip() or str(exc)
    return PrepStepResult(step=f"Submodule {submodule}", status="error", detail=message)


def _ensure_python_package(module_name: str, package_name: str) -> PrepStepResult:
  if importlib.util.find_spec(module_name) is not None:
    return PrepStepResult(
      step=f"Python package {package_name}",
      status="skipped",
      detail="already installed",
    )

  cmd = [sys.executable, "-m", "pip", "install", package_name]
  try:
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    summary = result.stdout.strip().splitlines()[-1] if result.stdout else "installed"
    return PrepStepResult(step=f"Python package {package_name}", status="ok", detail=summary)
  except subprocess.CalledProcessError as exc:
    message = exc.stderr.strip() or exc.stdout.strip() or str(exc)
    return PrepStepResult(step=f"Python package {package_name}", status="error", detail=message)


def run_preflight_checks(
  repo_root: Path,
  log_directory: Path,
  autopilot_log: Path,
  submodules: Iterable[str] = DEFAULT_SUBMODULES,
  python_dependencies: dict[str, str] | None = None,
  host_environment: HostEnvironment | None = None,
) -> List[PrepStepResult]:
  """Prepare the host so the sensor hub and openpilot can run seamlessly."""

  profile = host_environment or detect_host_environment()

  results: List[PrepStepResult] = [
    PrepStepResult(
      step="Host environment",
      status="ok",
      detail=f"{profile.description} [{profile.identifier}]",
    )
  ]
  results.append(_ensure_directory(log_directory, "Sensor hub log directory"))
  results.append(_ensure_file(autopilot_log, "Autopilot log file"))
  results.append(_ensure_launch_script(repo_root / "launch_openpilot.sh"))

  for submodule in submodules:
    results.append(_ensure_submodule(repo_root, submodule))

  dependencies = python_dependencies or DEFAULT_PYTHON_DEPENDENCIES
  for module_name, package_name in dependencies.items():
    results.append(_ensure_python_package(module_name, package_name))

  return results
