from __future__ import annotations

import logging
import signal
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

import cv2

from autonomy.control.controller import Controller, ControllerConfig
from autonomy.perception.object_detection import ObjectDetector, ObjectDetectorConfig
from autonomy.planning.navigator import Navigator, NavigatorConfig
from autonomy.sensors.camera import CameraSensor
from autonomy.utils.data_structures import ActuatorCommand, PerceptionSummary


@dataclass
class PilotConfig:
    camera_source: int | str = 0
    camera_width: int = 1280
    camera_height: int = 720
    camera_fps: int = 30
    model_name: str = "yolov8n.pt"
    confidence_threshold: float = 0.3
    iou_threshold: float = 0.4
    visualize: bool = False
    log_dir: Path = Path("logs")


class AutonomyPilot:
    """Main orchestrator tying together sensing, perception, planning, and control."""

    def __init__(self, config: PilotConfig | None = None) -> None:
        self.config = config or PilotConfig()
        self._camera = CameraSensor(
            source=self.config.camera_source,
            width=self.config.camera_width,
            height=self.config.camera_height,
            fps=self.config.camera_fps,
        )
        self._detector = ObjectDetector(
            ObjectDetectorConfig(
                model_name=self.config.model_name,
                confidence_threshold=self.config.confidence_threshold,
                iou_threshold=self.config.iou_threshold,
            )
        )
        self._navigator = Navigator(NavigatorConfig())
        self._controller = Controller(ControllerConfig())
        self._running = False

        if self.config.visualize:
            self.config.log_dir.mkdir(parents=True, exist_ok=True)

    def run(self) -> Iterator[ActuatorCommand]:
        logging.info("Starting autonomous pilot loop")
        self._running = True
        frame_iterator = self._camera.frames()
        for success, frame in frame_iterator:
            if not self._running:
                break
            if not success or frame is None:
                logging.warning("Failed to read frame from camera")
                continue

            perception_summary = self._detector.detect(frame)
            decision = self._navigator.plan(perception_summary.objects, perception_summary.frame_size)
            command = self._controller.command(decision)

            if self.config.visualize:
                self._visualize(frame, perception_summary, command)

            yield command

        self._camera.close()
        logging.info("Pilot loop terminated")

    def stop(self) -> None:
        self._running = False

    def _visualize(self, frame: np.ndarray, perception: PerceptionSummary, command: ActuatorCommand) -> None:
        visual = frame.copy()
        visual = self._detector.draw_detections(visual, perception.objects)
        text_lines = [
            f"steer={command.steer:+.2f}",
            f"throttle={command.throttle:.2f}",
            f"brake={command.brake:.2f}",
        ]
        for idx, text in enumerate(text_lines):
            cv2.putText(visual, text, (10, 30 + idx * 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        cv2.imshow("AutonomyPilot", visual)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            self.stop()


@contextmanager
def graceful_shutdown(pilot: AutonomyPilot):
    def handler(signum, frame):  # pragma: no cover - interacts with system signals
        logging.info("Received signal %s, shutting down", signum)
        pilot.stop()

    original = signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)
    try:
        yield
    finally:
        pilot.stop()
        signal.signal(signal.SIGINT, original)
        signal.signal(signal.SIGTERM, original)
        cv2.destroyAllWindows()


def run_pilot(config: PilotConfig) -> None:
    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s:%(name)s:%(message)s")
    pilot = AutonomyPilot(config)
    start_time = time.time()

    with graceful_shutdown(pilot):
        for command in pilot.run():
            elapsed = time.time() - start_time
            print(
                f"time={elapsed:.2f}s steer={command.steer:+.3f} throttle={command.throttle:.3f} brake={command.brake:.3f}",
                flush=True,
            )

    logging.info("Autonomy run complete")


def parse_args(argv: Optional[list[str]] = None) -> PilotConfig:
    import argparse

    parser = argparse.ArgumentParser(description="Autonomous scooter pilot")
    parser.add_argument("--camera", default=0, help="Camera source index or path")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--model", default="yolov8n.pt")
    parser.add_argument("--confidence", type=float, default=0.3)
    parser.add_argument("--iou", type=float, default=0.4)
    parser.add_argument("--visualize", action="store_true")
    parser.add_argument("--log-dir", default="logs")

    args = parser.parse_args(argv)

    return PilotConfig(
        camera_source=args.camera,
        camera_width=args.width,
        camera_height=args.height,
        camera_fps=args.fps,
        model_name=args.model,
        confidence_threshold=args.confidence,
        iou_threshold=args.iou,
        visualize=args.visualize,
        log_dir=Path(args.log_dir),
    )


def main(argv: Optional[list[str]] = None) -> None:
    config = parse_args(argv)
    run_pilot(config)


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main(sys.argv[1:])
