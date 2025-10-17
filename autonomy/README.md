# Autonomous Scooter Pilot

This package contains a self-contained autonomous driving stack tailored for lightweight vehicles such as scooters. The system is designed to run on NVIDIA Jetson devices as well as standard Ubuntu 24.04 laptops, using a single USB camera for perception. It exposes raw actuator values (`steer`, `throttle`, `brake`) that you can feed directly into your hardware interface.

## Features

- Camera ingestion pipeline compatible with any USB camera supported by OpenCV.
- Real-time object detection powered by Ultralytics YOLO models (default: `yolov8n.pt`).
- Heuristic navigator that prioritizes bike lanes and sidewalks by avoiding dense obstacle regions.
- Safety-aware control layer that outputs normalized actuator commands and aggressively brakes for imminent hazards.
- Optional visualization overlay for debugging perception and control decisions.
- Modular design that allows future sensors (ultrasonic, LiDAR, depth) to feed into the navigator without architectural changes.

## Quick Start

1. **Install dependencies** (Python 3.10+ recommended):

   ```bash
   python -m pip install --upgrade pip
   python -m pip install -r autonomy/requirements.txt
   ```

   On Jetson devices you may prefer the Jetson-specific OpenCV build. Adjust the requirement accordingly if you already have a hardware-accelerated package installed.

2. **Connect your camera** via USB and determine its index (usually `0`).

3. **Launch the pilot** using the unified launcher:

   ```bash
   python autonomy_launcher.py --camera 0 --visualize
   ```

   The launcher checks dependencies, starts the camera, runs perception and control, and prints actuator commands:

   ```text
   time=3.42s steer=+0.120 throttle=0.320 brake=0.000
   ```

   Press `q` in the visualization window or send `Ctrl+C` to exit.

## Configuration Options

The launcher accepts several runtime flags:

| Flag | Description | Default |
| --- | --- | --- |
| `--camera` | Camera index or video path | `0` |
| `--width` / `--height` | Capture resolution | `1280x720` |
| `--fps` | Target frame rate | `30` |
| `--model` | YOLO model file | `yolov8n.pt` |
| `--confidence` | Detection confidence threshold | `0.3` |
| `--iou` | Detection IoU threshold | `0.4` |
| `--visualize` | Enable on-screen overlays | Disabled |
| `--log-dir` | Directory for any future logs | `logs/` |

## How It Works

1. **CameraSensor** (`autonomy/sensors/camera.py`) continuously streams frames.
2. **ObjectDetector** (`autonomy/perception/object_detection.py`) identifies obstacles using YOLO and returns bounding boxes.
3. **Navigator** (`autonomy/planning/navigator.py`) evaluates obstacle density across left/center/right corridors to determine a steering bias and safe speed.
4. **Controller** (`autonomy/control/controller.py`) converts navigation goals into smoothed actuator commands, prioritizing braking when hazards are detected.
5. **AutonomyPilot** (`autonomy/pilot.py`) orchestrates these components and prints raw actuator values so you can interface with your vehicle controller.

The architecture favors clarity and extensibility. Adding additional sensors simply requires aggregating their readings into the navigator's obstacle metrics.

## Extending the System

- **Additional sensors:** Feed their obstacle cues into `Navigator.plan` by augmenting the occupancy map.
- **Custom models:** Provide a different YOLO checkpoint via `--model`. Jetson users may want to convert the model to TensorRT; you can still call `Navigator` and `Controller` with the resulting detections.
- **Vehicle integration:** Map the normalized actuator outputs to your scooter's control API. For example, scale `steer` to handlebar servo angles and translate `throttle`/`brake` to PWM duty cycles.

## Safety Notice

This codebase is intended for research and prototyping. Always test in a controlled environment, keep a human operator ready to take over, and comply with local regulations for sidewalk and bike-lane operation.
