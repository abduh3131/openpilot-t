from __future__ import annotations

from PyQt6 import QtCore, QtWidgets


class EstopWidget(QtWidgets.QWidget):
    estop_pressed = QtCore.pyqtSignal()
    reset_pressed = QtCore.pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        layout = QtWidgets.QHBoxLayout(self)
        self.estop_button = QtWidgets.QPushButton('EMERGENCY STOP')
        self.estop_button.setStyleSheet('background-color: red; color: white; font-weight: bold;')
        self.reset_button = QtWidgets.QPushButton('Reset')
        layout.addWidget(self.estop_button)
        layout.addWidget(self.reset_button)
        self.estop_button.clicked.connect(self.estop_pressed.emit)
        self.reset_button.clicked.connect(self.reset_pressed.emit)

    def set_estop(self, active: bool) -> None:
        if active:
            self.estop_button.setText('E-STOP ACTIVE')
            self.estop_button.setEnabled(False)
        else:
            self.estop_button.setText('EMERGENCY STOP')
            self.estop_button.setEnabled(True)
