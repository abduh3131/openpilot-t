from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Mapping, MutableMapping

from .models import DetectedSensor, SensorKind

CONFIG_DIR = Path.home() / ".config" / "scooter_sensor_hub"
CONFIG_FILE = CONFIG_DIR / "sensors.yaml"

__all__ = [
  "SensorDetector",
  "VideoDeviceDetector",
  "SerialDeviceDetector",
  "ConfigDetector",
  "load_sensor_overrides",
]


@dataclass(slots=True)
class SensorDetector:
  """Abstract base class for sensor discovery helpers."""

  overrides: Mapping[str, Mapping[str, str]]

  def scan(self) -> List[DetectedSensor]:
    raise NotImplementedError


class VideoDeviceDetector(SensorDetector):
  """Detect V4L2 cameras exposed under ``/dev/video*``."""

  def scan(self) -> List[DetectedSensor]:
    devices = sorted(Path("/dev").glob("video*"))
    sensors: List[DetectedSensor] = []
    for dev in devices:
      path = dev.resolve()
      identifier = f"camera:{path.name}"
      override = self.overrides.get(identifier, {})
      name = override.get("name") or override.get("label") or f"Camera {path.name}"
      description = override.get("description", "")
      transport = override.get("transport", "v4l2")
      metadata: MutableMapping[str, str] = {
        "path": str(path),
        "transport": transport,
      }

      card_name = _query_v4l2_card_name(path)
      if card_name:
        metadata["card"] = card_name
        description = description or card_name

      metadata.update({k: v for k, v in override.items() if isinstance(v, str)})
      sensors.append(
        DetectedSensor(
          identifier=identifier,
          name=name,
          kind=SensorKind.CAMERA,
          transport=transport,
          path=path,
          description=description,
          metadata=dict(metadata),
        )
      )
    return sensors


class SerialDeviceDetector(SensorDetector):
  """Detect serial devices and classify them heuristically."""

  KEYWORDS = {
    SensorKind.LIDAR: ("lidar", "velodyne", "ouster", "rplidar", "slamtec"),
    SensorKind.ULTRASONIC: ("ultrasonic", "sonar", "hc-sr04", "maxbotix"),
    SensorKind.IMU: ("imu", "accelerometer", "gyroscope"),
  }

  def scan(self) -> List[DetectedSensor]:
    sensors: List[DetectedSensor] = []
    try:
      from serial.tools import list_ports
    except Exception:
      return sensors

    for port in list_ports.comports():
      path = Path(port.device)
      identifier = f"serial:{path.name}"
      info = " ".join(filter(None, [port.manufacturer, port.description, port.hwid])).strip()
      kind = self._classify(info.lower())
      override = self.overrides.get(identifier, {})

      override_kind = override.get("kind")
      if override_kind:
        try:
          kind = SensorKind(override_kind.lower())
        except ValueError:
          pass

      name = override.get("name") or port.description or path.name
      description = override.get("description") or info
      transport = override.get("transport", "serial")
      metadata = {
        "hwid": port.hwid or "",
        "manufacturer": port.manufacturer or "",
        "product": port.product or "",
        "serial_number": port.serial_number or "",
      }
      metadata.update({k: v for k, v in override.items() if isinstance(v, str)})

      sensors.append(
        DetectedSensor(
          identifier=identifier,
          name=name,
          kind=kind,
          transport=transport,
          path=path,
          description=description,
          metadata=metadata,
        )
      )
    return sensors

  def _classify(self, info: str) -> SensorKind:
    for kind, keywords in self.KEYWORDS.items():
      for keyword in keywords:
        if keyword in info:
          return kind
    return SensorKind.OTHER


class ConfigDetector(SensorDetector):
  """Load virtual or network sensors defined in the user configuration."""

  def scan(self) -> List[DetectedSensor]:
    sensors: List[DetectedSensor] = []
    for identifier, values in self.overrides.items():
      if not identifier.startswith("static:"):
        continue
      path = Path(values.get("path", identifier.split(":", 1)[-1])).expanduser()
      try:
        kind = SensorKind(values.get("kind", "other").lower())
      except ValueError:
        kind = SensorKind.OTHER
      sensors.append(
        DetectedSensor(
          identifier=identifier,
          name=values.get("name", identifier),
          kind=kind,
          transport=values.get("transport", "network"),
          path=path,
          description=values.get("description", ""),
          metadata={k: v for k, v in values.items() if isinstance(v, str)},
        )
      )
    return sensors


def load_sensor_overrides() -> Mapping[str, Mapping[str, str]]:
  """Load user configuration overrides for sensor metadata."""

  if not CONFIG_FILE.exists():
    return {}

  text = CONFIG_FILE.read_text()
  if not text.strip():
    return {}

  try:
    import yaml  # type: ignore

    data = yaml.safe_load(text) or {}
  except ModuleNotFoundError:
    data = json.loads(text)

  if isinstance(data, Mapping):
    sensors_section = data.get("sensors")
    if isinstance(sensors_section, Mapping):
      return {str(k): v for k, v in sensors_section.items() if isinstance(v, Mapping)}

  return {}


def _query_v4l2_card_name(path: Path) -> str:
  if not shutil.which("v4l2-ctl"):
    return ""
  try:
    result = subprocess.run(
      ["v4l2-ctl", "--device", str(path), "--info"],
      check=False,
      capture_output=True,
      text=True,
    )
  except Exception:
    return ""

  for line in result.stdout.splitlines():
    if "Card type" in line:
      return line.split(":", 1)[-1].strip()
  return ""
