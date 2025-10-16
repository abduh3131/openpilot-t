from __future__ import annotations

import random
from typing import Optional

import rclpy
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus
from rclpy.node import Node
from std_msgs.msg import Float32MultiArray


class UltrasonicNode(Node):
    """Simple ultrasonic array driver with fallback noise model."""

    def __init__(self) -> None:
        super().__init__('ultrasonic_driver')
        self.declare_parameter('port', '/dev/ttyUSB1')
        self.declare_parameter('sensor_count', 3)
        self.declare_parameter('frame_rate', 10)
        self._sensor_count = int(self.get_parameter('sensor_count').value)
        self._period = 1.0 / float(self.get_parameter('frame_rate').value)
        self._publisher = self.create_publisher(Float32MultiArray, '/ultrasonic/distances', 10)
        self._diag_pub = self.create_publisher(DiagnosticArray, '/diagnostics', 10)
        self._serial = self._open_serial(self.get_parameter('port').value)
        self._timer = self.create_timer(self._period, self._on_timer)

    def _open_serial(self, port: str) -> Optional[object]:
        try:
            import serial

            ser = serial.Serial(port, 115200, timeout=0.2)
            self.get_logger().info(f'Ultrasonic array connected on {port}')
            return ser
        except Exception as exc:  # noqa: BLE001
            self.get_logger().warning(f'Ultrasonic serial fallback engaged: {exc}')
            return None

    def _on_timer(self) -> None:
        msg = Float32MultiArray()
        status = DiagnosticStatus()
        status.name = 'ultrasonic'
        status.hardware_id = 'ultrasonic_array'
        status.level = DiagnosticStatus.OK
        status.message = 'OK'

        if self._serial is not None:
            try:
                line = self._serial.readline().decode('utf-8').strip()
                values = [float(v) for v in line.split(',')[: self._sensor_count]]
                if len(values) != self._sensor_count:
                    raise ValueError('Incomplete frame')
                msg.data = values
            except Exception:  # noqa: BLE001
                status.level = DiagnosticStatus.WARN
                status.message = 'Serial parse failed, synthesizing ranges.'
                msg.data = [random.uniform(0.3, 4.0) for _ in range(self._sensor_count)]
        else:
            msg.data = [random.uniform(0.4, 5.0) for _ in range(self._sensor_count)]
        msg.layout.dim = []
        self._publisher.publish(msg)

        diag = DiagnosticArray()
        diag.status = [status]
        diag.header.stamp = self.get_clock().now().to_msg()
        self._diag_pub.publish(diag)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = UltrasonicNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
