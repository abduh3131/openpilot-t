from __future__ import annotations

import time
from typing import Optional, Tuple

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus
from rclpy.node import Node
from sensor_msgs.msg import Image


class CameraNode(Node):
    """UVC camera driver with deterministic synthetic fallback."""

    def __init__(self) -> None:
        super().__init__('camera_driver')
        self.declare_parameter('device', '/dev/video0')
        self.declare_parameter('frame_rate', 15)
        self.declare_parameter('resolution', [640, 480])
        self.declare_parameter('mode', 'color')
        device = self.get_parameter('device').get_parameter_value().string_value
        self._frame_period = 1.0 / float(self.get_parameter('frame_rate').value)
        width, height = self._parse_resolution()
        self._bridge = CvBridge()
        self._capture: Optional[cv2.VideoCapture] = None
        self._last_ok = True

        if cv2.getBuildInformation():
            cap = cv2.VideoCapture(device)
            if cap is not None and cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                cap.set(cv2.CAP_PROP_FPS, 1.0 / self._frame_period)
                self._capture = cap
                self.get_logger().info(f'Camera opened on {device}')
            else:
                self.get_logger().warning('Falling back to synthetic camera frames (device unavailable).')
        else:
            self.get_logger().warning('OpenCV not available; using synthetic frames.')

        self._publisher = self.create_publisher(Image, '/camera/image_raw', 10)
        self._diag_pub = self.create_publisher(DiagnosticArray, '/diagnostics', 10)
        self._timer = self.create_timer(self._frame_period, self._on_timer)
        self._start_time = time.time()

    def _parse_resolution(self) -> Tuple[int, int]:
        res = self.get_parameter('resolution').value
        if isinstance(res, (list, tuple)) and len(res) == 2:
            return int(res[0]), int(res[1])
        return 640, 480

    def _synthetic_frame(self, width: int, height: int) -> np.ndarray:
        t = time.time() - self._start_time
        xv, yv = np.meshgrid(np.linspace(0, 1, width), np.linspace(0, 1, height))
        pattern = ((np.sin(2 * np.pi * (xv + t * 0.1)) + 1.0) * 127).astype(np.uint8)
        overlay = np.zeros((height, width, 3), dtype=np.uint8)
        overlay[..., 1] = pattern
        overlay[..., 2] = (yv * 255).astype(np.uint8)
        return overlay

    def _on_timer(self) -> None:
        width, height = self._parse_resolution()
        frame: Optional[np.ndarray] = None
        status = DiagnosticStatus()
        status.name = 'camera'
        status.hardware_id = 'uvc'
        status.level = DiagnosticStatus.OK
        status.message = 'OK'

        if self._capture is not None:
            ok, data = self._capture.read()
            if ok and data is not None:
                frame = data
                self._last_ok = True
            else:
                status.level = DiagnosticStatus.WARN
                status.message = 'Frame grab failed, switching to synthetic frames.'
                self._last_ok = False
        if frame is None:
            frame = self._synthetic_frame(width, height)

        msg = self._bridge.cv2_to_imgmsg(frame, encoding='bgr8')
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'camera_frame'
        self._publisher.publish(msg)

        if not self._last_ok:
            status.level = DiagnosticStatus.WARN
            status.message = 'Synthetic frames in use'
        diag = DiagnosticArray()
        diag.header.stamp = msg.header.stamp
        diag.status = [status]
        self._diag_pub.publish(diag)

    def destroy_node(self) -> bool:
        if self._capture is not None:
            self._capture.release()
        return super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = CameraNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
