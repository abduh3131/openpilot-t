from __future__ import annotations

import os
from typing import Any, Dict, List

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus
from rclpy.node import Node
from sensor_msgs.msg import Image
from vision_msgs.msg import Detection2D, Detection2DArray, ObjectHypothesisWithPose

from .onnx_rt import OnnxRunner, load_inputs

CLASSES = ['person', 'bicycle', 'car', 'dog', 'cone']


def _nms(boxes: np.ndarray, scores: np.ndarray, iou_thresh: float) -> List[int]:
    idxs = scores.argsort()[::-1]
    keep: List[int] = []
    while idxs.size > 0:
        current = idxs[0]
        keep.append(current)
        if idxs.size == 1:
            break
        ious = _iou(boxes[current], boxes[idxs[1:]])
        idxs = idxs[1:][ious < iou_thresh]
    return keep


def _iou(box: np.ndarray, others: np.ndarray) -> np.ndarray:
    x1 = np.maximum(box[0], others[:, 0])
    y1 = np.maximum(box[1], others[:, 1])
    x2 = np.minimum(box[2], others[:, 2])
    y2 = np.minimum(box[3], others[:, 3])
    inter = np.maximum(0.0, x2 - x1) * np.maximum(0.0, y2 - y1)
    box_area = (box[2] - box[0]) * (box[3] - box[1])
    other_area = (others[:, 2] - others[:, 0]) * (others[:, 3] - others[:, 1])
    union = box_area + other_area - inter
    with np.errstate(divide='ignore', invalid='ignore'):
        return np.where(union > 0, inter / union, 0.0)


class ObjectDetNode(Node):
    """ONNX object detector with deterministic fallback outputs."""

    def __init__(self, config: Dict[str, Any]) -> None:
        super().__init__('object_detector')
        det_cfg = config.get('object_detection', {})
        model_path = det_cfg.get('model_path', 'models/object_det.onnx')
        if not os.path.isabs(model_path):
            root = os.environ.get('SCOOTPILOT_ROOT', os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            model_path = os.path.join(root, model_path)
        self._runner = OnnxRunner(model_path)
        self._score_threshold = float(det_cfg.get('score_threshold', 0.3))
        self._nms_iou = float(det_cfg.get('nms_iou', 0.45))
        self._bridge = CvBridge()
        self._diag_pub = self.create_publisher(DiagnosticArray, '/diagnostics', 10)
        self._publisher = self.create_publisher(Detection2DArray, '/perception/objects', 10)
        self.create_subscription(Image, '/camera/image_raw', self._on_image, 10)

    def _on_image(self, msg: Image) -> None:
        frame = self._bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        inputs = load_inputs(frame)
        result = self._runner.infer(inputs)
        raw = next(iter(result.outputs.values()))
        # Interpret the output as anchors: (N, classes+4)
        detections = []
        if raw.ndim == 3:
            raw = raw[0]
        if raw.ndim == 2:
            for row in raw:
                scores = row[: len(CLASSES)]
                bbox = row[len(CLASSES): len(CLASSES) + 4]
                label_idx = int(np.argmax(scores))
                score = float(scores[label_idx])
                if score < self._score_threshold:
                    continue
                x_center, y_center, width, height = bbox
                # Normalized coords in [0,1]
                w = float(width * frame.shape[1])
                h = float(height * frame.shape[0])
                x = float(x_center * frame.shape[1] - w / 2.0)
                y = float(y_center * frame.shape[0] - h / 2.0)
                detections.append((label_idx, score, np.array([x, y, x + w, y + h])))
        if detections:
            boxes = np.stack([d[2] for d in detections])
            scores = np.array([d[1] for d in detections])
            keep = _nms(boxes, scores, self._nms_iou)
        else:
            keep = []
        array_msg = Detection2DArray()
        array_msg.header = msg.header
        for idx in keep:
            label_idx, score, box = detections[idx]
            detection = Detection2D()
            detection.header = msg.header
            hypothesis = ObjectHypothesisWithPose()
            hypothesis.hypothesis.class_id = CLASSES[label_idx]
            hypothesis.hypothesis.score = score
            detection.results.append(hypothesis)
            detection.bbox.center.position.x = (box[0] + box[2]) / 2.0
            detection.bbox.center.position.y = (box[1] + box[3]) / 2.0
            detection.bbox.size_x = max(1.0, box[2] - box[0])
            detection.bbox.size_y = max(1.0, box[3] - box[1])
            array_msg.detections.append(detection)
        self._publisher.publish(array_msg)

        status = DiagnosticStatus()
        status.name = 'object_detection'
        status.hardware_id = 'onnxruntime'
        status.level = DiagnosticStatus.OK
        status.message = f'{len(array_msg.detections)} detections'
        diag = DiagnosticArray()
        diag.header = msg.header
        diag.status = [status]
        self._diag_pub.publish(diag)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = Node('object_det_wrapper')
    config_param = node.declare_parameter('config_path', '').value
    config: Dict[str, Any] = {}
    if isinstance(config_param, str) and config_param:
        import yaml

        with open(config_param, 'r', encoding='utf-8') as handle:
            config = yaml.safe_load(handle)
    det_node = ObjectDetNode(config)
    try:
        rclpy.spin(det_node)
    except KeyboardInterrupt:
        pass
    finally:
        det_node.destroy_node()
        rclpy.shutdown()
