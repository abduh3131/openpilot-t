from __future__ import annotations

import numpy as np
from PyQt6 import QtGui, QtWidgets
from nav_msgs.msg import Path


class MapViewWidget(QtWidgets.QLabel):
    def __init__(self) -> None:
        super().__init__()
        self.setMinimumSize(320, 240)
        self._path_points = np.zeros((0, 2))

    def update_path(self, msg: Path) -> None:
        if not msg.poses:
            return
        points = np.array([[pose.pose.position.x, pose.pose.position.y] for pose in msg.poses])
        self._path_points = points
        self._render()

    def _render(self) -> None:
        if self._path_points.size == 0:
            return
        pts = self._path_points
        pts -= pts.min(axis=0)
        if pts.max() > 0:
            pts /= pts.max()
        width, height = self.width(), self.height()
        image = QtGui.QImage(width, height, QtGui.QImage.Format.Format_RGB888)
        image.fill(QtGui.QColor('black'))
        painter = QtGui.QPainter(image)
        pen = QtGui.QPen(QtGui.QColor('lime'))
        pen.setWidth(3)
        painter.setPen(pen)
        for idx in range(len(pts) - 1):
            p1 = pts[idx]
            p2 = pts[idx + 1]
            painter.drawLine(int(p1[0] * width), int(height - p1[1] * height), int(p2[0] * width), int(height - p2[1] * height))
        painter.end()
        self.setPixmap(QtGui.QPixmap.fromImage(image))
