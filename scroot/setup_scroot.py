#!/usr/bin/env python3
"""Bootstrap script for the scooter autonomy stack.

This script creates an isolated Python virtual environment, installs the
project dependencies, downloads the default perception and advisor models,
and prepares the directory layout expected by ``autonomy_launcher.py``.

Run it from the ``scroot`` directory:

    python setup_scroot.py

After completion you can activate the virtual environment and launch the
pilot:

    source .venv/bin/activate
    python autonomy_launcher.py --camera 0
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from textwrap import dedent
import venv

ROOT = Path(__file__).resolve().parent
DEFAULT_VENV = ROOT / ".venv"
DEFAULT_MODELS_DIR = ROOT / "models"
REQUIREMENTS_FILE = ROOT / "autonomy" / "requirements.txt"

YOLO_MODEL = "yolov8n.pt"
BLIP_MODEL = "Salesforce/blip-image-captioning-base"
FLAN_MODEL = "google/flan-t5-small"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Set up the scooter autonomy environment")
    parser.add_argument(
        "--venv",
        type=Path,
        default=DEFAULT_VENV,
        help="Path to create or reuse the Python virtual environment (default: ./.venv)",
    )
    parser.add_argument(
        "--models-dir",
        type=Path,
        default=DEFAULT_MODELS_DIR,
        help="Directory where downloaded model weights will be stored (default: ./models)",
    )
    parser.add_argument(
        "--skip-models",
        action="store_true",
        help="Skip downloading pretrained model checkpoints",
    )
    parser.add_argument(
        "--upgrade",
        action="store_true",
        help="Force reinstallation of dependencies even if the environment exists",
    )
    return parser.parse_args()


def check_python_version() -> None:
    if sys.version_info < (3, 10):
        raise RuntimeError(
            "Python 3.10 or newer is required. Current version: "
            f"{platform.python_version()}"
        )


def run(cmd: list[str], env: dict[str, str] | None = None) -> None:
    print(f"[setup] Running: {' '.join(cmd)}")
    subprocess.check_call(cmd, env=env)


def ensure_venv(path: Path, upgrade: bool) -> Path:
    if path.exists() and not (path / "bin" / "python").exists() and not (path / "Scripts" / "python.exe").exists():
        raise RuntimeError(f"{path} exists but does not look like a virtual environment")

    if upgrade and path.exists():
        print(f"[setup] Removing existing virtual environment at {path}")
        shutil.rmtree(path)

    if not path.exists():
        print(f"[setup] Creating virtual environment at {path}")
        builder = venv.EnvBuilder(with_pip=True)
        builder.create(path)
    else:
        print(f"[setup] Reusing virtual environment at {path}")

    if os.name == "nt":
        python_path = path / "Scripts" / "python.exe"
    else:
        python_path = path / "bin" / "python"

    if not python_path.exists():
        raise RuntimeError(f"Unable to locate python executable inside {path}")

    return python_path


def install_requirements(python_exe: Path) -> None:
    if not REQUIREMENTS_FILE.exists():
        raise FileNotFoundError(f"Cannot find requirements file at {REQUIREMENTS_FILE}")

    run([str(python_exe), "-m", "pip", "install", "--upgrade", "pip"])
    run([str(python_exe), "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)])


def download_models(python_exe: Path, models_dir: Path) -> None:
    models_dir.mkdir(parents=True, exist_ok=True)

    download_script = dedent(
        f"""
        import json
        from pathlib import Path

        from huggingface_hub import snapshot_download
        from ultralytics import YOLO

        models_dir = Path({models_dir!r})
        models_dir.mkdir(parents=True, exist_ok=True)

        summary = {{}}

        # Download YOLO weights using the Ultralytics loader (caches under ~/.cache/ultralytics).
        yolo_model = {YOLO_MODEL!r}
        YOLO(yolo_model)
        summary["yolo"] = yolo_model

        # Download BLIP and FLAN checkpoints into deterministic local folders.
        blip_repo = {BLIP_MODEL!r}
        flan_repo = {FLAN_MODEL!r}

        blip_dir = models_dir / "blip"
        flan_dir = models_dir / "flan"

        snapshot_download(repo_id=blip_repo, local_dir=blip_dir, local_dir_use_symlinks=False)
        snapshot_download(repo_id=flan_repo, local_dir=flan_dir, local_dir_use_symlinks=False)

        manifest_path = models_dir / "manifest.json"
        manifest_path.write_text(json.dumps(summary, indent=2))
        print(f"Models cached under {{models_dir}}")
        """
    )

    run([str(python_exe), "-c", download_script])


def ensure_runtime_dirs() -> None:
    for name in ("logs", "models"):
        path = ROOT / name
        path.mkdir(exist_ok=True)
        print(f"[setup] Ensured directory: {path}")


def main() -> None:
    check_python_version()
    args = parse_args()

    ensure_runtime_dirs()
    venv_python = ensure_venv(args.venv, args.upgrade)
    install_requirements(venv_python)

    if not args.skip_models:
        download_models(venv_python, args.models_dir)
    else:
        print("[setup] Skipping model downloads as requested")

    print("\n[setup] Completed successfully!\n")
    activation_hint = "Scripts\\activate" if os.name == "nt" else "bin/activate"
    print(
        dedent(
            f"""
            Next steps:
              1. Activate the virtual environment:
                     source {args.venv}/{activation_hint}
              2. Launch the pilot:
                     python autonomy_launcher.py --camera 0
            """
        ).strip()
    )


if __name__ == "__main__":
    main()
