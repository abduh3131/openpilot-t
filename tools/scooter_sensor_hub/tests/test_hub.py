from __future__ import annotations

import time
from pathlib import Path

import pytest
from cereal import log

from tools.scooter_sensor_hub.hub import SensorHub
from tools.scooter_sensor_hub.drivers import MockSensorDriver, SensorDriverError
from tools.scooter_sensor_hub.models import (
  DetectedSensor,
  HostEnvironment,
  PrepStepResult,
  Publisher,
  SensorKind,
)


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


def test_prepare_environment_records_failures(monkeypatch):
  publisher = FakePublisher()
  hub = SensorHub(publisher=publisher, repo_root=Path.cwd())

  expected = [
    PrepStepResult(step="Example", status="error", detail="missing"),
    PrepStepResult(step="Other", status="ok", detail="fine"),
  ]

  monkeypatch.setattr(
    "tools.scooter_sensor_hub.hub.run_preflight_checks",
    lambda *args, **kwargs: expected,
  )

  results = hub.prepare_environment()
  assert results == expected
  assert any("Example" in issue for issue in hub.issues)


def test_sensor_self_test_uses_driver(monkeypatch, sample_sensor):
  publisher = FakePublisher()
  hub = SensorHub(publisher=publisher, repo_root=Path.cwd())
  hub.detectors = [StaticDetector([sample_sensor])]
  hub.scan_sensors()

  driver = DummyDriver(sample_sensor)

  def fake_driver_for_sensor(sensor):
    return driver

  monkeypatch.setattr("tools.scooter_sensor_hub.hub.driver_for_sensor", fake_driver_for_sensor)

  results = hub.test_sensors()
  assert results and results[0].status == "ok"
  assert driver.started and driver.stopped


def test_scan_injects_mock_when_none():
  publisher = FakePublisher()
  hub = SensorHub(publisher=publisher, repo_root=Path.cwd())
  hub.detectors = [StaticDetector([])]
  sensors = hub.scan_sensors()
  assert sensors, "expected mock sensors to be injected"
  assert any(sensor.metadata.get("mock") == "true" for sensor in sensors)


def test_start_sensor_falls_back_to_mock(monkeypatch, sample_sensor):
  publisher = FakePublisher()
  hub = SensorHub(publisher=publisher, repo_root=Path.cwd())
  hub.detectors = [StaticDetector([sample_sensor])]
  hub.scan_sensors()

  def fake_driver_for_sensor(sensor):
    raise SensorDriverError("missing hardware")

  monkeypatch.setattr("tools.scooter_sensor_hub.hub.driver_for_sensor", fake_driver_for_sensor)

  assert hub.start_sensor(sample_sensor.identifier)
  time.sleep(0.05)
  session = hub.sessions[sample_sensor.identifier]
  assert isinstance(session.driver, MockSensorDriver)
  hub.stop_sensor(sample_sensor.identifier)


def test_start_autopilot_uses_environment_prefix(monkeypatch, tmp_path):
  repo_root = tmp_path
  script = repo_root / "launch_openpilot.sh"
  script.write_text("#!/bin/bash\necho hi\n", encoding="utf-8")
  script.chmod(0o755)

  publisher = FakePublisher()
  host_env = HostEnvironment(
    identifier="wsl",
    description="Windows Subsystem for Linux",
    launch_prefix=("/bin/bash",),
    notes="",
  )
  hub = SensorHub(publisher=publisher, repo_root=repo_root, host_environment=host_env)
  monkeypatch.setattr(hub, "scan_sensors", lambda: [])
  monkeypatch.setattr(hub, "start_all_sensors", lambda: [])

  captured: dict[str, list[str]] = {}

  class DummyProcess:
    pid = 1234

    def poll(self):
      return None

    def terminate(self):
      return None

    def wait(self, timeout=None):
      return 0

    def kill(self):
      return None

  def fake_popen(cmd, **kwargs):
    captured["cmd"] = cmd
    return DummyProcess()

  monkeypatch.setattr("tools.scooter_sensor_hub.hub.subprocess.Popen", fake_popen)

  started, sensors = hub.start_autopilot()
  assert started is True
  assert sensors == []
  assert captured["cmd"] == ["/bin/bash", str(script)]
