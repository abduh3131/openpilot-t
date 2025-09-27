#!/usr/bin/env python3
import csv
from pathlib import Path

from openpilot.selfdrive.controls.raw_actuator_logger import RawActuatorLogger


def test_raw_actuator_logger_creates_csv(tmp_path: Path) -> None:
  log_path = tmp_path / 'raw.csv'
  logger = RawActuatorLogger(path=str(log_path), print_period=3)

  logger.log(1.0, 0.0, 0.5, 123)
  logger.log(0.0, 1.0, 0.0, 456)
  logger.close()

  with log_path.open() as f:
    rows = list(csv.reader(f))

  assert rows[0] == ['iso_timestamp_utc', 'monotonic_time_ns', 'steering', 'braking', 'throttle']
  assert rows[1][0].endswith('+00:00')
  assert rows[1][1:] == ['123', '1.0', '0.0', '0.5']
  assert rows[2][1:] == ['456', '0.0', '1.0', '0.0']
