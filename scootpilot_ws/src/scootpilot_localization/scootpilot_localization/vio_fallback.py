from __future__ import annotations

import time

import numpy as np
import rclpy
from cv_bridge import CvBridge
from nav_msgs.msg import Odometry
from rclpy.node import Node
from sensor_msgs.msg import Image


class VioFallback(Node):
    """Visual odometry fallback using simple frame differencing."""

    def __init__(self) -> None:
        super().__init__('vio_fallback')
        self._bridge = CvBridge()
        self._last_gray = None
        self._last_time = time.time()
        self._x = 0.0
        self._y = 0.0
        self._odom_pub = self.create_publisher(Odometry, '/vio/odom', 10)
        self.create_subscription(Image, '/camera/image_raw', self._on_image, 10)

    def _on_image(self, msg: Image) -> None:
        frame = self._bridge.imgmsg_to_cv2(msg, desired_encoding='mono8')
        now = time.time()
        dt = now - self._last_time
        self._last_time = now
        if self._last_gray is None:
            self._last_gray = frame
            return
        diff = np.mean(np.abs(frame.astype(np.float32) - self._last_gray.astype(np.float32)))
        speed = min(2.0, diff / 50.0)
        self._x += speed * dt
        odom = Odometry()
        odom.header = msg.header
        odom.header.frame_id = 'odom'
        odom.child_frame_id = 'base_link'
        odom.pose.pose.position.x = self._x
        odom.pose.pose.position.y = self._y
        odom.twist.twist.linear.x = speed
        self._odom_pub.publish(odom)
        self._last_gray = frame


def main(args=None) -> None:
    rclpy.init(args=args)
    node = VioFallback()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
