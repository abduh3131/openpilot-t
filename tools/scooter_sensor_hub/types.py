from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping


class SensorKind(str, Enum):
  """Supported sensor categories."""

  CAMERA = "camera"
  ULTRASONIC = "ultrasonic"
  LIDAR = "lidar"
  IMU = "imu"
  GPS = "gps"
  OTHER = "other"


@dataclass(frozen=True, slots=True)
class DetectedSensor:
  """Information about a device discovered on the host system."""

  identifier: str
  name: str
  kind: SensorKind
  transport: str
  path: Path
  description: str = ""
  metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class SensorSession:
  """Runtime information for a streaming sensor."""

  sensor: DetectedSensor
  driver: "SensorDriver"
  stop: "threading.Event"
  thread: "threading.Thread"


@dataclass(frozen=True, slots=True)
class PrepStepResult:
  """Outcome of a single environment preparation step."""

  step: str
  status: str
  detail: str = ""


@dataclass(frozen=True, slots=True)
class SensorTestResult:
  """Outcome of an on-demand sensor self test."""

  sensor_id: str
  status: str
  detail: str = ""


class SensorDriver:
  """Protocol for sensor streaming implementations."""

  def __init__(self, sensor: DetectedSensor):
    self.sensor = sensor

  def start(self) -> None:
    """Allocate resources before the streaming loop starts."""

  def stream(self, publisher: "Publisher", stop_event: "threading.Event") -> None:
    """Continuously publish samples until ``stop_event`` is set."""
    raise NotImplementedError

  def stop(self) -> None:
    """Release any resources acquired in :meth:`start`."""


class Publisher:
  """Abstraction over the messaging layer for dependency injection."""

  def send_hub_state(self, msg: Any) -> None:  # pragma: no cover - interface
    raise NotImplementedError

  def send_sensor_data(self, msg: Any) -> None:  # pragma: no cover - interface
    raise NotImplementedError
