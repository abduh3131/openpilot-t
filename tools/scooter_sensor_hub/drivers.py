from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from cereal import log

from .types import DetectedSensor, Publisher, SensorDriver, SensorKind

__all__ = [
  "SensorDriverError",
  "CameraDriver",
  "UltrasonicDriver",
  "LidarDriver",
  "driver_for_sensor",
]


class SensorDriverError(RuntimeError):
  """Raised when a driver cannot be started due to missing dependencies or hardware."""


@dataclass(slots=True)
class _BaseDriver(SensorDriver):
  sensor: DetectedSensor

  def __post_init__(self) -> None:
    super().__init__(self.sensor)
    self._sequence = 0

  def _next_sequence(self) -> int:
    self._sequence += 1
    return self._sequence


class CameraDriver(_BaseDriver):
  """Stream frames from a V4L2-compatible camera device."""

  def __init__(self, sensor: DetectedSensor):
    super().__init__(sensor)
    self._cap = None
    self._cv2 = None

  def start(self) -> None:
    try:
      import cv2  # type: ignore
    except ModuleNotFoundError as exc:
      raise SensorDriverError("OpenCV is required for camera streaming") from exc

    self._cv2 = cv2
    source = str(self.sensor.path)
    self._cap = cv2.VideoCapture(source)
    if not self._cap.isOpened():
      raise SensorDriverError(f"Unable to open camera device {source}")

  def stream(self, publisher: Publisher, stop_event: threading.Event) -> None:
    assert self._cap is not None and self._cv2 is not None
    capture_time = time.monotonic_ns

    width = int(self._cap.get(self._cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(self._cap.get(self._cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    fps = float(self._cap.get(self._cv2.CAP_PROP_FPS) or 0.0)

    while not stop_event.is_set():
      ok, frame = self._cap.read()
      if not ok:
        time.sleep(0.1)
        continue

      success, encoded = self._cv2.imencode(".jpg", frame)
      if not success:
        continue

      msg = log.Event.new_message("sensorData")
      data = msg.sensorData
      data.timestampMono = time.monotonic_ns()
      data.sensorId = self.sensor.identifier
      data.type = log.ExternalSensorType.camera
      data.sequence = self._next_sequence()
      data.confidence = 1.0

      camera = data.camera
      camera.encoding = log.ExternalSensorCameraSample.CameraEncoding.jpeg
      camera.width = width or frame.shape[1]
      camera.height = height or frame.shape[0]
      camera.frameRate = fps
      camera.exposureUsec = 0
      camera.captureMonoTime = capture_time()
      camera.data = encoded.tobytes()

      publisher.send_sensor_data(msg)

    self.stop()

  def stop(self) -> None:
    if self._cap is not None:
      self._cap.release()
      self._cap = None


class UltrasonicDriver(_BaseDriver):
  """Read range measurements from a serial ultrasonic sensor."""

  def __init__(self, sensor: DetectedSensor, baudrate: int = 9600):
    super().__init__(sensor)
    self._serial = None
    self._baudrate = baudrate

  def start(self) -> None:
    try:
      import serial  # type: ignore
    except ModuleNotFoundError as exc:
      raise SensorDriverError("pyserial is required for ultrasonic streaming") from exc

    self._serial = serial.Serial(str(self.sensor.path), self._baudrate, timeout=1.0)

  def stream(self, publisher: Publisher, stop_event: threading.Event) -> None:
    assert self._serial is not None
    while not stop_event.is_set():
      line = self._serial.readline()
      if not line:
        continue
      try:
        distance = float(line.decode("utf-8", "ignore").strip())
      except ValueError:
        continue

      msg = log.Event.new_message("sensorData")
      data = msg.sensorData
      data.timestampMono = time.monotonic_ns()
      data.sensorId = self.sensor.identifier
      data.type = log.ExternalSensorType.ultrasonic
      data.sequence = self._next_sequence()
      data.confidence = 1.0
      sample = data.ultrasonic
      sample.distanceMeters = distance
      sample.signalStrength = 1.0
      publisher.send_sensor_data(msg)

    self.stop()

  def stop(self) -> None:
    if self._serial is not None:
      try:
        self._serial.close()
      finally:
        self._serial = None


class LidarDriver(_BaseDriver):
  """Consume packets from a serial-based lidar and forward them raw."""

  def __init__(self, sensor: DetectedSensor, baudrate: int = 115200):
    super().__init__(sensor)
    self._serial = None
    self._baudrate = baudrate

  def start(self) -> None:
    try:
      import serial  # type: ignore
    except ModuleNotFoundError as exc:
      raise SensorDriverError("pyserial is required for lidar streaming") from exc

    self._serial = serial.Serial(str(self.sensor.path), self._baudrate, timeout=1.0)

  def stream(self, publisher: Publisher, stop_event: threading.Event) -> None:
    assert self._serial is not None
    while not stop_event.is_set():
      packet = self._serial.read(2048)
      if not packet:
        continue

      msg = log.Event.new_message("sensorData")
      data = msg.sensorData
      data.timestampMono = time.monotonic_ns()
      data.sensorId = self.sensor.identifier
      data.type = log.ExternalSensorType.lidar
      data.sequence = self._next_sequence()
      data.confidence = 1.0
      sample = data.lidar
      sample.format = log.ExternalSensorLidarSample.PointCloudFormat.custom
      sample.pointCount = 0
      sample.data = packet
      publisher.send_sensor_data(msg)

    self.stop()

  def stop(self) -> None:
    if self._serial is not None:
      try:
        self._serial.close()
      finally:
        self._serial = None


def driver_for_sensor(sensor: DetectedSensor) -> SensorDriver:
  if sensor.kind is SensorKind.CAMERA:
    return CameraDriver(sensor)
  if sensor.kind is SensorKind.ULTRASONIC:
    return UltrasonicDriver(sensor)
  if sensor.kind is SensorKind.LIDAR:
    return LidarDriver(sensor)
  raise SensorDriverError(f"No driver implemented for sensor kind {sensor.kind.value}")
