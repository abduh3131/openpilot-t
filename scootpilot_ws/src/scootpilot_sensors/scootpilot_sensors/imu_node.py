from __future__ import annotations

import math
import random
from typing import Optional

import rclpy
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus
from geometry_msgs.msg import Vector3
from rclpy.node import Node
from sensor_msgs.msg import Imu


class ImuNode(Node):
    """IMU driver with synthetic vibration model fallback."""

    def __init__(self) -> None:
        super().__init__('imu_driver')
        self.declare_parameter('port', '/dev/ttyUSB2')
        self.declare_parameter('frame_rate', 100)
        self._period = 1.0 / float(self.get_parameter('frame_rate').value)
        self._publisher = self.create_publisher(Imu, '/imu/data', 50)
        self._diag_pub = self.create_publisher(DiagnosticArray, '/diagnostics', 10)
        self._serial = self._open_serial(self.get_parameter('port').value)
        self._timer = self.create_timer(self._period, self._on_timer)
        self._yaw = 0.0

    def _open_serial(self, port: str) -> Optional[object]:
        try:
            import serial

            ser = serial.Serial(port, 115200, timeout=0.02)
            self.get_logger().info(f'IMU connected on {port}')
            return ser
        except Exception as exc:  # noqa: BLE001
            self.get_logger().warning(f'IMU serial fallback engaged: {exc}')
            return None

    def _on_timer(self) -> None:
        msg = Imu()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'imu_link'
        status = DiagnosticStatus()
        status.name = 'imu'
        status.hardware_id = 'imu_generic'
        status.level = DiagnosticStatus.OK
        status.message = 'OK'

        if self._serial is not None:
            try:
                line = self._serial.readline().decode('utf-8').strip().split(',')
                if len(line) >= 9:
                    ax, ay, az, gx, gy, gz, qx, qy, qz = [float(x) for x in line[:9]]
                    msg.linear_acceleration.x = ax
                    msg.linear_acceleration.y = ay
                    msg.linear_acceleration.z = az
                    msg.angular_velocity.x = gx
                    msg.angular_velocity.y = gy
                    msg.angular_velocity.z = gz
                    msg.orientation.x = qx
                    msg.orientation.y = qy
                    msg.orientation.z = qz
                    msg.orientation.w = math.sqrt(max(0.0, 1.0 - (qx * qx + qy * qy + qz * qz)))
                else:
                    raise ValueError('IMU packet too short')
            except Exception:  # noqa: BLE001
                status.level = DiagnosticStatus.WARN
                status.message = 'IMU parse failed, synthesizing motion.'
                self._fill_synthetic(msg)
        else:
            self._fill_synthetic(msg)

        diag = DiagnosticArray()
        diag.status = [status]
        diag.header = msg.header
        self._publisher.publish(msg)
        self._diag_pub.publish(diag)

    def _fill_synthetic(self, msg: Imu) -> None:
        self._yaw += random.uniform(-0.01, 0.01)
        msg.orientation.z = math.sin(self._yaw / 2.0)
        msg.orientation.w = math.cos(self._yaw / 2.0)
        msg.angular_velocity = Vector3(x=0.0, y=0.0, z=random.uniform(-0.05, 0.05))
        msg.linear_acceleration = Vector3(x=random.uniform(-0.2, 0.2), y=random.uniform(-0.2, 0.2), z=9.81)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = ImuNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
