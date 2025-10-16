#!/usr/bin/env python3
"""Desktop launcher and telemetry dashboard for openpilot."""
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple

from cereal import messaging
from cereal.log import log
from PySide6 import QtCore, QtGui, QtWidgets


ACTUATOR_FIELDS: Tuple[Tuple[str, str], ...] = (
  ("steeringAngleDeg", "Steering angle (deg)"),
  ("torque", "Steering torque"),
  ("steer", "Raw steer command"),
  ("steerRate", "Steer rate"),
  ("accel", "Acceleration request"),
  ("brake", "Brake request"),
  ("longControlState", "Longitudinal state"),
)

CAMERA_SENSORS = {
  log.FrameData.ImageSensor.unknown: "Unknown",
  log.FrameData.ImageSensor.ar0231: "AR0231 (Road)",
  log.FrameData.ImageSensor.ox03c10: "OX03C10 (Driver)",
  log.FrameData.ImageSensor.os04c10: "OS04C10 (Wide Road)",
}

NETWORK_TYPES = {
  log.DeviceState.NetworkType.none: "Offline",
  log.DeviceState.NetworkType.wifi: "Wi-Fi",
  log.DeviceState.NetworkType.cell2G: "Cell 2G",
  log.DeviceState.NetworkType.cell3G: "Cell 3G",
  log.DeviceState.NetworkType.cell4G: "Cell 4G",
  log.DeviceState.NetworkType.cell5G: "Cell 5G",
  log.DeviceState.NetworkType.ethernet: "Ethernet",
}

NETWORK_STRENGTHS = {
  log.DeviceState.NetworkStrength.unknown: "Unknown",
  log.DeviceState.NetworkStrength.poor: "Poor",
  log.DeviceState.NetworkStrength.moderate: "Moderate",
  log.DeviceState.NetworkStrength.good: "Good",
  log.DeviceState.NetworkStrength.great: "Great",
}

THERMAL_STATES = {
  log.DeviceState.ThermalStatus.green: "Nominal",
  log.DeviceState.ThermalStatus.yellow: "Warm",
  log.DeviceState.ThermalStatus.red: "Hot",
  log.DeviceState.ThermalStatus.danger: "Danger",
}


@dataclass
class MessagingSnapshot:
  actuators: Optional[Dict[str, str]] = None
  actuators_output: Optional[Dict[str, str]] = None
  camera: Optional[Dict[str, str]] = None
  device: Optional[Dict[str, str]] = None
  car: Optional[Dict[str, str]] = None


def _format_number(value: Optional[float], precision: int = 3) -> str:
  if value is None:
    return "-"
  return f"{value:.{precision}f}"


def _format_actuators(data: Optional[object]) -> Dict[str, str]:
  result: Dict[str, str] = {}
  if data is None:
    return {label: "-" for _, label in ACTUATOR_FIELDS}

  for attr, label in ACTUATOR_FIELDS:
    value = getattr(data, attr, None)
    if isinstance(value, float):
      result[label] = _format_number(value)
    elif isinstance(value, bool):
      result[label] = "True" if value else "False"
    elif value is None:
      result[label] = "-"
    else:
      result[label] = str(value)
  return result


def _format_camera(frame: Optional[object]) -> Dict[str, str]:
  if frame is None:
    return {
      "Sensor": "-",
      "Frame": "-",
      "Processing": "-",
      "Exposure": "-",
      "Temperature": "-",
    }

  temperatures = list(frame.temperaturesC)
  temperature = temperatures[0] if temperatures else None
  sensor_name = CAMERA_SENSORS.get(frame.sensor, f"Sensor #{frame.sensor}")
  exposure = frame.exposureValPercent if hasattr(frame, "exposureValPercent") else None
  processing = getattr(frame, "processingTime", None)

  return {
    "Sensor": sensor_name,
    "Frame": str(frame.frameId),
    "Processing": f"{processing * 1000.0:.1f} ms" if processing is not None else "-",
    "Exposure": _format_number(exposure, precision=1) + "%" if exposure is not None else "-",
    "Temperature": _format_number(temperature, precision=1) + " °C" if temperature is not None else "-",
  }


def _format_device(state: Optional[object]) -> Dict[str, str]:
  if state is None:
    return {
      "Network": "-",
      "Storage": "-",
      "Thermals": "-",
      "Fan": "-",
    }

  network = NETWORK_TYPES.get(state.networkType, "Unknown")
  strength = NETWORK_STRENGTHS.get(getattr(state, "networkStrength", None), None)
  if strength and strength != "Unknown":
    network += f" ({strength})"

  free_space = getattr(state, "freeSpacePercent", None)
  storage = f"{_format_number(free_space, 1)}% free" if free_space is not None else "-"
  max_temp = getattr(state, "maxTempC", None)
  thermal_status = THERMAL_STATES.get(getattr(state, "thermalStatus", None), "Unknown")
  thermals = f"{thermal_status} / {_format_number(max_temp, 1)} °C" if max_temp is not None else thermal_status
  fan_speed = getattr(state, "fanSpeedPercentDesired", None)
  fan = f"{fan_speed} %" if fan_speed is not None else "-"

  return {
    "Network": network,
    "Storage": storage,
    "Thermals": thermals,
    "Fan": fan,
  }


def _format_car(state: Optional[object]) -> Dict[str, str]:
  if state is None:
    return {
      "Speed": "-",
      "Acceleration": "-",
      "Standstill": "-",
    }

  speed = getattr(state, "vEgo", None)
  accel = getattr(state, "aEgo", None)
  return {
    "Speed": f"{_format_number(speed, 2)} m/s" if speed is not None else "-",
    "Acceleration": f"{_format_number(accel, 2)} m/s²" if accel is not None else "-",
    "Standstill": "Yes" if getattr(state, "standstill", False) else "No",
  }


class SubMasterWorker(QtCore.QThread):
  snapshot_ready = QtCore.Signal(MessagingSnapshot)

  def __init__(self, parent: Optional[QtCore.QObject] = None):
    super().__init__(parent)
    self._topics = [
      "carControl",
      "carOutput",
      "roadCameraState",
      "deviceState",
      "carState",
    ]
    self._running = threading.Event()
    self._running.set()

  def run(self) -> None:
    sub_master = messaging.SubMaster(self._topics)
    try:
      while self._running.is_set():
        sub_master.update(100)

        snapshot = MessagingSnapshot()
        if sub_master.updated.get("carControl"):
          snapshot.actuators = _format_actuators(sub_master["carControl"].actuators)
        if sub_master.updated.get("carOutput"):
          snapshot.actuators_output = _format_actuators(sub_master["carOutput"].actuatorsOutput)
        if sub_master.updated.get("roadCameraState"):
          snapshot.camera = _format_camera(sub_master["roadCameraState"])
        if sub_master.updated.get("deviceState"):
          snapshot.device = _format_device(sub_master["deviceState"])
        if sub_master.updated.get("carState"):
          snapshot.car = _format_car(sub_master["carState"])

        if any((snapshot.actuators, snapshot.actuators_output, snapshot.camera, snapshot.device, snapshot.car)):
          self.snapshot_ready.emit(snapshot)
    except Exception as exc:  # pragma: no cover - defensive guard for GUI thread
      sys.stderr.write(f"[openpilot-desktop] messaging worker error: {exc}\n")

  def stop(self) -> None:
    self._running.clear()


class KeyValueGroup(QtWidgets.QGroupBox):
  def __init__(self, title: str, keys: Iterable[str]):
    super().__init__(title)
    self._labels: Dict[str, QtWidgets.QLabel] = {}
    form = QtWidgets.QFormLayout()
    for key in keys:
      label = QtWidgets.QLabel("-")
      label.setObjectName(key)
      label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
      form.addRow(f"{key}:", label)
      self._labels[key] = label
    self.setLayout(form)

  def update_values(self, values: Dict[str, str]) -> None:
    for key, label in self._labels.items():
      if key in values:
        label.setText(values[key])


class MainWindow(QtWidgets.QWidget):
  def __init__(self, repo_root: Path, parent: Optional[QtWidgets.QWidget] = None):
    super().__init__(parent)
    self.repo_root = repo_root
    self.openpilot_process: Optional[subprocess.Popen[str]] = None

    self.setWindowTitle("openpilot Desktop Controller")
    self.resize(900, 600)

    self.status_label = QtWidgets.QLabel("openpilot is not running")
    self.status_label.setAlignment(QtCore.Qt.AlignCenter)
    self.status_label.setStyleSheet("font-size: 16px; font-weight: 600;")

    self.run_button = QtWidgets.QPushButton("Start openpilot")
    self.run_button.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_MediaPlay))
    self.run_button.clicked.connect(self.toggle_openpilot)

    self.actuator_group = KeyValueGroup("Actuator Commands", [label for _, label in ACTUATOR_FIELDS])
    self.output_group = KeyValueGroup("Post-Safety Actuators", [label for _, label in ACTUATOR_FIELDS])
    self.camera_group = KeyValueGroup("Camera", ["Sensor", "Frame", "Processing", "Exposure", "Temperature"])
    self.device_group = KeyValueGroup("Device", ["Network", "Storage", "Thermals", "Fan"])
    self.car_group = KeyValueGroup("Vehicle", ["Speed", "Acceleration", "Standstill"])

    control_layout = QtWidgets.QHBoxLayout()
    control_layout.addWidget(self.status_label, stretch=2)
    control_layout.addWidget(self.run_button, stretch=1)

    telemetry_layout = QtWidgets.QGridLayout()
    telemetry_layout.addWidget(self.actuator_group, 0, 0)
    telemetry_layout.addWidget(self.output_group, 0, 1)
    telemetry_layout.addWidget(self.camera_group, 1, 0)
    telemetry_layout.addWidget(self.device_group, 1, 1)
    telemetry_layout.addWidget(self.car_group, 2, 0, 1, 2)

    layout = QtWidgets.QVBoxLayout()
    title = QtWidgets.QLabel("openpilot Desktop Launcher")
    font = QtGui.QFont()
    font.setPointSize(20)
    font.setBold(True)
    title.setFont(font)
    title.setAlignment(QtCore.Qt.AlignCenter)

    layout.addWidget(title)
    layout.addLayout(control_layout)
    layout.addLayout(telemetry_layout)

    self.setLayout(layout)

    self._worker = SubMasterWorker()
    self._worker.snapshot_ready.connect(self.on_snapshot)
    self._worker.start()

    self._process_timer = QtCore.QTimer(self)
    self._process_timer.setInterval(1000)
    self._process_timer.timeout.connect(self._refresh_process_status)
    self._process_timer.start()

  @QtCore.Slot()
  def toggle_openpilot(self) -> None:
    if self.openpilot_process and self.openpilot_process.poll() is None:
      self.stop_openpilot()
    else:
      self.start_openpilot()

  def start_openpilot(self) -> None:
    if self.openpilot_process and self.openpilot_process.poll() is None:
      return

    env = os.environ.copy()
    launch_script = self.repo_root / "launch_openpilot.sh"
    if not launch_script.exists():
      QtWidgets.QMessageBox.critical(self, "Launch error", "launch_openpilot.sh not found in repository root")
      return

    try:
      self.openpilot_process = subprocess.Popen(
        ["./launch_openpilot.sh"],
        cwd=self.repo_root,
        env=env,
        preexec_fn=os.setsid,
      )
    except OSError as exc:
      QtWidgets.QMessageBox.critical(self, "Launch error", f"Failed to start openpilot: {exc}")
      self.openpilot_process = None
      return

    self.run_button.setText("Stop openpilot")
    self.run_button.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_MediaStop))
    self.status_label.setText("openpilot is starting...")

  def stop_openpilot(self) -> None:
    if not self.openpilot_process:
      return

    if self.openpilot_process.poll() is None:
      try:
        os.killpg(os.getpgid(self.openpilot_process.pid), signal.SIGINT)
      except ProcessLookupError:
        pass
      try:
        self.openpilot_process.wait(timeout=10)
      except subprocess.TimeoutExpired:
        self.openpilot_process.terminate()
    self.openpilot_process = None
    self.run_button.setText("Start openpilot")
    self.run_button.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_MediaPlay))
    self.status_label.setText("openpilot is not running")

  @QtCore.Slot(MessagingSnapshot)
  def on_snapshot(self, snapshot: MessagingSnapshot) -> None:
    if snapshot.actuators:
      self.actuator_group.update_values(snapshot.actuators)
    if snapshot.actuators_output:
      self.output_group.update_values(snapshot.actuators_output)
    if snapshot.camera:
      self.camera_group.update_values(snapshot.camera)
    if snapshot.device:
      self.device_group.update_values(snapshot.device)
    if snapshot.car:
      self.car_group.update_values(snapshot.car)

  def _refresh_process_status(self) -> None:
    running = self.openpilot_process and self.openpilot_process.poll() is None
    if running:
      self.status_label.setText("openpilot is running")
    else:
      self.status_label.setText("openpilot is not running")
      if self.openpilot_process and self.openpilot_process.poll() is not None:
        self.openpilot_process = None
        self.run_button.setText("Start openpilot")
        self.run_button.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_MediaPlay))

  def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # type: ignore[override]
    self._worker.stop()
    self._worker.wait(2000)
    self.stop_openpilot()
    super().closeEvent(event)


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Launch and monitor openpilot from a desktop GUI")
  parser.add_argument(
    "--root",
    type=Path,
    default=Path(__file__).resolve().parents[2],
    help="Root directory of the openpilot repository",
  )
  return parser.parse_args()


def main() -> int:
  args = parse_args()
  repo_root = args.root.resolve()
  if not (repo_root / "launch_openpilot.sh").exists():
    print(f"launch_openpilot.sh not found in {repo_root}", file=sys.stderr)
    return 1

  app = QtWidgets.QApplication(sys.argv)
  window = MainWindow(repo_root)
  window.show()
  return app.exec()


if __name__ == "__main__":
  raise SystemExit(main())
