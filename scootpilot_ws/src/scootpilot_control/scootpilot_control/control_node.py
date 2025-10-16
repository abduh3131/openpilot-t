from __future__ import annotations

import time
from typing import List, Optional, Tuple

import numpy as np
import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry, Path
from rclpy.node import Node
from std_msgs.msg import Float32, Float32MultiArray

from .pure_pursuit import PurePursuit
from .speed_controller import SpeedController


class ControlNode(Node):
    """Combines lateral pure pursuit and longitudinal PID control."""

    def __init__(self) -> None:
        super().__init__('control_node')
        self._pose: Tuple[float, float, float] = (0.0, 0.0, 0.0)
        self._speed = 0.0
        self._path: List[Tuple[float, float]] = []
        self._speed_limit = 2.0
        self._pure_pursuit = PurePursuit()
        self._speed_ctrl = SpeedController()
        self._cmd_pub = self.create_publisher(Twist, '/control/cmd', 10)
        self._raw_pub = self.create_publisher(Float32MultiArray, '/control/raw', 10)
        self.create_subscription(Path, '/planning/local_path', self._on_path, 10)
        self.create_subscription(Float32, '/planning/speed_limit', self._on_speed_limit, 10)
        self.create_subscription(Odometry, '/odom', self._on_odom, 10)
        self._last_time = time.time()
        self._timer = self.create_timer(0.05, self._step)
        self._last_accel = 0.0

    def _on_path(self, msg: Path) -> None:
        self._path = [(pose.pose.position.x, pose.pose.position.y) for pose in msg.poses]

    def _on_speed_limit(self, msg: Float32) -> None:
        self._speed_limit = float(np.clip(msg.data, 0.0, 4.2))

    def _on_odom(self, msg: Odometry) -> None:
        self._pose = (
            msg.pose.pose.position.x,
            msg.pose.pose.position.y,
            self._yaw_from_quaternion(msg.pose.pose.orientation),
        )
        self._speed = float(np.hypot(msg.twist.twist.linear.x, msg.twist.twist.linear.y))

    def _step(self) -> None:
        now = time.time()
        dt = now - self._last_time
        self._last_time = now
        steer = self._pure_pursuit.compute(self._pose, self._path)
        target_speed = self._speed_limit
        accel = self._speed_ctrl.step(target_speed, self._speed, dt)
        jerk_limit = 1.5
        accel = np.clip(accel, self._last_accel - jerk_limit * dt, self._last_accel + jerk_limit * dt)
        self._last_accel = accel
        cmd = Twist()
        cmd.linear.x = float(np.clip(self._speed + accel * dt, 0.0, 4.2))
        cmd.angular.z = steer
        self._cmd_pub.publish(cmd)

        raw = Float32MultiArray()
        throttle = max(0.0, accel)
        brake = max(0.0, -accel)
        raw.data = [throttle, brake, steer]
        self._raw_pub.publish(raw)

    @staticmethod
    def _yaw_from_quaternion(quat) -> float:
        return float(np.arctan2(2.0 * quat.w * quat.z, 1.0 - 2.0 * quat.z * quat.z))


def main(args=None) -> None:
    rclpy.init(args=args)
    node = ControlNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
