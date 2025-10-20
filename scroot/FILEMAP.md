# scroot Folder Reference

This document walks through every artifact under `scroot/`, outlines how the pieces fit together, and explains the exact library versions the stack expects. Use it as a high-level map when onboarding new contributors or integrating the scooter pilot into a new platform.

## Top-Level Layout

| Path | Purpose |
| --- | --- |
| `README.md` | Operator-facing quick start guide for installing dependencies and launching the autonomy stack. |
| `REPORT.md` | Development report summarizing design decisions, testing status, and future work items. |
| `FILEMAP.md` | (This file) Complete description of modules, runtime flow, and dependency rationale. |
| `setup_scroot.py` | One-shot bootstrap script that creates a virtual environment, installs dependencies, and caches pretrained models. |
| `autonomy/` | Python package implementing sensing, perception, AI assistants, planning, control, and shared utilities. |
| `autonomy_launcher.py` | Single-entry launch script that wires CLI arguments into the `AutonomyPilot` orchestrator and performs dependency checks before boot. |

## Dependency Versions and Rationale

The stack is pinned to Python 3.10+ and depends on the following packages declared in `autonomy/requirements.txt`:

| Package | Minimum Version | Reason |
| --- | --- | --- |
| `ultralytics` | `>=8.1.0` | Provides YOLOv8 detector weights and runtime utilities with ONNX/TensorRT export compatibility for Jetson-class hardware. |
| `opencv-python` | `>=4.8.0` | Supplies camera capture, image resizing, and visualization primitives across desktop and Jetson builds. |
| `numpy` | `>=1.24.0` | Underpins numeric operations for occupancy map aggregation, filtering, and control smoothing. |
| `torch` | `>=2.1.0` | Required to execute YOLOv8 as well as the multimodal advisor (BLIP + FLAN) efficiently on CPU or CUDA. |
| `torchvision` | `>=0.16.0` | Bundles pre/post-processing transforms used by YOLO and image captioning models. |
| `transformers` | `>=4.37.0` | Loads Hugging Face language models (FLAN-T5) and multimodal pipelines for the situational advisor. |
| `accelerate` | `>=0.25.0` | Streamlines device placement and mixed-precision execution for the advisor on Jetson GPUs. |
| `sentencepiece` | `>=0.1.99` | Tokenizer dependency for FLAN-T5 language understanding. |
| `safetensors` | `>=0.3.1` | Speeds up secure model weight loading for BLIP/FLAN checkpoints. |

Jetson deployments can swap in vendor-optimized wheels as long as the versions meet or exceed these baselines.

## Python Package Structure (`autonomy/`)

The `autonomy` package is deliberately split into feature-oriented subpackages. Each module below can be tested or replaced independently.

### `autonomy/__init__.py`
Exports convenience imports so downstream code can instantiate `AutonomyPilot` and configuration dataclasses without deep module paths.

### `autonomy/pilot.py`
Central orchestrator that binds sensors, perception, navigation, advisor, and control. The `AutonomyPilot` class exposes a `run()` generator yielding raw `ActuatorCommand` tuples (`steer`, `throttle`, `brake`). It handles:
- Camera startup and graceful shutdown.
- Polling the natural-language `CommandInterface`.
- Passing frames through the `ObjectDetector` and `Navigator` to compute motion plans.
- Invoking the `SituationalAdvisor` to enrich decisions with traffic-law directives and emergency stops.
- Feeding `NavigationDecision` objects into the `Controller` for smoothing and actuator scaling.
- Persisting telemetry JSON and optional visualization overlays.

### `autonomy/sensors/camera.py`
Defines `CameraSensor`, a thin wrapper around OpenCV’s `VideoCapture` that exposes a frame iterator with resolution/FPS controls and lifecycle management tailored for USB cameras.

### `autonomy/perception/object_detection.py`
Wraps Ultralytics YOLO to produce `PerceptionSummary` objects containing detections, obstacle density metrics, and frame metadata. Configuration toggles allow adjusting model name, confidence, and IoU thresholds.

### `autonomy/ai/command_interface.py`
Parses human directives such as “drive 2 m forward” or “turn around” into structured `HighLevelCommand` dataclasses. Supports live updates via a watched text file, default commands, and exports of the latest parsed state.

### `autonomy/ai/advisor.py`
Implements the multimodal `SituationalAdvisor` that fuses YOLO detections with BLIP image captions and FLAN-T5 reasoning. It emits textual guidance (e.g., “use the bike lane”) and can set `enforced_stop` flags when detecting pedestrians, stop signs, or conflicting instructions.

### `autonomy/planning/navigator.py`
Holds the `Navigator`, which converts perception results and parsed commands into `NavigationDecision` outputs. Responsibilities include hazard scoring, speed targets, steering bias computation, and goal tracking for distance-based maneuvers.

### `autonomy/control/controller.py`
Translates navigation decisions into normalized actuator commands. Implements PID-style smoothing, braking prioritization during hazards or enforced stops, and ensures outputs stay within [-1, 1] bounds expected by downstream actuators.

### `autonomy/utils/data_structures.py`
Defines the shared dataclasses (`ActuatorCommand`, `PerceptionObject`, `NavigationDecision`, etc.) that flow between modules, ensuring type consistency and easy telemetry serialization.

### `autonomy/utils/filters.py`
Contains helper functions for exponential smoothing of speed/steering signals, reducing oscillations in tight spaces.

## Documentation Assets

- `README.md` – End-user instructions for setup, runtime arguments, and operating practices.
- `REPORT.md` – Engineering log describing implementation rationale, testing steps, and follow-on roadmap suggestions.
- `FILEMAP.md` – Detailed architectural reference (this document).

## Launcher (`autonomy_launcher.py`)
The single entry point for operators. Responsibilities:
- Validates Python package dependencies before importing the heavy modules, providing actionable error messages if something is missing.
- Parses CLI arguments for camera setup, YOLO configuration, advisor toggles, and logging destinations.
- Instantiates `AutonomyPilot` and iterates through its command generator, printing each actuator triple alongside advisor guidance for integration with low-level motor controllers.

## Data Flow Summary

1. `autonomy_launcher.py` constructs `AutonomyPilot` using CLI-specified configuration.
2. `CameraSensor` streams frames. `ObjectDetector` converts them into detection lists.
3. `CommandInterface` delivers the latest high-level goal (if any).
4. `Navigator` evaluates detections plus goals to produce steering/speed intents.
5. `SituationalAdvisor` (optional) analyzes frames and detections to append directives or trigger stops.
6. `Controller` generates final actuator outputs, which the launcher prints or forwards.
7. `AutonomyPilot` continuously exports JSON state for external monitoring and respects stop signals for safe shutdowns.

With this map, new engineers can trace any actuator value back to its upstream source and adjust modules without breaking the surrounding system.
