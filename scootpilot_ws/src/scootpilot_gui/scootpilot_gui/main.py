from __future__ import annotations

import sys
from typing import Dict

import numpy as np
import rclpy
from PyQt6 import QtCore, QtWidgets
from nav_msgs.msg import Path
from sensor_msgs.msg import Image
from std_msgs.msg import Bool, Float32

from .widgets.dashboard import StatusDashboard
from .widgets.estop import EstopWidget
from .widgets.mapview import MapViewWidget
from .widgets.video import VideoWidget


class ScootPilotWindow(QtWidgets.QMainWindow):
    def __init__(self, node: rclpy.node.Node) -> None:
        super().__init__()
        self.setWindowTitle('ScootPilot Operator Console')
        self._node = node
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QGridLayout(central)

        self.video = VideoWidget()
        self.map_view = MapViewWidget()
        self.dashboard = StatusDashboard()
        self.estop = EstopWidget()

        layout.addWidget(self.video, 0, 0, 2, 2)
        layout.addWidget(self.map_view, 0, 2, 1, 1)
        layout.addWidget(self.dashboard, 1, 2, 1, 1)
        layout.addWidget(self.estop, 2, 0, 1, 3)

        self.start_button = QtWidgets.QPushButton('Start')
        self.stop_button = QtWidgets.QPushButton('Stop')
        self.mode_box = QtWidgets.QComboBox()
        self.mode_box.addItems(['Teleop', 'Assisted', 'Autonomy'])
        self.speed_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.speed_slider.setRange(0, 40)
        self.speed_slider.setValue(20)

        button_row = QtWidgets.QHBoxLayout()
        button_row.addWidget(self.start_button)
        button_row.addWidget(self.stop_button)
        button_row.addWidget(QtWidgets.QLabel('Mode'))
        button_row.addWidget(self.mode_box)
        button_row.addWidget(QtWidgets.QLabel('Speed Limit (km/h)'))
        button_row.addWidget(self.speed_slider)
        layout.addLayout(button_row, 3, 0, 1, 3)

        self.start_button.clicked.connect(lambda: self._publish_bool('/gui/start', True))
        self.stop_button.clicked.connect(lambda: self._publish_bool('/gui/stop', True))
        self.estop.estop_pressed.connect(self._on_estop)
        self.estop.reset_pressed.connect(self._on_reset)
        self.speed_slider.valueChanged.connect(self._on_speed_limit)

        self._node.create_subscription(Image, '/camera/image_raw', self.video.update_image, 10)
        self._node.create_subscription(Path, '/planning/local_path', self.map_view.update_path, 10)
        self._node.create_subscription(Float32, '/planning/speed_limit', self.dashboard.update_speed_limit, 10)
        self._node.create_subscription(Bool, '/safety/estop', self._on_estop_status, 10)
        self._speed_pub = self._node.create_publisher(Float32, '/gui/speed_limit', 10)
        self._estop_pub = self._node.create_publisher(Bool, '/gui/estop', 10)
        self._reset_pub = self._node.create_publisher(Bool, '/gui/reset_estop', 10)

    def _publish_bool(self, topic: str, value: bool) -> None:
        pub = self._node.create_publisher(Bool, topic, 10)
        msg = Bool()
        msg.data = value
        pub.publish(msg)

    def _on_speed_limit(self, value: int) -> None:
        msg = Float32()
        msg.data = float(value) / 3.6
        self._speed_pub.publish(msg)

    def _on_estop(self) -> None:
        msg = Bool()
        msg.data = True
        self._estop_pub.publish(msg)

    def _on_reset(self) -> None:
        msg = Bool()
        msg.data = True
        self._reset_pub.publish(msg)

    def _on_estop_status(self, msg: Bool) -> None:
        self.estop.set_estop(msg.data)
        self.dashboard.set_estop(msg.data)


class GuiNode(rclpy.node.Node):
    def __init__(self) -> None:
        super().__init__('scootpilot_gui')


def main() -> None:
    rclpy.init()
    node = GuiNode()
    app = QtWidgets.QApplication(sys.argv)
    window = ScootPilotWindow(node)
    window.show()

    timer = QtCore.QTimer()
    timer.setInterval(50)

    def spin():
        rclpy.spin_once(node, timeout_sec=0.0)

    timer.timeout.connect(spin)
    timer.start()
    app.exec()
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
