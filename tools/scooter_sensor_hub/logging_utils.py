from __future__ import annotations

import logging
from pathlib import Path
from typing import Tuple

__all__ = ["configure_logging", "LOG_DIR", "LOG_FILE"]

LOG_DIR = Path.home() / ".local" / "share" / "scooter_sensor_hub"
LOG_FILE = LOG_DIR / "hub.log"


def configure_logging() -> Tuple[logging.Logger, Path]:
  """Configure a rotating log file shared across the sensor hub."""

  LOG_DIR.mkdir(parents=True, exist_ok=True)
  logger = logging.getLogger("scooter_sensor_hub")
  logger.setLevel(logging.INFO)

  if not logger.handlers:
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

  return logger, LOG_FILE
