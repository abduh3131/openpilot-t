from __future__ import annotations

import os
from typing import Dict

import numpy as np
import rclpy
from cv_bridge import CvBridge
from diagnostic_msgs.msg import DiagnosticArray
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import Bool, Float32MultiArray
from vision_msgs.msg import Detection2DArray

from .fence_guard import road_violation
from .heartbeat import HeartbeatMonitor
from .ttc_monitor import compute_ttc


class SafetySupervisor(Node):
    """Independent safety monitor with latched E-stop."""

    def __init__(self) -> None:
        super().__init__('safety_supervisor')
        self.declare_parameter('config_path', 'config/safety.yaml')
        config_path = self.get_parameter('config_path').get_parameter_value().string_value
        self._bridge = CvBridge()
        self._mask: np.ndarray | None = None
        self._detections: Detection2DArray | None = None
        self._speed = 0.0
        config = self._load_config(config_path)
        safety_cfg = config.get('safety', {})
        self._ttc_threshold = float(safety_cfg.get('ttc_threshold', 2.0))
        self._sensor_timeout = float(safety_cfg.get('sensor_timeout', 1.0))
        self._fence_margin = float(safety_cfg.get('fence_margin', 0.2))
        self._estop_latch = bool(safety_cfg.get('estop_latch', True))
        self._estop = False
        self._manual_estop = False
        self._estop_pub = self.create_publisher(Bool, '/safety/estop', 10)
        self.create_subscription(Detection2DArray, '/perception/objects', self._on_detections, 10)
        self.create_subscription(Float32MultiArray, '/control/raw', self._on_control, 10)
        self.create_subscription(DiagnosticArray, '/diagnostics', self._on_diagnostics, 10)
        self.create_subscription(Image, '/perception/drivable_mask', self._on_mask, 10)
        self.create_subscription(Bool, '/gui/estop', self._on_manual_estop, 10)
        self.create_subscription(Bool, '/gui/reset_estop', self._on_reset, 10)
        self.create_subscription(Bool, '/safety/manual_estop', self._on_manual_estop, 10)
        self.create_subscription(Bool, '/safety/clear_estop', self._on_reset, 10)
        self._heartbeat = HeartbeatMonitor(timeout=self._sensor_timeout)
        self._timer = self.create_timer(0.1, self._evaluate)

    def _load_config(self, path: str) -> Dict[str, Dict[str, float]]:
        import yaml

        if not os.path.isabs(path):
            root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            path = os.path.join(root, path)
        with open(path, 'r', encoding='utf-8') as handle:
            return yaml.safe_load(handle)

    def _on_mask(self, msg: Image) -> None:
        self._mask = self._bridge.imgmsg_to_cv2(msg, desired_encoding='mono8')
        self._heartbeat.ping('drivable_mask')

    def _on_detections(self, msg: Detection2DArray) -> None:
        self._detections = msg
        self._heartbeat.ping('perception')

    def _on_control(self, msg: Float32MultiArray) -> None:
        if msg.data:
            throttle = msg.data[0]
            brake = msg.data[1] if len(msg.data) > 1 else 0.0
            self._speed = max(0.0, throttle - brake) * 4.0
            self._heartbeat.ping('control')

    def _on_diagnostics(self, msg: DiagnosticArray) -> None:
        for status in msg.status:
            self._heartbeat.ping(status.name)

    def _on_manual_estop(self, msg: Bool) -> None:
        if msg.data:
            self._manual_estop = True
            self._estop = True
            self._publish_estop()

    def _on_reset(self, msg: Bool) -> None:
        if msg.data:
            self._manual_estop = False
            self._estop = False
            self._publish_estop()

    def _evaluate(self) -> None:
        statuses = self._heartbeat.check()
        if any(not alive for alive in statuses.values()):
            self._estop = True
        if self._detections is not None:
            distances = [max(0.1, det.bbox.center.position.y) for det in self._detections.detections]
            ttc_result = compute_ttc(distances, max(self._speed, 0.1), self._ttc_threshold)
            if ttc_result.hazardous:
                self._estop = True
        if self._mask is not None and road_violation(self._mask, margin=self._fence_margin):
            self._estop = True
        if self._manual_estop:
            self._estop = True
        self._publish_estop()

    def _publish_estop(self) -> None:
        msg = Bool()
        msg.data = self._estop
        self._estop_pub.publish(msg)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = SafetySupervisor()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
