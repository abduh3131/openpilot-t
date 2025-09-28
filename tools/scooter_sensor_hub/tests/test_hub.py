from __future__ import annotations

import time
from pathlib import Path

import pytest
from cereal import log

from tools.scooter_sensor_hub.hub import SensorHub
from tools.scooter_sensor_hub.types import DetectedSensor, Publisher, SensorKind


class FakePublisher(Publisher):
  def __init__(self) -> None:
    self.hub_msgs = []
    self.sensor_msgs = []

  def send_hub_state(self, msg) -> None:  # type: ignore[override]
    self.hub_msgs.append(msg)

  def send_sensor_data(self, msg) -> None:  # type: ignore[override]
    self.sensor_msgs.append(msg)


class StaticDetector:
  def __init__(self, sensors):
    self._sensors = sensors

  def scan(self):
    return list(self._sensors)


class DummyDriver:
  def __init__(self, sensor: DetectedSensor):
    self.sensor = sensor
    self.started = False
    self.stopped = False

  def start(self) -> None:
    self.started = True

  def stream(self, publisher: Publisher, stop_event) -> None:
    msg = log.Event.new_message("sensorData")
    data = msg.sensorData
    data.timestampMono = 1
    data.sensorId = self.sensor.identifier
    data.type = log.ExternalSensorType.camera
    data.sequence = 1
    data.confidence = 1.0
    cam = data.camera
    cam.encoding = log.ExternalSensorCameraSample.CameraEncoding.jpeg
    cam.width = 1
    cam.height = 1
    cam.frameRate = 0.0
    cam.exposureUsec = 0
    cam.captureMonoTime = 1
    cam.data = b"ÿØ"
    publisher.send_sensor_data(msg)
    stop_event.wait(0.01)

  def stop(self) -> None:
    self.stopped = True


@pytest.fixture
def sample_sensor() -> DetectedSensor:
  return DetectedSensor(
    identifier="camera:video0",
    name="Test Camera",
    kind=SensorKind.CAMERA,
    transport="v4l2",
    path=Path("/dev/video0"),
    description="",
    metadata={}
  )


def test_scan_publishes_hub_state(monkeypatch, sample_sensor):
  publisher = FakePublisher()
  hub = SensorHub(publisher=publisher, repo_root=Path.cwd())
  hub.detectors = [StaticDetector([sample_sensor])]
  sensors = hub.scan_sensors()
  assert sensors and sensors[0].identifier == sample_sensor.identifier
  assert publisher.hub_msgs, "expected a hub state message"
  state = publisher.hub_msgs[-1].sensorHubState
  assert state.detectedSensors[0].sensorId == sample_sensor.identifier


def test_start_sensor_uses_driver(monkeypatch, sample_sensor):
  publisher = FakePublisher()
  hub = SensorHub(publisher=publisher, repo_root=Path.cwd())
  hub.detectors = [StaticDetector([sample_sensor])]
  hub.scan_sensors()

  driver = DummyDriver(sample_sensor)

  def fake_driver_for_sensor(sensor):
    assert sensor.identifier == sample_sensor.identifier
    return driver

  monkeypatch.setattr('tools.scooter_sensor_hub.hub.driver_for_sensor', fake_driver_for_sensor)

  assert hub.start_sensor(sample_sensor.identifier)
  time.sleep(0.05)
  assert driver.started
  assert publisher.sensor_msgs, "sensor driver should have emitted a sample"
  hub.stop_sensor(sample_sensor.identifier)
  assert driver.stopped
