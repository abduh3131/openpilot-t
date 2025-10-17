from __future__ import annotations

import time
from typing import Iterator, Optional

import cv2


class CameraSensor:
    """Wraps OpenCV capture with sensible defaults for autonomous operation."""

    def __init__(
        self,
        source: int | str = 0,
        width: int = 1280,
        height: int = 720,
        fps: int = 30,
        auto_reconnect: bool = True,
    ) -> None:
        self.source = source
        self.width = width
        self.height = height
        self.fps = fps
        self.auto_reconnect = auto_reconnect
        self._capture: Optional[cv2.VideoCapture] = None

    def _open(self) -> cv2.VideoCapture:
        capture = cv2.VideoCapture(self.source)
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        capture.set(cv2.CAP_PROP_FPS, self.fps)
        if not capture.isOpened():
            raise RuntimeError(f"Unable to open camera source {self.source}")
        return capture

    def frames(self) -> Iterator[tuple[bool, Optional[cv2.Mat]]]:
        frame_interval = 1.0 / float(self.fps)
        while True:
            if self._capture is None:
                self._capture = self._open()
            success, frame = self._capture.read()
            if not success:
                if not self.auto_reconnect:
                    yield success, None
                    break
                self._capture.release()
                self._capture = None
                time.sleep(0.1)
                continue
            yield success, frame
            time.sleep(frame_interval)

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None
