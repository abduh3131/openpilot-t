# Autonomous Scooter Pilot

This package contains a self-contained autonomous driving stack tailored for lightweight vehicles such as scooters. The system is designed to run on NVIDIA Jetson devices as well as standard Ubuntu 24.04 laptops, using a single USB camera for perception. It exposes raw actuator values (`steer`, `throttle`, `brake`) that you can feed directly into your hardware interface. All commands below assume you are inside the `scroot` directory.

## Features

- Camera ingestion pipeline compatible with any USB camera supported by OpenCV.
- Real-time object detection powered by Ultralytics YOLO models (default: `yolov8n.pt`).
- Hybrid navigation that fuses obstacle density analysis with natural-language operator goals.
- Safety-aware control layer that outputs normalized actuator commands, brakes for hazards, and honors enforced stops.
- Optional multimodal advisor (BLIP + FLAN-T5) that captions the scene and issues traffic-law-compliant directives ("use the bike lane", "yield", "slow down").
- Command parser that understands phrases such as "drive to the plaza", "drive 2 m forward", or "turn right" and feeds them into the navigator.
- Structured state export (`logs/command_state.json`, `logs/advisor_state.json`) for telemetry, remote supervision, or UI dashboards.
- Modular design that allows future sensors (ultrasonic, LiDAR, depth) to feed into the navigator without architectural changes.

## Quick Start

1. **Install dependencies** (Python 3.10+ recommended):

   ```bash
   python -m pip install --upgrade pip
   python -m pip install -r autonomy/requirements.txt
   ```

   On Jetson devices you may prefer the Jetson-specific OpenCV or PyTorch builds. Adjust the requirement accordingly if you already have hardware-accelerated packages installed.

2. **Connect your camera** via USB and determine its index (usually `0`).

3. **Launch the pilot** using the unified launcher:

   ```bash
   python autonomy_launcher.py --camera 0 --visualize --command "drive 2 m forward"
   ```

   The launcher checks dependencies, starts the camera, runs perception and control, and prints actuator commands together with the advisor verdict:

   ```text
   time=3.42s steer=+0.120 throttle=0.320 brake=0.000 directive="stay in bike lane" goal="drive 2 m forward"
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
| `--log-dir` | Directory for visualizations and state dumps | `logs/` |
| `--command` | Initial natural-language goal (e.g. `"drive to the park"`) | None |
| `--command-file` | Path to a UTF-8 text file that can be updated with new commands | None |
| `--disable-advisor` | Skip loading the multimodal advisor | Enabled |
| `--advisor-image-model` | Hugging Face name for the BLIP image encoder | `Salesforce/blip-image-captioning-base` |
| `--advisor-language-model` | Hugging Face name for the language model | `google/flan-t5-small` |
| `--advisor-device` | Force the device used by the advisor (`cpu`, `cuda`, etc.) | Auto-detect |
| `--advisor-state` | JSON file capturing the latest advisor directive | `logs/advisor_state.json` |
| `--command-state` | JSON file capturing the parsed command | `logs/command_state.json` |

## How It Works

1. **CameraSensor** (`autonomy/sensors/camera.py`) continuously streams frames.
2. **ObjectDetector** (`autonomy/perception/object_detection.py`) identifies obstacles using YOLO and returns bounding boxes.
3. **CommandInterface** (`autonomy/ai/command_interface.py`) parses operator phrases and exposes structured goals.
4. **Navigator** (`autonomy/planning/navigator.py`) evaluates obstacle density and the active goal to produce a steering bias, target speed, and goal context.
5. **SituationalAdvisor** (`autonomy/ai/advisor.py`) captions the scene, blends detection metadata with the goal, and emits a short instruction; it can enforce a full stop for compliance events such as stop signs or pedestrians.
6. **Controller** (`autonomy/control/controller.py`) converts navigation decisions into smoothed actuator commands, prioritizing braking when hazards or enforced stops occur.
7. **AutonomyPilot** (`autonomy/pilot.py`) orchestrates these components, exports telemetry, and prints raw actuator values for integration with your vehicle controller.

## Command Interface Tips

- Update the file passed with `--command-file` to issue live instructions. Each save triggers a re-parse.
- Supported phrases include:
  - `drive 5 m forward`
  - `drive to the loading dock`
  - `turn around`
  - `turn left`
  - `stop`
- Any unrecognized text is still passed to the advisor so it can reason about free-form goals.

## Safety Advisor Behavior

The advisor enforces conservative behavior:

- Stops when YOLO detects `stop sign`, `traffic light`, `person`, or `bicycle` directly ahead.
- Prioritizes sidewalks or bike lanes in its textual guidance.
- Raises braking priority when the navigator reports a high hazard score (>0.85 by default).
- Exports human-readable directives and scene captions for auditing.

## Extending the System

- **Additional sensors:** Feed their obstacle cues into `Navigator.plan` by augmenting the occupancy map.
- **Custom models:** Provide a different YOLO checkpoint via `--model` or swap the advisor models with lighter or heavier variants.
- **Vehicle integration:** Map the normalized actuator outputs to your scooter's control API. For example, scale `steer` to handlebar servo angles and translate `throttle`/`brake` to PWM duty cycles.

## Safety Notice

This codebase is intended for research and prototyping. Always test in a controlled environment, keep a human operator ready to take over, and comply with local regulations for sidewalk and bike-lane operation.
