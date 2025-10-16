from __future__ import annotations

import os
from typing import Any, Dict

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus
from rclpy.node import Node
from sensor_msgs.msg import Image

from .onnx_rt import OnnxRunner, load_inputs


class DrivableSegNode(Node):
    """Runs drivable-area segmentation and publishes mask + confidence."""

    def __init__(self, config: Dict[str, Any]) -> None:
        super().__init__('drivable_seg_node')
        seg_cfg = config.get('segmentation', {})
        model_path = seg_cfg.get('model_path', 'models/drivable_seg.onnx')
        if not os.path.isabs(model_path):
            root = os.environ.get('SCOOTPILOT_ROOT', os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            model_path = os.path.join(root, model_path)
        self._runner = OnnxRunner(model_path)
        self._mask_threshold = float(seg_cfg.get('mask_threshold', 0.5))
        self._smooth_kernel = int(seg_cfg.get('smooth_kernel', 5))
        self._min_confidence = float(seg_cfg.get('min_confidence', 0.2))
        self._bridge = CvBridge()
        self._mask_pub = self.create_publisher(Image, '/perception/drivable_mask', 10)
        self._confidence_pub = self.create_publisher(Image, '/perception/drivable_confidence', 10)
        self._diag_pub = self.create_publisher(DiagnosticArray, '/diagnostics', 10)
        self.create_subscription(Image, '/camera/image_raw', self._on_image, 10)
        self._last_stamp = None

    @classmethod
    def from_parameters(cls, node: Node) -> 'DrivableSegNode':
        params = node._parameters  # type: ignore[attr-defined]
        return cls(params or {})

    def _on_image(self, msg: Image) -> None:
        frame = self._bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        inputs = load_inputs(frame)
        result = self._runner.infer(inputs)
        output = next(iter(result.outputs.values()))
        if output.ndim == 4:
            mask_logits = output[0, 0]
        else:
            mask_logits = output.reshape(frame.shape[0], frame.shape[1])
        mask = cv2.resize(mask_logits, (frame.shape[1], frame.shape[0]))
        confidence = np.clip(mask, 0.0, 1.0)
        mask = (confidence > self._mask_threshold).astype(np.uint8) * 255
        kernel = np.ones((self._smooth_kernel, self._smooth_kernel), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        mask_msg = self._bridge.cv2_to_imgmsg(mask, encoding='mono8')
        mask_msg.header = msg.header
        self._mask_pub.publish(mask_msg)

        conf_vis = (confidence * 255).astype(np.uint8)
        conf_msg = self._bridge.cv2_to_imgmsg(conf_vis, encoding='mono8')
        conf_msg.header = msg.header
        self._confidence_pub.publish(conf_msg)

        status = DiagnosticStatus()
        status.name = 'drivable_seg'
        status.hardware_id = 'onnxruntime'
        status.level = DiagnosticStatus.OK
        status.message = 'OK'
        if confidence.mean() < self._min_confidence:
            status.level = DiagnosticStatus.WARN
            status.message = 'Low segmentation confidence'
        diag = DiagnosticArray()
        diag.header = msg.header
        diag.status = [status]
        self._diag_pub.publish(diag)
        self._last_stamp = msg.header.stamp


def main(args=None) -> None:
    rclpy.init(args=args)
    node = Node('drivable_seg_wrapper')
    config_param = node.declare_parameter('config_path', '').value
    config: Dict[str, Any] = {}
    if isinstance(config_param, str) and config_param:
        import yaml

        with open(config_param, 'r', encoding='utf-8') as handle:
            config = yaml.safe_load(handle)
    seg_node = DrivableSegNode(config)
    try:
        rclpy.spin(seg_node)
    except KeyboardInterrupt:
        pass
    finally:
        seg_node.destroy_node()
        rclpy.shutdown()
