from __future__ import annotations

import argparse
import textwrap
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from .hub import SensorHub
from .logging_utils import LOG_FILE, configure_logging
from .models import DetectedSensor, PrepStepResult, SensorTestResult

MENU = textwrap.dedent(
  """
  Scooter Sensor Hub
  ==================
  [R] Rescan sensors        [E] Enable sensor      [D] Disable sensor
  [S] Prep & start autopilot[P] Prep environment   [H] Test sensors
  [T] Stop autopilot        [L] View hub log       [A] View autopilot log
  [Q] Quit
  """
)


def _print_sensors(sensors: Iterable[DetectedSensor], active: List[str]) -> None:
  print("\nDetected sensors:")
  empty = True
  for idx, sensor in enumerate(sensors, start=1):
    empty = False
    status = "*" if sensor.identifier in active else " "
    metadata_flag = str(sensor.metadata.get("mock", "")).lower()
    display_name = sensor.name
    if metadata_flag in {"true", "1", "yes", "mock"}:
      display_name = f"{display_name} (mock)"
    print(f"  [{idx:02d}] [{status}] {sensor.identifier} | {display_name} | {sensor.kind.value} | {sensor.path}")
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


def _print_prep_results(results: Sequence[PrepStepResult]) -> None:
  print("\nPreparation summary:")
  if not results:
    print("  (no actions performed)")
    return
  for result in results:
    detail = f" - {result.detail}" if result.detail else ""
    print(f"  [{result.status.upper():>7}] {result.step}{detail}")


def _print_sensor_test_results(results: Sequence[SensorTestResult]) -> None:
  print("\nSensor self-test results:")
  if not results:
    print("  (no sensors detected)")
    return
  for result in results:
    detail = f" - {result.detail}" if result.detail else ""
    print(f"  [{result.status.upper():>7}] {result.sensor_id}{detail}")


def run_cli(hub: SensorHub) -> None:
  initial = hub.prepare_environment()
  _print_prep_results(initial)
  env = hub.host_environment
  print(
    f"\nHost environment detected: {env.description} [{env.identifier}]"
  )
  if env.notes:
    wrapped = textwrap.fill(
      f"Notes: {env.notes}", width=78, subsequent_indent="       "
    )
    print(wrapped)
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
      prep_results = hub.prepare_environment()
      _print_prep_results(prep_results)
      if any(result.status == "error" for result in prep_results):
        print("Preparation reported issues; continuing with mock fallbacks where needed.")
      started, auto_started = hub.start_autopilot()
      if auto_started:
        started_list = ", ".join(auto_started)
        print(f"Streaming sensors: {started_list}")
      else:
        print("All configured sensors were already streaming.")
      if started:
        print(f"Autopilot launch initiated via {hub.host_environment.description}.")
      else:
        print("Autopilot already running.")
    elif choice == "t":
      hub.stop_autopilot()
    elif choice == "p":
      prep_results = hub.prepare_environment()
      _print_prep_results(prep_results)
    elif choice == "h":
      results = hub.test_sensors()
      _print_sensor_test_results(results)
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
