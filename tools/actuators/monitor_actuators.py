#!/usr/bin/env python3
"""Stream actuator commands published by openpilot."""
import argparse
import math
import time
from typing import Any, Iterable, Tuple

from cereal import messaging


DEFAULT_FIELDS = (
  ("steeringAngleDeg", "steering angle (deg)"),
  ("torque", "steering torque"),
  ("steer", "raw steer command"),
  ("steerRate", "steer rate"),
  ("accel", "acceleration request"),
  ("brake", "brake request"),
  ("longControlState", "longitudinal state"),
)

TOPIC_TO_FIELDS = {
  "carControl": "actuators",
  "carOutput": "actuatorsOutput",
}


def _safe_getattr(obj: Any, name: str) -> Any:
  if obj is None:
    return None
  return getattr(obj, name, None)


def _format_value(value: Any) -> str:
  if isinstance(value, float):
    if math.isnan(value) or math.isinf(value):
      return "nan"
    return f"{value: .3f}"
  if isinstance(value, bool):
    return "True" if value else "False"
  if value is None:
    return "-"
  return str(value)


def _iter_fields(obj: Any, fields: Iterable[Tuple[str, str]]):
  for field, label in fields:
    yield label, _safe_getattr(obj, field)


def stream_actuators(topic: str, rate_hz: float, fields: Iterable[Tuple[str, str]]):
  sub = messaging.SubMaster([topic])
  interval = 0.0 if rate_hz <= 0 else 1.0 / rate_hz
  next_emit = 0.0

  print(f"Subscribed to '{topic}' - press Ctrl+C to stop.")
  while True:
    sub.update(1000)
    if not sub.updated[topic]:
      continue

    now = time.monotonic()
    if now < next_emit:
      continue
    next_emit = now + interval

    message = sub[topic]
    actuators_attr = TOPIC_TO_FIELDS[topic]
    actuators = getattr(message, actuators_attr, None)
    stamp = getattr(message, "logMonoTime", 0)

    parts = [f"logMonoTime={stamp}"]
    for label, value in _iter_fields(actuators, fields):
      parts.append(f"{label}: {_format_value(value)}")
    print(" | ".join(parts), flush=True)


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(
    description=(
      "Print actuator command values as they are published on openpilot's messaging bus. "
      "Run this while openpilot is active to monitor steering and longitudinal commands."
    )
  )
  parser.add_argument(
    "--topic",
    choices=sorted(TOPIC_TO_FIELDS),
    default="carControl",
    help="Which message stream to monitor. 'carControl' shows the controller commands before safety limits,"
         " while 'carOutput' shows the commands after safety limits are applied.",
  )
  parser.add_argument(
    "--rate",
    type=float,
    default=5.0,
    help="Maximum print rate in Hz. Use 0 for every update (may be very verbose).",
  )
  return parser.parse_args()


def main() -> None:
  args = parse_args()
  try:
    stream_actuators(args.topic, args.rate, DEFAULT_FIELDS)
  except KeyboardInterrupt:
    pass


if __name__ == "__main__":
  main()
