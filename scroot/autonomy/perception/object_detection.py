from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

import cv2
import numpy as np

try:
    from ultralytics import YOLO
except ImportError as exc:  # pragma: no cover - handled at runtime
    raise ImportError(
        "The 'ultralytics' package is required for object detection. Install it with 'pip install ultralytics'."
    ) from exc

from autonomy.utils.data_structures import DetectedObject, PerceptionSummary


@dataclass
class ObjectDetectorConfig:
    model_name: str = "yolov8n.pt"
    confidence_threshold: float = 0.3
    iou_threshold: float = 0.4


class ObjectDetector:
    """Thin wrapper around the Ultralytics YOLO models."""

    def __init__(self, config: ObjectDetectorConfig | None = None) -> None:
        self.config = config or ObjectDetectorConfig()
        self._model = YOLO(self.config.model_name)
        self._model.fuse()

    def detect(self, frame: np.ndarray) -> PerceptionSummary:
        results = self._model.predict(
            source=frame,
            conf=self.config.confidence_threshold,
            iou=self.config.iou_threshold,
            verbose=False,
        )[0]

        detections: List[DetectedObject] = []
        names = self._model.names

        for box in results.boxes:
            cls_idx = int(box.cls.item())
            conf = float(box.conf.item())
            xyxy = box.xyxy[0].tolist()
            x_min, y_min, x_max, y_max = xyxy
            area = float((x_max - x_min) * (y_max - y_min))
            detections.append(
                DetectedObject(
                    label=str(names.get(cls_idx, cls_idx)),
                    confidence=conf,
                    bbox=(x_min, y_min, x_max, y_max),
                    area=area,
                )
            )

        return PerceptionSummary(objects=detections, frame_size=(frame.shape[1], frame.shape[0]))

    @staticmethod
    def draw_detections(frame: np.ndarray, detections: Iterable[DetectedObject]) -> np.ndarray:
        visual = frame.copy()
        for detection in detections:
            x_min, y_min, x_max, y_max = map(int, detection.bbox)
            cv2.rectangle(visual, (x_min, y_min), (x_max, y_max), (0, 255, 0), 2)
            label = f"{detection.label}:{detection.confidence:.2f}"
            cv2.putText(visual, label, (x_min, max(20, y_min - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
        return visual
