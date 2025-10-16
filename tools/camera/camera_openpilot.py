#!/usr/bin/env python3
"""Run a camera-only openpilot control loop and log actuator outputs to CSV."""
from __future__ import annotations

import argparse
import csv
import signal
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Union

import os

import numpy as np

try:
  import cv2  # type: ignore[import]
except Exception as exc:  # pragma: no cover - dependency is required at runtime
  cv2 = None
  _cv2_import_error = exc
else:
  _cv2_import_error = None

from cereal import car, log, messaging

LongCtrlState = car.CarControl.Actuators.LongControlState
GearShifter = car.CarState.GearShifter
ThermalStatus = log.DeviceState.ThermalStatus
NetworkType = log.DeviceState.NetworkType
NetworkStrength = log.DeviceState.NetworkStrength
ImageSensor = log.FrameData.ImageSensor

LONG_STATE_LABELS = {value: name for name, value in LongCtrlState.schema.enumerants.items()}


@dataclass
class ActuatorSnapshot:
  steer: float
  steering_angle_deg: float
  steer_rate: float
  torque: float
  accel: float
  brake: float
  long_control_state: int
  speed: float
  accel_estimate: float
  processing_time_s: float
  exposure_percent: float
  camera_temp_c: float
  center_offset: float


def resolve_camera(target: str) -> Union[int, str]:
  target = target.strip()
  if target == "":
    raise ValueError("Camera target cannot be empty")
  try:
    return int(target)
  except ValueError:
    return target


def compute_actuator_snapshot(frame: np.ndarray, prev_angle: float, prev_speed: float, dt: float) -> ActuatorSnapshot:
  start = time.perf_counter()
  height, width = frame.shape[:2]
  gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
  blur = cv2.GaussianBlur(gray, (5, 5), 0)
  edges = cv2.Canny(blur, 50, 150)

  mask = np.zeros_like(edges)
  roi = np.array([
    [
      (0, height),
      (width, height),
      (width, int(height * 0.55)),
      (0, int(height * 0.55)),
    ]
  ], dtype=np.int32)
  cv2.fillPoly(mask, roi, 255)
  cropped = cv2.bitwise_and(edges, mask)

  lines = cv2.HoughLinesP(
    cropped,
    1,
    np.pi / 180,
    threshold=60,
    minLineLength=max(width // 4, 50),
    maxLineGap=80,
  )

  center_offset = 0.0
  if lines is not None:
    left_slopes: list[float] = []
    left_intercepts: list[float] = []
    right_slopes: list[float] = []
    right_intercepts: list[float] = []

    for x1, y1, x2, y2 in lines[:, 0, :]:
      if x1 == x2:
        continue
      slope = (y2 - y1) / (x2 - x1)
      if abs(slope) < 0.3 or abs(slope) > 10:
        continue
      intercept = y1 - slope * x1
      if slope < 0:
        left_slopes.append(slope)
        left_intercepts.append(intercept)
      else:
        right_slopes.append(slope)
        right_intercepts.append(intercept)

    lane_center = width / 2.0
    y_eval = height * 0.9
    if left_slopes and right_slopes:
      left_x = (y_eval - float(np.mean(left_intercepts))) / float(np.mean(left_slopes))
      right_x = (y_eval - float(np.mean(right_intercepts))) / float(np.mean(right_slopes))
      lane_center = (left_x + right_x) / 2.0
    elif left_slopes:
      left_x = (y_eval - float(np.mean(left_intercepts))) / float(np.mean(left_slopes))
      lane_center = left_x + width * 0.25
    elif right_slopes:
      right_x = (y_eval - float(np.mean(right_intercepts))) / float(np.mean(right_slopes))
      lane_center = right_x - width * 0.25

    center_offset = (lane_center - width / 2.0) / (width / 2.0)

  desired_angle = float(np.clip(-center_offset * 20.0, -25.0, 25.0))
  steer = float(np.clip(desired_angle / 25.0, -1.0, 1.0))
  steer_rate = (desired_angle - prev_angle) / dt if dt > 1e-3 else 0.0
  torque = steer

  target_speed = max(2.0, 12.0 - abs(steer) * 6.0)
  smoothing = min(dt * 0.7, 1.0)
  speed = prev_speed + (target_speed - prev_speed) * smoothing
  accel_estimate = (speed - prev_speed) / dt if dt > 1e-6 else 0.0

  accel = max(0.0, 0.5 - abs(steer) * 0.4)
  brake = max(0.0, abs(steer) - 0.85) * 0.5
  processing_time_s = time.perf_counter() - start
  exposure_percent = float(np.clip(50.0 + center_offset * 10.0, 0.0, 100.0))
  camera_temp_c = float(np.clip(35.0 + abs(center_offset) * 5.0, 25.0, 60.0))

  return ActuatorSnapshot(
    steer=steer,
    steering_angle_deg=desired_angle,
    steer_rate=steer_rate,
    torque=torque,
    accel=accel,
    brake=brake,
    long_control_state=LongCtrlState.pid,
    speed=speed,
    accel_estimate=accel_estimate,
    processing_time_s=processing_time_s,
    exposure_percent=exposure_percent,
    camera_temp_c=camera_temp_c,
    center_offset=center_offset,
  )


def publish_messages(
  pm: messaging.PubMaster,
  snapshot: ActuatorSnapshot,
  frame_id: int,
  timestamp_ns: int,
) -> None:
  cc_msg = messaging.new_message("carControl")
  cc_msg.valid = True
  cc = cc_msg.carControl
  cc.enabled = True
  cc.latActive = True
  cc.longActive = True
  cc.actuators.steer = snapshot.steer
  cc.actuators.steeringAngleDeg = snapshot.steering_angle_deg
  cc.actuators.steerRate = snapshot.steer_rate
  cc.actuators.torque = snapshot.torque
  cc.actuators.accel = snapshot.accel
  cc.actuators.brake = snapshot.brake
  cc.actuators.longControlState = snapshot.long_control_state
  pm.send("carControl", cc_msg)

  co_msg = messaging.new_message("carOutput")
  co_msg.valid = True
  co = co_msg.carOutput
  co.enabled = True
  co.latActive = True
  co.longActive = True
  co.actuatorsOutput.steer = snapshot.steer
  co.actuatorsOutput.steeringAngleDeg = snapshot.steering_angle_deg
  co.actuatorsOutput.steerRate = snapshot.steer_rate
  co.actuatorsOutput.torque = snapshot.torque
  co.actuatorsOutput.accel = snapshot.accel
  co.actuatorsOutput.brake = snapshot.brake
  co.actuatorsOutputValid = True
  co.canMonoTime = timestamp_ns
  pm.send("carOutput", co_msg)

  cs_msg = messaging.new_message("carState")
  cs_msg.valid = True
  cs = cs_msg.carState
  cs.vEgo = snapshot.speed
  cs.vEgoRaw = snapshot.speed
  cs.aEgo = snapshot.accel_estimate
  cs.standstill = snapshot.speed < 0.1
  cs.steeringAngleDeg = snapshot.steering_angle_deg
  cs.steeringRateDeg = snapshot.steer_rate
  cs.gearShifter = GearShifter.drive
  cs.canValid = True
  cs.gas = max(snapshot.accel, 0.0)
  cs.brake = snapshot.brake
  cs.cruiseState.enabled = True
  cs.cruiseState.available = True
  cs.cruiseState.speed = snapshot.speed * 3.6
  cs.cruiseState.standstill = cs.standstill
  pm.send("carState", cs_msg)

  cam_msg = messaging.new_message("roadCameraState")
  cam = cam_msg.roadCameraState
  cam.frameId = frame_id
  cam.frameIdSensor = frame_id
  cam.requestId = frame_id
  cam.encodeId = frame_id
  cam.timestampSof = timestamp_ns
  cam.timestampEof = timestamp_ns
  cam.processingTime = snapshot.processing_time_s
  cam.exposureValPercent = snapshot.exposure_percent
  cam.integLines = 0
  cam.gain = 1.0
  cam.measuredGreyFraction = float(np.clip(0.5 + snapshot.center_offset * 0.1, 0.0, 1.0))
  cam.targetGreyFraction = 0.5
  cam.sensor = ImageSensor.unknown
  cam.temperaturesC = [snapshot.camera_temp_c]
  cam.transform = []
  cam.image = b""
  pm.send("roadCameraState", cam_msg)

  device_msg = messaging.new_message("deviceState")
  device = device_msg.deviceState
  device.started = True
  device.startedMonoTime = timestamp_ns
  device.freeSpacePercent = 80.0
  device.memoryUsagePercent = 35
  device.cpuUsagePercent = [18, 16, 14, 17]
  device.networkType = NetworkType.ethernet
  device.networkStrength = NetworkStrength.great
  device.networkMetered = False
  device.lastAthenaPingTime = timestamp_ns
  device.maxTempC = snapshot.camera_temp_c
  device.cpuTempC = [snapshot.camera_temp_c]
  device.gpuTempC = [max(snapshot.camera_temp_c - 2.0, 20.0)]
  device.dspTempC = snapshot.camera_temp_c
  device.memoryTempC = snapshot.camera_temp_c
  device.thermalStatus = ThermalStatus.green if snapshot.camera_temp_c < 55.0 else ThermalStatus.yellow
  device.fanSpeedPercentDesired = 0
  device.screenBrightnessPercent = 0
  device.powerDrawW = 35.0
  device.somPowerDrawW = 18.0
  device.networkInfo.technology = "USB Camera"
  device.networkInfo.operator = "openpilot-desktop"
  pm.send("deviceState", device_msg)


def csv_writer(path: Path) -> tuple[csv.DictWriter, object]:
  path.parent.mkdir(parents=True, exist_ok=True)
  file_exists = path.exists() and path.stat().st_size > 0
  csv_file = path.open("a", newline="")
  fieldnames = [
    "timestamp_ns",
    "frame_id",
    "steer",
    "steering_angle_deg",
    "steer_rate",
    "torque",
    "accel",
    "brake",
    "long_control_state",
    "speed_mps",
    "accel_mps2",
    "center_offset",
    "exposure_percent",
    "camera_temp_c",
  ]
  writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
  if not file_exists:
    writer.writeheader()
  return writer, csv_file


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Camera-only openpilot launcher with CSV actuator logging")
  parser.add_argument(
    "--camera",
    default=os.environ.get("OPENPILOT_CAMERA", "0"),
    help="Camera index or path to capture from (default: %(default)s)",
  )
  parser.add_argument(
    "--csv",
    type=Path,
    default=Path(os.environ.get("OPENPILOT_ACTUATOR_CSV", "./actuators.csv")),
    help="Where to store actuator samples as CSV (default: %(default)s)",
  )
  parser.add_argument(
    "--fps",
    type=float,
    default=20.0,
    help="Target control loop frequency in Hz (default: %(default)s)",
  )
  return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> int:
  if cv2 is None:
    print("opencv-python-headless is required to run the camera control loop", file=sys.stderr)
    print(f"Import error: {_cv2_import_error}", file=sys.stderr)
    return 2

  args = parse_args(argv)

  try:
    camera_target = resolve_camera(str(args.camera))
  except ValueError as exc:
    print(f"Invalid camera target: {exc}", file=sys.stderr)
    return 2

  cap = cv2.VideoCapture(camera_target, cv2.CAP_ANY)
  if not cap or not cap.isOpened():
    print(f"Unable to open camera '{args.camera}'. Ensure it is connected and not in use.", file=sys.stderr)
    return 1

  cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)

  pm = messaging.PubMaster(["carControl", "carOutput", "carState", "roadCameraState", "deviceState"])
  csv_path = args.csv.expanduser().resolve()
  writer, csv_file = csv_writer(csv_path)

  stop = False

  def _handle_signal(signum: int, _frame: Optional[object]) -> None:
    nonlocal stop
    stop = True

  signal.signal(signal.SIGINT, _handle_signal)
  signal.signal(signal.SIGTERM, _handle_signal)

  frame_id = 0
  prev_angle = 0.0
  speed = 0.0
  last_time = time.monotonic()
  target_interval = 0.0 if args.fps <= 0 else 1.0 / args.fps

  print(f"Starting camera-only openpilot loop on '{args.camera}' -> logging to {csv_path}")
  try:
    while not stop:
      ret, frame = cap.read()
      if not ret:
        time.sleep(0.01)
        continue

      now = time.monotonic()
      dt = now - last_time
      last_time = now
      if dt <= 0:
        dt = 1.0 / max(args.fps, 20.0)

      snapshot = compute_actuator_snapshot(frame, prev_angle, speed, dt)
      prev_angle = snapshot.steering_angle_deg
      speed = snapshot.speed
      timestamp_ns = time.time_ns()
      frame_id += 1

      publish_messages(pm, snapshot, frame_id, timestamp_ns)

      writer.writerow({
        "timestamp_ns": timestamp_ns,
        "frame_id": frame_id,
        "steer": snapshot.steer,
        "steering_angle_deg": snapshot.steering_angle_deg,
        "steer_rate": snapshot.steer_rate,
        "torque": snapshot.torque,
        "accel": snapshot.accel,
        "brake": snapshot.brake,
        "long_control_state": LONG_STATE_LABELS.get(snapshot.long_control_state, snapshot.long_control_state),
        "speed_mps": snapshot.speed,
        "accel_mps2": snapshot.accel_estimate,
        "center_offset": snapshot.center_offset,
        "exposure_percent": snapshot.exposure_percent,
        "camera_temp_c": snapshot.camera_temp_c,
      })
      csv_file.flush()

      if target_interval > 0:
        sleep_time = target_interval - (time.monotonic() - now)
        if sleep_time > 0:
          time.sleep(sleep_time)
  finally:
    cap.release()
    csv_file.close()

  print("Camera loop stopped. Actuator samples saved to", csv_path)
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
