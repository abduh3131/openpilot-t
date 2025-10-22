from __future__ import annotations

import importlib
import sys
from typing import Optional

REQUIRED_PACKAGES = [
    "cv2",
    "ultralytics",
    "torch",
    "transformers",
]


def _check_dependencies() -> None:
    missing = []
    for package in REQUIRED_PACKAGES:
        try:
            importlib.import_module(package)
        except Exception:  # pragma: no cover - used for runtime dependency checks
            missing.append(package)
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(
            "Missing required packages: "
            f"{joined}. Install them with 'python -m pip install -r autonomy/requirements.txt'."
        )


def main(argv: Optional[list[str]] = None) -> None:
    """Entry point that wires dependency checking with the pilot."""

    _check_dependencies()

    from autonomy.pilot import main as pilot_main  # pylint: disable=import-outside-toplevel

    pilot_main(argv)


if __name__ == "__main__":  # pragma: no cover
    main(sys.argv[1:])
