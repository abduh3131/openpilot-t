from __future__ import annotations

import argparse
import textwrap
from pathlib import Path
from typing import Iterable, List, Optional

from .hub import SensorHub
from .logging_utils import LOG_FILE, configure_logging
from .types import DetectedSensor

MENU = textwrap.dedent(
  """
  Scooter Sensor Hub
  ==================
  [R] Rescan sensors      [E] Enable sensor      [D] Disable sensor
  [S] Start autopilot     [T] Stop autopilot     [L] View hub log
  [A] View autopilot log  [Q] Quit
  """
)


def _print_sensors(sensors: Iterable[DetectedSensor], active: List[str]) -> None:
  print("\nDetected sensors:")
  empty = True
  for idx, sensor in enumerate(sensors, start=1):
    empty = False
    status = "*" if sensor.identifier in active else " "
    print(f"  [{idx:02d}] [{status}] {sensor.identifier} | {sensor.name} | {sensor.kind.value} | {sensor.path}")
  if empty:
    print("  (none detected)")


def _tail_file(path: Path, lines: int = 40) -> None:
  if not path.exists():
    print(f"No log file at {path}")
    return
  print(f"\n--- Last {lines} lines of {path} ---")
  with path.open("r", encoding="utf-8", errors="ignore") as fh:
    content = fh.readlines()[-lines:]
  for line in content:
    print(line.rstrip())
  print("--- end ---\n")


def run_cli(hub: SensorHub) -> None:
  hub.scan_sensors()
  while True:
    sensors = hub.get_detected()
    active = hub.get_active()
    print(MENU)
    _print_sensors(sensors, active)
    choice = input("Select option: ").strip().lower()
    if choice == "r":
      hub.scan_sensors()
    elif choice == "e":
      sensor_id = _prompt_sensor_id(sensors, active)
      if sensor_id:
        hub.start_sensor(sensor_id)
    elif choice == "d":
      sensor_id = _prompt_sensor_id(sensors, active, only_active=True)
      if sensor_id:
        hub.stop_sensor(sensor_id)
    elif choice == "s":
      hub.start_autopilot()
    elif choice == "t":
      hub.stop_autopilot()
    elif choice == "l":
      _tail_file(LOG_FILE)
    elif choice == "a":
      _tail_file(hub.autopilot_log_path)
    elif choice == "q":
      break
    else:
      print("Unknown option. Please choose again.")


def _prompt_sensor_id(sensors: List[DetectedSensor], active: List[str], only_active: bool = False) -> Optional[str]:
  if not sensors:
    print("No sensors available.")
    return None
  mapping: dict[str, str] = {}
  for idx, sensor in enumerate(sensors, start=1):
    if only_active and sensor.identifier not in active:
      continue
    mapping[str(idx)] = sensor.identifier
    mapping[sensor.identifier] = sensor.identifier
  if not mapping:
    print("No matching sensors for this action.")
    return None
  selection = input("Enter sensor number or identifier: ").strip()
  sensor_id = mapping.get(selection)
  if not sensor_id:
    print("Invalid selection.")
  return sensor_id


def main(argv: Optional[List[str]] = None) -> int:
  parser = argparse.ArgumentParser(description="External sensor hub for openpilot")
  parser.add_argument("--once", action="store_true", help="Scan sensors once and print the roster")
  args = parser.parse_args(argv)

  configure_logging()
  hub = SensorHub()
  if args.once:
    sensors = hub.scan_sensors()
    _print_sensors(sensors, hub.get_active())
    return 0

  try:
    run_cli(hub)
  finally:
    hub.shutdown()
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
