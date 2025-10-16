from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import rclpy
from geometry_msgs.msg import Quaternion, TransformStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.time import Time
from sensor_msgs.msg import Imu
from tf2_ros import TransformBroadcaster


@dataclass
class State:
    x: float = 0.0
    y: float = 0.0
    yaw: float = 0.0
    vx: float = 0.0
    vy: float = 0.0


class EkfFusionNode(Node):
    """Lightweight EKF-like integrator for IMU + odom."""

    def __init__(self) -> None:
        super().__init__('ekf_fusion_node')
        self._state = State()
        self._last_update: Optional[Time] = None
        self._odom_sub = self.create_subscription(Odometry, '/sim/odom', self._on_odom, 10)
        self._imu_sub = self.create_subscription(Imu, '/imu/data', self._on_imu, 50)
        self._odom_pub = self.create_publisher(Odometry, '/odom', 10)
        self._tf_broadcaster = TransformBroadcaster(self)
        self._timer = self.create_timer(0.02, self._publish_estimate)
        self._odom_buffer: Optional[Odometry] = None

    def _on_odom(self, msg: Odometry) -> None:
        self._odom_buffer = msg
        self._state.x = msg.pose.pose.position.x
        self._state.y = msg.pose.pose.position.y
        self._state.vx = msg.twist.twist.linear.x
        self._state.vy = msg.twist.twist.linear.y
        orientation = msg.pose.pose.orientation
        self._state.yaw = self._yaw_from_quaternion(orientation)
        self._last_update = self.get_clock().now()

    def _on_imu(self, msg: Imu) -> None:
        now = self.get_clock().now()
        if self._last_update is None:
            self._last_update = now
            return
        dt = (now - self._last_update).nanoseconds / 1e9
        self._last_update = now
        ax = msg.linear_acceleration.x
        ay = msg.linear_acceleration.y
        self._state.vx += ax * dt
        self._state.vy += ay * dt
        self._state.x += self._state.vx * dt
        self._state.y += self._state.vy * dt
        self._state.yaw += msg.angular_velocity.z * dt

    def _publish_estimate(self) -> None:
        now = self.get_clock().now().to_msg()
        odom = Odometry()
        odom.header.stamp = now
        odom.header.frame_id = 'odom'
        odom.child_frame_id = 'base_link'
        odom.pose.pose.position.x = self._state.x
        odom.pose.pose.position.y = self._state.y
        odom.pose.pose.orientation = self._quaternion_from_yaw(self._state.yaw)
        odom.twist.twist.linear.x = self._state.vx
        odom.twist.twist.linear.y = self._state.vy
        self._odom_pub.publish(odom)

        transform = TransformStamped()
        transform.header.stamp = now
        transform.header.frame_id = 'map'
        transform.child_frame_id = 'odom'
        transform.transform.rotation.w = 1.0
        self._tf_broadcaster.sendTransform(transform)

        transform = TransformStamped()
        transform.header.stamp = now
        transform.header.frame_id = 'odom'
        transform.child_frame_id = 'base_link'
        transform.transform.translation.x = self._state.x
        transform.transform.translation.y = self._state.y
        transform.transform.rotation = self._quaternion_from_yaw(self._state.yaw)
        self._tf_broadcaster.sendTransform(transform)

    @staticmethod
    def _quaternion_from_yaw(yaw: float) -> Quaternion:
        quat = Quaternion()
        quat.z = np.sin(yaw / 2.0)
        quat.w = np.cos(yaw / 2.0)
        return quat

    @staticmethod
    def _yaw_from_quaternion(quat: Quaternion) -> float:
        return float(np.arctan2(2.0 * quat.w * quat.z, 1.0 - 2.0 * quat.z * quat.z))


def main(args=None) -> None:
    rclpy.init(args=args)
    node = EkfFusionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
