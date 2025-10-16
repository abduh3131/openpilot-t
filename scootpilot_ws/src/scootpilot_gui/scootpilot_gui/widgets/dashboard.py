from __future__ import annotations

from PyQt6 import QtWidgets
from std_msgs.msg import Bool, Float32


class StatusDashboard(QtWidgets.QGroupBox):
    def __init__(self) -> None:
        super().__init__('Status')
        layout = QtWidgets.QFormLayout(self)
        self._speed_label = QtWidgets.QLabel('0.0 m/s')
        self._estop_label = QtWidgets.QLabel('OK')
        layout.addRow('Speed limit', self._speed_label)
        layout.addRow('E-Stop', self._estop_label)

    def update_speed_limit(self, msg: Float32) -> None:
        self._speed_label.setText(f'{msg.data:.2f} m/s')

    def set_estop(self, active: bool) -> None:
        self._estop_label.setText('ACTIVE' if active else 'OK')
        self._estop_label.setStyleSheet('color: red;' if active else 'color: green;')
