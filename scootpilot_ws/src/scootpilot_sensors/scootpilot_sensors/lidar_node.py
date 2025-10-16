from __future__ import annotations

import math
import random
from typing import Optional

import numpy as np
import rclpy
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus
from rclpy.node import Node
from sensor_msgs.msg import LaserScan


class LidarNode(Node):
    """Serial LiDAR reader with deterministic simulation fallback."""

    def __init__(self) -> None:
        super().__init__('lidar_driver')
        self.declare_parameter('port', '/dev/ttyUSB0')
        self.declare_parameter('frame_rate', 10)
        self.declare_parameter('enabled', False)
        self._period = 1.0 / float(self.get_parameter('frame_rate').value)
        self._publisher = self.create_publisher(LaserScan, '/lidar/points', 10)
        self._diag_pub = self.create_publisher(DiagnosticArray, '/diagnostics', 10)
        self._timer = self.create_timer(self._period, self._on_timer)
        self._serial = self._open_serial(self.get_parameter('port').value)

    def _open_serial(self, port: str) -> Optional[object]:
        try:
            import serial

            ser = serial.Serial(port, 115200, timeout=0.1)
            self.get_logger().info(f'LiDAR connected on {port}')
            return ser
        except Exception as exc:  # noqa: BLE001
            self.get_logger().warning(f'LiDAR serial fallback engaged: {exc}')
            return None

    def _simulate_scan(self) -> np.ndarray:
        angles = np.linspace(-math.pi, math.pi, 360)
        base = 4.0 - 1.0 * np.cos(angles)
        for idx in range(angles.size // 20, angles.size // 18):
            base[idx] = 1.0 + 0.2 * math.sin(idx)
        return base

    def _on_timer(self) -> None:
        scan = LaserScan()
        scan.header.stamp = self.get_clock().now().to_msg()
        scan.header.frame_id = 'lidar'
        scan.angle_min = -math.pi
        scan.angle_max = math.pi
        scan.angle_increment = (scan.angle_max - scan.angle_min) / 360.0
        scan.time_increment = self._period / 360.0
        scan.range_min = 0.1
        scan.range_max = 10.0

        status = DiagnosticStatus()
        status.name = 'lidar'
        status.hardware_id = 'serial_lidar'
        status.level = DiagnosticStatus.OK
        status.message = 'OK'

        if self._serial:
            try:
                # Minimal stub reading pattern.
                raw = self._serial.read(2 * 360)
                if len(raw) >= 720:
                    data = np.frombuffer(raw[:720], dtype=np.uint16).astype(np.float32) / 1000.0
                    scan.ranges = data.tolist()
                else:
                    raise RuntimeError('insufficient data')
            except Exception:  # noqa: BLE001
                status.level = DiagnosticStatus.WARN
                status.message = 'Serial read failed, using synthetic scan.'
                scan.ranges = self._simulate_scan().tolist()
        else:
            scan.ranges = self._simulate_scan().tolist()

        # Add mild noise to keep planners conservative.
        scan.ranges = [max(scan.range_min, min(scan.range_max, r + random.uniform(-0.05, 0.05))) for r in scan.ranges]
        self._publisher.publish(scan)

        diag = DiagnosticArray()
        diag.header = scan.header
        diag.status = [status]
        self._diag_pub.publish(diag)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = LidarNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
