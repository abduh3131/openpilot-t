from __future__ import annotations

import json
import logging
import signal
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterator, Optional

import cv2
import numpy as np

from autonomy.ai.advisor import AdvisorConfig, SituationalAdvisor
from autonomy.ai.command_interface import CommandInterface
from autonomy.control.controller import Controller, ControllerConfig
from autonomy.perception.object_detection import ObjectDetector, ObjectDetectorConfig
from autonomy.planning.navigator import Navigator, NavigatorConfig
from autonomy.sensors.camera import CameraSensor
from autonomy.utils.data_structures import (
    ActuatorCommand,
    AdvisorDirective,
    HighLevelCommand,
    NavigationDecision,
    PerceptionSummary,
)


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
    advisor_enabled: bool = True
    advisor_image_model: str = "Salesforce/blip-image-captioning-base"
    advisor_language_model: str = "google/flan-t5-small"
    advisor_device: Optional[str] = None
    advisor_state_path: Optional[Path] = Path("logs/advisor_state.json")
    command_state_path: Optional[Path] = Path("logs/command_state.json")
    initial_command: Optional[str] = None
    command_file: Optional[Path] = None


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
        self._advisor = None
        if self.config.advisor_enabled:
            advisor_config = AdvisorConfig(
                image_model=self.config.advisor_image_model,
                language_model=self.config.advisor_language_model,
                device=self.config.advisor_device,
            )
            self._advisor = SituationalAdvisor(advisor_config)

        self._command_interface = CommandInterface(
            command_file=self.config.command_file,
            initial_command=self.config.initial_command,
        )
        self._running = False
        self._latest_decision: Optional[NavigationDecision] = None
        self._latest_directive: Optional[AdvisorDirective] = None

        if self.config.visualize or self.config.advisor_state_path or self.config.command_state_path:
            self.config.log_dir.mkdir(parents=True, exist_ok=True)

    @property
    def latest_decision(self) -> Optional[NavigationDecision]:
        return self._latest_decision

    @property
    def latest_directive(self) -> Optional[AdvisorDirective]:
        return self._latest_directive

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

            current_command: Optional[HighLevelCommand] = None
            if self._command_interface:
                current_command = self._command_interface.poll()

            perception_summary = self._detector.detect(frame)
            decision = self._navigator.plan(perception_summary.objects, perception_summary.frame_size, current_command)

            if current_command and current_command.command_type == "stop":
                decision = replace(decision, desired_speed=0.0, hazard_level=1.0, enforced_stop=True)

            advisor_directive: Optional[AdvisorDirective] = None
            if self._advisor:
                advisor_directive = self._advisor.analyze(frame, perception_summary, decision, current_command)
                decision = replace(
                    decision,
                    enforced_stop=decision.enforced_stop or advisor_directive.enforced_stop,
                    directive=advisor_directive.directive,
                    caption=advisor_directive.caption,
                )
                if advisor_directive.enforced_stop:
                    decision = replace(decision, desired_speed=0.0, hazard_level=1.0)

            command = self._controller.command(decision)

            self._latest_decision = decision
            self._latest_directive = advisor_directive

            if self.config.visualize:
                self._visualize(frame, perception_summary, decision, command)

            self._export_state(current_command, advisor_directive, decision)

            yield command

        self._camera.close()
        logging.info("Pilot loop terminated")

    def stop(self) -> None:
        self._running = False

    def _export_state(
        self,
        current_command: Optional[HighLevelCommand],
        advisor_directive: Optional[AdvisorDirective],
        decision: NavigationDecision,
    ) -> None:
        if self._command_interface and self.config.command_state_path:
            self._command_interface.export_state(self.config.command_state_path)

        if advisor_directive and self.config.advisor_state_path:
            payload = {
                "directive": advisor_directive.directive,
                "enforced_stop": advisor_directive.enforced_stop,
                "caption": advisor_directive.caption,
                "goal_context": decision.goal_context,
            }
            path = self.config.advisor_state_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _visualize(
        self,
        frame: np.ndarray,
        perception: PerceptionSummary,
        decision: NavigationDecision,
        command: ActuatorCommand,
    ) -> None:
        visual = frame.copy()
        visual = self._detector.draw_detections(visual, perception.objects)
        text_lines = [
            f"steer={command.steer:+.2f}",
            f"throttle={command.throttle:.2f}",
            f"brake={command.brake:.2f}",
        ]
        if decision.directive:
            text_lines.append(f"advisor: {decision.directive}")
        text_lines.append(f"goal: {decision.goal_context}")
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
            decision = pilot.latest_decision
            directive = decision.directive if decision else ""
            goal_context = decision.goal_context if decision else ""
            print(
                " ".join(
                    [
                        f"time={elapsed:.2f}s",
                        f"steer={command.steer:+.3f}",
                        f"throttle={command.throttle:.3f}",
                        f"brake={command.brake:.3f}",
                        f"directive=\"{directive}\"",
                        f"goal=\"{goal_context}\"",
                    ]
                ),
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
    parser.add_argument("--disable-advisor", action="store_true")
    parser.add_argument("--advisor-image-model", default="Salesforce/blip-image-captioning-base")
    parser.add_argument("--advisor-language-model", default="google/flan-t5-small")
    parser.add_argument("--advisor-device", default=None)
    parser.add_argument("--command", default=None, help="Initial natural language command")
    parser.add_argument("--command-file", default=None, help="Path to a file containing operator commands")
    parser.add_argument("--advisor-state", default="logs/advisor_state.json", help="Where to export advisor decisions")
    parser.add_argument("--command-state", default="logs/command_state.json", help="Where to export parsed commands")

    args = parser.parse_args(argv)

    command_file = Path(args.command_file).expanduser() if args.command_file else None
    advisor_state_path = Path(args.advisor_state).expanduser() if args.advisor_state else None
    command_state_path = Path(args.command_state).expanduser() if args.command_state else None

    return PilotConfig(
        camera_source=args.camera,
        camera_width=args.width,
        camera_height=args.height,
        camera_fps=args.fps,
        model_name=args.model,
        confidence_threshold=args.confidence,
        iou_threshold=args.iou,
        visualize=args.visualize,
        log_dir=Path(args.log_dir).expanduser(),
        advisor_enabled=not args.disable_advisor,
        advisor_image_model=args.advisor_image_model,
        advisor_language_model=args.advisor_language_model,
        advisor_device=args.advisor_device,
        advisor_state_path=advisor_state_path,
        command_state_path=command_state_path,
        initial_command=args.command,
        command_file=command_file,
    )


def main(argv: Optional[list[str]] = None) -> None:
    config = parse_args(argv)
    run_pilot(config)


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main(sys.argv[1:])
