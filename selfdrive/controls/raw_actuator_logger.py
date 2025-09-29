#!/usr/bin/env python3
import atexit
import csv
import os
from datetime import datetime, timezone
from typing import TextIO


class RawActuatorLogger:
  """Persist raw actuator output to a CSV file while printing at a reduced rate."""

  def __init__(self, path: str | None = None, print_period: int = 10) -> None:
    self.print_period = max(1, int(print_period))
    self._counter = 0

    if path is None:
      path = os.path.expanduser('~/raw_actuator_output.csv')

    self.path = path
    directory = os.path.dirname(self.path)
    if directory:
      os.makedirs(directory, exist_ok=True)

    self._file: TextIO = open(self.path, 'w', newline='')
    self._writer = csv.writer(self._file)
    self._writer.writerow(['iso_timestamp_utc', 'monotonic_time_ns', 'steering', 'braking', 'throttle'])
    self._file.flush()
    atexit.register(self.close)

  def log(self, steering: float, braking: float, throttle: float, monotonic_time_ns: int) -> None:
    iso_timestamp = datetime.now(timezone.utc).isoformat()
    self._writer.writerow([iso_timestamp, int(monotonic_time_ns), float(steering), float(braking), float(throttle)])
    self._file.flush()

    if self._counter == 0:
      print(f"Raw actuator output: ({steering:.6f}, {braking:.6f}, {throttle:.6f}) @ {iso_timestamp}")
    self._counter = (self._counter + 1) % self.print_period

  def close(self) -> None:
    if not self._file.closed:
      self._file.flush()
      self._file.close()
