from __future__ import annotations

import numpy as np
from PyQt6 import QtGui, QtWidgets
from cv_bridge import CvBridge
from sensor_msgs.msg import Image


class VideoWidget(QtWidgets.QLabel):
    def __init__(self) -> None:
        super().__init__()
        self.setMinimumSize(320, 240)
        self.setScaledContents(True)
        self._bridge = CvBridge()

    def update_image(self, msg: Image) -> None:
        frame = self._bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        rgb = frame[:, :, ::-1]
        h, w, _ = rgb.shape
        qimage = QtGui.QImage(rgb.data, w, h, QtGui.QImage.Format.Format_RGB888)
        self.setPixmap(QtGui.QPixmap.fromImage(qimage))
