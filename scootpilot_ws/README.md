# ScootPilot

ScootPilot is a ROS 2 Humble autopilot stack tailored for sidewalk and bike-lane micromobility vehicles such as stand-up scooters. The stack runs fully on Linux laptops with a USB webcam and keyboard joystick while remaining Jetson-friendly for deployment on embedded hardware.

## Features
- Modular bringup that auto-detects available sensors and falls back to simulation stubs when hardware is absent.
- Perception pipeline with ONNXRuntime-based drivable-area segmentation, object detection, curb detection, and multi-sensor fusion producing safety-aware costmaps.
- Localization with wheel odometry / visual-inertial odometry fallback fused with IMU and GNSS in an EKF (`map -> odom -> base_link`).
- Global and local planning constrained to footways, sidewalks, shoulders, and cycleways. Dynamic behaviors (yield, slow, stop) keep operations conservative and legal.
- Control stack with pure pursuit lateral control and PID longitudinal control with jerk limiting, outputting normalized throttle, brake, and steer commands.
- Independent safety supervisor that monitors time-to-collision, drivable boundaries, and node heartbeats to trigger a latched emergency stop.
- PyQt6 operator GUI with live video, map view, status tiles, telemetry, and one-click E-stop.
- Lightweight 2-D kinematic simulator and rosbag replay harness for regression testing.

## Quickstart
```bash
cd scootpilot_ws
./setup.sh
./run_sim.sh
```
The GUI should open, displaying a simulated sidewalk scene. The virtual scooter will follow the planned path, slow for driveway zones, and stop for a scripted pedestrian without leaving the sidewalk mask.

## Repository Layout
```
scootpilot_ws/
  config/             # Sensor configs, planner/safety tuning, OSM map snippets
  models/             # Default ONNX models (toy but functional)
  maps/               # Example visualization assets
  src/                # ROS 2 packages (bringup, sensors, perception, etc.)
  tests/              # Pytest-based unit/integration tests
```

## Dependencies
All dependencies are installed by `setup.sh` and pinned for reproducibility:
- **APT**: `ros-humble-desktop`, `python3-rosdep`, `python3-vcstool`, `python3-colcon-common-extensions`, `ros-humble-navigation2`, `ros-humble-nav2-bringup`, `ros-humble-rmw-cyclonedds-cpp`, `libeigen3-dev`, `libyaml-cpp-dev`, `qtbase5-dev`, `libqt6svg6`, `libqt6widgets6`, `python3-pyqt6`, `python3-opencv`, `onnxruntime`, `ros-humble-diagnostic-updater`, `ros-humble-vision-msgs`, `ros-humble-rclpy`, `ros-humble-cv-bridge`.
- **PIP** (see `setup.sh`): `onnxruntime==1.17.0`, `onnx==1.15.0`, `numpy==1.26.4`, `scipy==1.11.4`, `opencv-python==4.9.0.80`, `pyyaml==6.0.1`, `networkx==3.2.1`, `matplotlib==3.8.2`, `pyqtgraph==0.13.3`, `shapely==2.0.3`, `rtree==1.2.0`, `pytest==7.4.4`, `pytest-asyncio==0.21.1`, `transforms3d==0.4.1`, `pyserial==3.5`, `psutil==5.9.7`.

> **Note:** Some APT packages may already be satisfied by the ROS 2 desktop install. The script safely ignores already-installed dependencies.

## Running with Real Hardware
1. Edit `config/sensors.example.yaml` to reflect your sensor suite. Each sensor can be set to `enabled: true/false`, with device-specific parameters (e.g., serial port, frame rate).
2. Launch the stack with GUI:
   ```bash
   ./run_gui.sh
   ```
3. Use the GUI to switch between `Teleop`, `Assisted`, and `Autonomy` modes. The E-stop button latches until you click `Reset`.

### Sensor Notes
- **Camera**: Standard UVC webcams auto-detected. If disconnected at runtime, the safety supervisor commands an E-stop and the GUI shows a fault banner.
- **LiDAR / Ultrasonics**: When hardware is absent, simulated ranges are generated for development. Drivers use non-blocking serial I/O to avoid hangs.
- **IMU / GNSS**: Parsed via simple ASCII protocols (NMEA/RTIMU). EKF continues with available data; the safety layer lowers speed and raises warnings when sensors degrade.

## Simulation Mode
`run_sim.sh` starts the headless simulator, synthesizing localization, perception masks, and objects. This mode is used for unit tests and CI smoke checks. Recorded rosbags placed under `data/bags/` are also supported via the GUI "Replay" control.

## Testing
Run all unit tests with:
```bash
cd scootpilot_ws
source install/setup.bash
pytest tests
```

## Logging
Logs are written to `~/.ros/log/scootpilot/` with rotation. The GUI can start/stop rosbag recording to `data/bags/`.

## Future Work
- Swap in higher-quality segmentation and detection ONNX models trained on sidewalk/bike-lane datasets.
- Add crosswalk detection and explicit pedestrian intent prediction.
- Integrate V2X messages (DSRC/C-V2X) for cooperative safety near intersections.
