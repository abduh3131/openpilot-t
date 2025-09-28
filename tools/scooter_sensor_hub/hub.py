from __future__ import annotations

import subprocess
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Dict, Iterable, List, MutableSequence, Optional

import cereal.messaging as messaging
from cereal import log

from .detectors import ConfigDetector, SerialDeviceDetector, VideoDeviceDetector, load_sensor_overrides
from .environment import detect_host_environment
from .drivers import MockSensorDriver, SensorDriverError, driver_for_sensor
from .logging_utils import configure_logging
from .preflight import run_preflight_checks
from .models import (
  DetectedSensor,
  HostEnvironment,
  PrepStepResult,
  Publisher,
  SensorKind,
  SensorSession,
  SensorTestResult,
)

__all__ = [
  "MessagingPublisher",
  "SensorHub",
]


MOCK_SENSOR_DEFINITIONS: Iterable[dict[str, object]] = (
  {
    "identifier": "mock:camera",
    "name": "Mock Camera",
    "kind": SensorKind.CAMERA,
    "transport": "virtual",
    "path": Path("/virtual/mock_camera"),
    "description": "synthetic RGB frames",
  },
  {
    "identifier": "mock:ultrasonic",
    "name": "Mock Ultrasonic",
    "kind": SensorKind.ULTRASONIC,
    "transport": "virtual",
    "path": Path("/virtual/mock_ultrasonic"),
    "description": "synthetic range readings",
  },
  {
    "identifier": "mock:lidar",
    "name": "Mock Lidar",
    "kind": SensorKind.LIDAR,
    "transport": "virtual",
    "path": Path("/virtual/mock_lidar"),
    "description": "synthetic scan packets",
  },
)


class MessagingPublisher(Publisher):
  """Real publisher that writes to the openpilot messaging bus."""

  def __init__(self) -> None:
    self._pm = messaging.PubMaster(["sensorHubState", "sensorData"])

  def send_hub_state(self, msg) -> None:  # type: ignore[override]
    self._pm.send("sensorHubState", msg.to_bytes())

  def send_sensor_data(self, msg) -> None:  # type: ignore[override]
    self._pm.send("sensorData", msg.to_bytes())


class SensorHub:
  """Manage device discovery, sensor streaming, and autopilot lifecycle."""

  def __init__(
    self,
    publisher: Optional[Publisher] = None,
    repo_root: Optional[Path] = None,
    host_environment: Optional[HostEnvironment] = None,
  ) -> None:
    self.publisher = publisher or MessagingPublisher()
    self.repo_root = repo_root or Path(__file__).resolve().parents[2]
    self.logger, self.log_file = configure_logging()
    self.host_environment = host_environment or detect_host_environment()
    self._environment_locked = host_environment is not None

    overrides = load_sensor_overrides()
    self.detectors = [
      VideoDeviceDetector(overrides),
      SerialDeviceDetector(overrides),
      ConfigDetector(overrides),
    ]

    self.detected: Dict[str, DetectedSensor] = OrderedDict()
    self.sessions: Dict[str, SensorSession] = {}
    self.issues: MutableSequence[str] = []
    self._lock = threading.RLock()
    self._autopilot_process: Optional[subprocess.Popen] = None
    self._autopilot_log_handle = None
    self.autopilot_log_path = self.log_file.parent / "autopilot.log"

  # ---------------------------------------------------------------------------
  # Discovery & state publishing
  # ---------------------------------------------------------------------------
  def scan_sensors(self) -> List[DetectedSensor]:
    with self._lock:
      catalog: Dict[str, DetectedSensor] = OrderedDict()
      for detector in self.detectors:
        try:
          sensors = detector.scan()
        except Exception as exc:  # pragma: no cover - defensive
          self.logger.exception("Detector %s failed", detector.__class__.__name__)
          self.issues.append(f"Detector {detector.__class__.__name__} failed: {exc}")
          continue
        for sensor in sensors:
          catalog[sensor.identifier] = sensor
      if not catalog:
        self._inject_mock_sensors(catalog)
      missing = set(self.sessions) - set(catalog)
      for sensor_id in missing:
        self.logger.warning("Sensor %s removed, stopping stream", sensor_id)
        self._stop_sensor_locked(sensor_id)
      self.detected = catalog
      self.publish_state()
      return list(catalog.values())

  def publish_state(self) -> None:
    with self._lock:
      msg = log.Event.new_message("sensorHubState")
      state = msg.sensorHubState
      state.timestampMono = time.monotonic_ns()
      sensors = list(self.detected.values())
      state.init("detectedSensors", len(sensors))
      for idx, sensor in enumerate(sensors):
        entry = state.detectedSensors[idx]
        entry.sensorId = sensor.identifier
        entry.name = sensor.name
        entry.type = getattr(log.ExternalSensorType, sensor.kind.name.lower())
        entry.transport = sensor.transport
        entry.path = str(sensor.path)
        entry.description = sensor.description
        metadata_items = list(sensor.metadata.items())
        entry.init("metadataEntries", len(metadata_items))
        for m_idx, (key, value) in enumerate(metadata_items):
          metadata = entry.metadataEntries[m_idx]
          metadata.key = str(key)
          metadata.value = str(value)
      active_ids = list(self.sessions.keys())
      state.init("activeSensorIds", len(active_ids))
      for idx, sensor_id in enumerate(active_ids):
        state.activeSensorIds[idx] = sensor_id
      issue_items = list(dict.fromkeys(self.issues))
      state.init("issues", len(issue_items))
      for idx, issue in enumerate(issue_items):
        state.issues[idx] = issue
      self.publisher.send_hub_state(msg)

  # ---------------------------------------------------------------------------
  # Sensor lifecycle
  # ---------------------------------------------------------------------------
  def start_sensor(self, sensor_id: str) -> bool:
    with self._lock:
      if sensor_id in self.sessions:
        self.logger.info("Sensor %s already running", sensor_id)
        return False
      sensor = self.detected.get(sensor_id)
      if sensor is None:
        raise KeyError(f"Sensor {sensor_id} not found")

    fallback_reason = ""
    try:
      driver = driver_for_sensor(sensor)
      driver.start()
    except SensorDriverError as exc:
      self.logger.warning("Falling back to mock driver for %s: %s", sensor_id, exc)
      fallback_reason = str(exc)
      metadata = dict(sensor.metadata)
      metadata.setdefault("mock", "true")
      sensor = DetectedSensor(
        identifier=sensor.identifier,
        name=sensor.name,
        kind=sensor.kind,
        transport=sensor.transport,
        path=sensor.path,
        description=sensor.description,
        metadata=metadata,
      )
      with self._lock:
        self.detected[sensor_id] = sensor
      driver = MockSensorDriver(sensor)
      driver.start()

    stop_event = threading.Event()
    thread = threading.Thread(
      target=self._run_driver,
      args=(driver, stop_event),
      name=f"sensor-{sensor_id}",
      daemon=True,
    )
    session = SensorSession(sensor=sensor, driver=driver, stop=stop_event, thread=thread)

    with self._lock:
      self.sessions[sensor_id] = session
      thread.start()
      self.logger.info("Started sensor %s", sensor_id)
      if fallback_reason:
        self.issues.append(f"{sensor_id}: using mock driver ({fallback_reason})")
      self.publish_state()
    return True

  def _run_driver(self, driver, stop_event: threading.Event) -> None:
    try:
      driver.stream(self.publisher, stop_event)
    except Exception as exc:
      self.logger.exception("Driver %s crashed", driver.sensor.identifier)
      with self._lock:
        self.issues.append(f"{driver.sensor.identifier}: {exc}")
        self.sessions.pop(driver.sensor.identifier, None)
        self.publish_state()

  def stop_sensor(self, sensor_id: str) -> bool:
    with self._lock:
      return self._stop_sensor_locked(sensor_id)

  def _stop_sensor_locked(self, sensor_id: str) -> bool:
    session = self.sessions.pop(sensor_id, None)
    if not session:
      return False
    session.stop.set()
    session.thread.join(timeout=2.0)
    try:
      session.driver.stop()
    except Exception:
      self.logger.exception("Error stopping sensor %s", sensor_id)
    self.logger.info("Stopped sensor %s", sensor_id)
    self.publish_state()
    return True

  def stop_all_sensors(self) -> None:
    for sensor_id in list(self.sessions.keys()):
      self.stop_sensor(sensor_id)

  def start_all_sensors(self) -> List[str]:
    with self._lock:
      sensor_ids = [sensor_id for sensor_id in self.detected if sensor_id not in self.sessions]
    started: List[str] = []
    for sensor_id in sensor_ids:
      if self.start_sensor(sensor_id):
        started.append(sensor_id)
    return started

  # ---------------------------------------------------------------------------
  # Preparation & diagnostics
  # ---------------------------------------------------------------------------
  def prepare_environment(self) -> List[PrepStepResult]:
    """Ensure dependencies, directories, and assets are available."""

    if not self._environment_locked:
      self.host_environment = detect_host_environment()

    results = run_preflight_checks(
      self.repo_root,
      self.log_file.parent,
      self.autopilot_log_path,
      host_environment=self.host_environment,
    )

    with self._lock:
      for result in results:
        if result.status == "error":
          self.issues.append(f"Prep failed: {result.step} ({result.detail})")
      self.publish_state()

    for result in results:
      if result.status == "error":
        self.logger.error("Preparation step failed: %s (%s)", result.step, result.detail)
      else:
        self.logger.info("Preparation step %s -> %s", result.step, result.status)

    return results

  def test_sensors(self) -> List[SensorTestResult]:
    """Probe each detected sensor to confirm the driver can initialise it."""

    with self._lock:
      sensors = list(self.detected.values())
      active_ids = set(self.sessions.keys())

    results: List[SensorTestResult] = []
    for sensor in sensors:
      if sensor.identifier in active_ids:
        results.append(SensorTestResult(sensor.identifier, "skipped", "already streaming"))
        continue

      driver = None
      try:
        driver = driver_for_sensor(sensor)
        driver.start()
      except SensorDriverError as exc:
        self.logger.error("Self-test failed for %s: %s", sensor.identifier, exc)
        results.append(SensorTestResult(sensor.identifier, "error", str(exc)))
        continue
      except Exception as exc:  # pragma: no cover - defensive
        self.logger.exception("Unexpected failure initialising %s", sensor.identifier)
        results.append(SensorTestResult(sensor.identifier, "error", str(exc)))
        continue

      try:
        detail = "driver initialised"
        results.append(SensorTestResult(sensor.identifier, "ok", detail))
      finally:
        try:
          driver.stop()
        except Exception:  # pragma: no cover - defensive
          self.logger.exception("Error cleaning up driver for %s", sensor.identifier)

    if any(result.status == "error" for result in results):
      with self._lock:
        for result in results:
          if result.status == "error":
            self.issues.append(f"Sensor self-test failed: {result.sensor_id} ({result.detail})")
        self.publish_state()

    return results

  # ---------------------------------------------------------------------------
  # Autopilot lifecycle
  # ---------------------------------------------------------------------------
  def start_autopilot(self) -> tuple[bool, List[str]]:
    self.scan_sensors()
    started_sensors = self.start_all_sensors()
    with self._lock:
      if self._autopilot_process and self._autopilot_process.poll() is None:
        self.logger.info("Autopilot already running")
        return False, started_sensors
      script = self.repo_root / "launch_openpilot.sh"
      if not script.exists():
        raise FileNotFoundError(f"Unable to locate {script}")
      log_handle = self.autopilot_log_path.open("a", buffering=1)
      command = list(self.host_environment.launch_prefix) + [str(script)]
      process = subprocess.Popen(command, cwd=self.repo_root, stdout=log_handle, stderr=subprocess.STDOUT)
      self._autopilot_process = process
      self._autopilot_log_handle = log_handle
      self.logger.info(
        "Started autopilot (PID %s) via %s", process.pid, self.host_environment.description
      )
      return True, started_sensors

  def stop_autopilot(self) -> bool:
    with self._lock:
      proc = self._autopilot_process
      if not proc or proc.poll() is not None:
        self.logger.info("Autopilot not running")
        return False
      proc.terminate()
      try:
        proc.wait(timeout=10)
      except subprocess.TimeoutExpired:
        self.logger.warning("Autopilot did not exit in time, killing")
        proc.kill()
        proc.wait(timeout=5)
      finally:
        if self._autopilot_log_handle:
          self._autopilot_log_handle.close()
          self._autopilot_log_handle = None
      self.logger.info("Stopped autopilot")
      return True

  def autopilot_running(self) -> bool:
    with self._lock:
      return bool(self._autopilot_process and self._autopilot_process.poll() is None)

  # ---------------------------------------------------------------------------
  # Utilities
  # ---------------------------------------------------------------------------
  def get_detected(self) -> List[DetectedSensor]:
    with self._lock:
      return list(self.detected.values())

  def get_active(self) -> List[str]:
    with self._lock:
      return list(self.sessions.keys())

  def shutdown(self) -> None:
    self.stop_all_sensors()
    self.stop_autopilot()

  # ---------------------------------------------------------------------------
  # Mock sensor helpers
  # ---------------------------------------------------------------------------
  def _inject_mock_sensors(self, catalog: Dict[str, DetectedSensor]) -> None:
    self.logger.info("No physical sensors detected, adding mock feeds")
    for definition in MOCK_SENSOR_DEFINITIONS:
      kind_value = definition.get("kind", SensorKind.OTHER)
      if isinstance(kind_value, SensorKind):
        kind = kind_value
      else:
        try:
          kind = SensorKind(str(kind_value))
        except ValueError:
          kind = SensorKind.OTHER
      metadata = {
        "mock": "true",
        "transport": str(definition.get("transport", "virtual")),
        "source": "auto-fallback",
      }
      sensor = DetectedSensor(
        identifier=str(definition["identifier"]),
        name=str(definition["name"]),
        kind=kind,
        transport=str(definition.get("transport", "virtual")),
        path=Path(str(definition.get("path", "/virtual/mock"))),
        description=str(definition.get("description", "")),
        metadata=metadata,
      )
      catalog[sensor.identifier] = sensor
