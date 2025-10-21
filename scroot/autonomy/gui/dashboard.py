"""PyQt-based dashboard for operating the scooter autonomy stack."""

from __future__ import annotations

import logging
import subprocess
import sys
import time
from pathlib import Path
from queue import Empty, Queue
from typing import Optional

import cv2
import numpy as np
from PyQt6 import QtCore, QtGui, QtWidgets

from autonomy.pilot import AutonomyPilot, PilotConfig
from autonomy.utils.data_structures import PilotSnapshot


LOGGER = logging.getLogger(__name__)


class SignalLogHandler(logging.Handler):
    """Logging handler that forwards log records to a Qt signal."""

    def __init__(self, signal: QtCore.pyqtSignal) -> None:  # type: ignore[assignment]
        super().__init__()
        self._signal = signal

    def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover - GUI side effect
        message = self.format(record)
        self._signal.emit(message)


class PilotWorker(QtCore.QObject):
    """Runs the autonomy pilot on a background thread."""

    snapshot_ready = QtCore.pyqtSignal(object)
    actuator_ready = QtCore.pyqtSignal(float, float, float)
    log_ready = QtCore.pyqtSignal(str)
    status_changed = QtCore.pyqtSignal(str)
    command_ack = QtCore.pyqtSignal(str)
    finished = QtCore.pyqtSignal()

    def __init__(self, config: PilotConfig) -> None:
        super().__init__()
        self._config = config
        self._mutex = QtCore.QMutex()
        self._stop_requested = False
        self._command_queue: Queue[str] = Queue()
        self._pilot: Optional[AutonomyPilot] = None
        self._log_handler: Optional[SignalLogHandler] = None

    @QtCore.pyqtSlot()
    def run(self) -> None:  # pragma: no cover - requires runtime environment
        root_logger = logging.getLogger()
        self._log_handler = SignalLogHandler(self.log_ready)
        self._log_handler.setLevel(logging.INFO)
        root_logger.addHandler(self._log_handler)
        root_logger.setLevel(logging.INFO)

        try:
            self.status_changed.emit("starting")
            self._pilot = AutonomyPilot(self._config)
            self.status_changed.emit("running")
            self._drain_command_queue()

            for command in self._pilot.run():
                if self._should_stop():
                    break

                snapshot = self._pilot.latest_snapshot
                if snapshot:
                    self.snapshot_ready.emit(snapshot)
                self.actuator_ready.emit(command.steer, command.throttle, command.brake)

                self._drain_command_queue()

            self.status_changed.emit("stopped")
        except Exception as exc:  # pragma: no cover - propagated to GUI
            LOGGER.exception("Pilot worker encountered an error")
            self.log_ready.emit(f"[error] {exc}")
            self.status_changed.emit("error")
        finally:
            if self._pilot:
                self._pilot.stop()
            if self._log_handler:
                root_logger.removeHandler(self._log_handler)
            self.finished.emit()

    @QtCore.pyqtSlot()
    def stop(self) -> None:  # pragma: no cover - requires runtime environment
        with QtCore.QMutexLocker(self._mutex):
            self._stop_requested = True
        if self._pilot:
            self._pilot.stop()

    @QtCore.pyqtSlot(str)
    def submit_command(self, text: str) -> None:
        self._command_queue.put(text)

    def _should_stop(self) -> bool:
        with QtCore.QMutexLocker(self._mutex):
            return self._stop_requested

    def _drain_command_queue(self) -> None:
        if not self._pilot:
            return

        while True:
            try:
                text = self._command_queue.get_nowait()
            except Empty:
                break

            command = self._pilot.submit_command(text)
            if command is not None:
                summary = f"{command.command_type}: {command.raw_text}"
            else:
                summary = "Command ignored (interface disabled)"
            self.command_ack.emit(summary)


class SetupWorker(QtCore.QObject):
    """Runs setup_scroot.py in a background process."""

    log_ready = QtCore.pyqtSignal(str)
    finished = QtCore.pyqtSignal(bool)

    def __init__(self, script_path: Path) -> None:
        super().__init__()
        self._script_path = script_path

    @QtCore.pyqtSlot()
    def run(self) -> None:  # pragma: no cover - requires runtime environment
        try:
            process = subprocess.Popen(
                [sys.executable, str(self._script_path)],
                cwd=str(self._script_path.parent),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except OSError as exc:
            self.log_ready.emit(f"[setup:error] {exc}")
            self.finished.emit(False)
            return

        success = True
        assert process.stdout is not None
        for line in process.stdout:
            self.log_ready.emit(line.rstrip())
        exit_code = process.wait()
        if exit_code != 0:
            success = False
            self.log_ready.emit(f"[setup] exited with code {exit_code}")
        self.finished.emit(success)


def draw_overlay(snapshot: PilotSnapshot) -> np.ndarray:
    frame = snapshot.frame.copy()
    height, width = frame.shape[:2]
    center_x = width // 2
    center_y = height // 2

    cv2.line(frame, (center_x, 0), (center_x, height), (0, 255, 0), 1)
    cv2.line(frame, (0, center_y), (width, center_y), (0, 255, 0), 1)

    steer_offset = int(snapshot.command.steer * (width / 2.0))
    cv2.line(frame, (center_x + steer_offset, 0), (center_x + steer_offset, height), (0, 0, 255), 2)

    bar_height = int(height * 0.35)
    base_y = height - 30

    throttle = np.clip(snapshot.command.throttle, 0.0, 1.0)
    brake = np.clip(snapshot.command.brake, 0.0, 1.0)

    throttle_pixels = int(bar_height * throttle)
    brake_pixels = int(bar_height * brake)

    throttle_rect = (40, base_y - throttle_pixels, 80, base_y)
    brake_rect = (width - 80, base_y - brake_pixels, width - 40, base_y)

    cv2.rectangle(frame, (throttle_rect[0], throttle_rect[1]), (throttle_rect[2], throttle_rect[3]), (0, 200, 0), -1)
    cv2.rectangle(frame, (brake_rect[0], brake_rect[1]), (brake_rect[2], brake_rect[3]), (0, 0, 200), -1)

    directive = snapshot.decision.directive or "hold lane"
    caption = snapshot.decision.caption or ""
    goal = snapshot.decision.goal_context or ""

    overlay_lines = [
        f"directive: {directive}",
        f"speed: {snapshot.decision.desired_speed:.2f} m/s",
        f"hazard: {snapshot.decision.hazard_level:.2f}",
    ]
    if goal:
        overlay_lines.append(f"goal: {goal}")
    if caption:
        overlay_lines.append(f"advisor: {caption}")

    for index, text in enumerate(overlay_lines):
        cv2.putText(
            frame,
            text,
            (20, 40 + 30 * index),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2,
        )

    return frame


def to_qimage(frame: np.ndarray) -> QtGui.QImage:
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    height, width, channel = rgb_frame.shape
    bytes_per_line = channel * width
    image = QtGui.QImage(
        rgb_frame.data,
        width,
        height,
        bytes_per_line,
        QtGui.QImage.Format.Format_RGB888,
    )
    return image.copy()


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Scooter Autonomy Dashboard")
        self.resize(1280, 800)

        self._pilot_thread: Optional[QtCore.QThread] = None
        self._pilot_worker: Optional[PilotWorker] = None
        self._setup_thread: Optional[QtCore.QThread] = None
        self._setup_worker: Optional[SetupWorker] = None

        self._build_ui()

    def _build_ui(self) -> None:
        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central)

        self.video_label = QtWidgets.QLabel("Video feed will appear here once running")
        self.video_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.video_label.setMinimumHeight(360)
        layout.addWidget(self.video_label)

        actuator_layout = QtWidgets.QHBoxLayout()
        self.steer_value = QtWidgets.QLabel("Steer: 0.00")
        self.throttle_value = QtWidgets.QLabel("Throttle: 0.00")
        self.brake_value = QtWidgets.QLabel("Brake: 0.00")
        actuator_layout.addWidget(self.steer_value)
        actuator_layout.addWidget(self.throttle_value)
        actuator_layout.addWidget(self.brake_value)
        actuator_layout.addStretch()
        layout.addLayout(actuator_layout)

        control_layout = QtWidgets.QHBoxLayout()
        self.setup_button = QtWidgets.QPushButton("Run Setup")
        self.start_button = QtWidgets.QPushButton("Start Autonomy")
        self.stop_button = QtWidgets.QPushButton("Stop Autonomy")
        self.stop_button.setEnabled(False)
        control_layout.addWidget(self.setup_button)
        control_layout.addWidget(self.start_button)
        control_layout.addWidget(self.stop_button)
        control_layout.addStretch()
        self.status_label = QtWidgets.QLabel("Status: idle")
        control_layout.addWidget(self.status_label)
        layout.addLayout(control_layout)

        config_layout = QtWidgets.QHBoxLayout()
        config_layout.addWidget(QtWidgets.QLabel("Camera:"))
        self.camera_input = QtWidgets.QLineEdit(str(PilotConfig().camera_source))
        config_layout.addWidget(self.camera_input)
        config_layout.addWidget(QtWidgets.QLabel("Model:"))
        self.model_input = QtWidgets.QLineEdit(PilotConfig().model_name)
        config_layout.addWidget(self.model_input)
        layout.addLayout(config_layout)

        command_layout = QtWidgets.QHBoxLayout()
        self.command_input = QtWidgets.QLineEdit()
        self.command_input.setPlaceholderText("e.g. drive to the park, stop, or turn right")
        self.command_button = QtWidgets.QPushButton("Send Command")
        command_layout.addWidget(self.command_input)
        command_layout.addWidget(self.command_button)
        layout.addLayout(command_layout)

        self.log_output = QtWidgets.QPlainTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output, 1)

        self.command_history = QtWidgets.QLabel("Last command: none")
        layout.addWidget(self.command_history)

        self.setCentralWidget(central)

        self.setup_button.clicked.connect(self._run_setup)
        self.start_button.clicked.connect(self._start_autonomy)
        self.stop_button.clicked.connect(self._stop_autonomy)
        self.command_button.clicked.connect(self._send_command)
        self.command_input.returnPressed.connect(self._send_command)

    def _append_log(self, text: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        self.log_output.appendPlainText(f"[{timestamp}] {text}")
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum())

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # pragma: no cover - GUI interaction
        if self._pilot_worker:
            self._pilot_worker.stop()
        if self._pilot_thread:
            self._pilot_thread.quit()
            self._pilot_thread.wait(2000)
        if self._setup_thread:
            self._setup_thread.quit()
            self._setup_thread.wait(2000)
        super().closeEvent(event)

    def _run_setup(self) -> None:
        if self._setup_thread and self._setup_thread.isRunning():
            return

        script_path = Path(__file__).resolve().parents[2] / "setup_scroot.py"
        self._setup_worker = SetupWorker(script_path)
        self._setup_thread = QtCore.QThread()
        self._setup_worker.moveToThread(self._setup_thread)
        self._setup_thread.started.connect(self._setup_worker.run)
        self._setup_worker.log_ready.connect(self._append_log)
        self._setup_worker.finished.connect(self._on_setup_finished)
        self._setup_worker.finished.connect(self._setup_thread.quit)
        self._setup_worker.finished.connect(self._setup_worker.deleteLater)
        self._setup_thread.finished.connect(self._setup_thread.deleteLater)
        self._setup_thread.start()
        self.setup_button.setEnabled(False)
        self._append_log("Setup started...")

    def _on_setup_finished(self, success: bool) -> None:
        state = "completed" if success else "failed"
        self._append_log(f"Setup {state}.")
        self.setup_button.setEnabled(True)

    def _start_autonomy(self) -> None:
        if self._pilot_thread and self._pilot_thread.isRunning():
            return

        config = self._build_config()
        self._pilot_worker = PilotWorker(config)
        self._pilot_thread = QtCore.QThread()
        self._pilot_worker.moveToThread(self._pilot_thread)
        self._pilot_thread.started.connect(self._pilot_worker.run)
        self._pilot_worker.snapshot_ready.connect(self._update_snapshot)
        self._pilot_worker.actuator_ready.connect(self._update_actuators)
        self._pilot_worker.log_ready.connect(self._append_log)
        self._pilot_worker.status_changed.connect(self._update_status)
        self._pilot_worker.command_ack.connect(self._update_command_history)
        self._pilot_worker.finished.connect(self._on_pilot_finished)
        self._pilot_worker.finished.connect(self._pilot_thread.quit)
        self._pilot_worker.finished.connect(self._pilot_worker.deleteLater)
        self._pilot_thread.finished.connect(self._pilot_thread.deleteLater)
        self._pilot_thread.start()

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self._append_log("Autonomy starting...")

    def _stop_autonomy(self) -> None:
        if self._pilot_worker:
            self._pilot_worker.stop()
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self._append_log("Autonomy stop requested")

    def _on_pilot_finished(self) -> None:
        self._append_log("Autonomy stopped")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self._pilot_worker = None
        self._pilot_thread = None

    def _send_command(self) -> None:
        text = self.command_input.text().strip()
        if not text:
            return

        if self._pilot_worker:
            self._pilot_worker.submit_command(text)
            self._append_log(f"Queued command: {text}")
        else:
            self._append_log("Cannot send command: autonomy not running")
        self.command_input.clear()

    def _build_config(self) -> PilotConfig:
        base = PilotConfig()

        camera_text = self.camera_input.text().strip()
        camera_source: int | str
        if camera_text.isdigit():
            camera_source = int(camera_text)
        else:
            camera_source = camera_text or base.camera_source

        model_name = self.model_input.text().strip() or base.model_name

        return PilotConfig(
            camera_source=camera_source,
            camera_width=base.camera_width,
            camera_height=base.camera_height,
            camera_fps=base.camera_fps,
            model_name=model_name,
            confidence_threshold=base.confidence_threshold,
            iou_threshold=base.iou_threshold,
            visualize=False,
            log_dir=base.log_dir,
            advisor_enabled=base.advisor_enabled,
            advisor_image_model=base.advisor_image_model,
            advisor_language_model=base.advisor_language_model,
            advisor_device=base.advisor_device,
            advisor_state_path=base.advisor_state_path,
            command_state_path=base.command_state_path,
        )

    def _update_snapshot(self, snapshot: PilotSnapshot) -> None:
        overlay = draw_overlay(snapshot)
        image = to_qimage(overlay)
        pixmap = QtGui.QPixmap.fromImage(image)
        self.video_label.setPixmap(pixmap.scaled(
            self.video_label.size(),
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        ))

    def _update_actuators(self, steer: float, throttle: float, brake: float) -> None:
        self.steer_value.setText(f"Steer: {steer:+.2f}")
        self.throttle_value.setText(f"Throttle: {throttle:.2f}")
        self.brake_value.setText(f"Brake: {brake:.2f}")

    def _update_status(self, status: str) -> None:
        self.status_label.setText(f"Status: {status}")

    def _update_command_history(self, text: str) -> None:
        self.command_history.setText(f"Last command: {text}")


def launch_dashboard() -> None:  # pragma: no cover - requires runtime environment
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("Scooter Autonomy Dashboard")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":  # pragma: no cover
    launch_dashboard()
