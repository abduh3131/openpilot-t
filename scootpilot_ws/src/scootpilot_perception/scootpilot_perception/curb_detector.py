from __future__ import annotations

import cv2
import numpy as np


def detect_curbs(mask: np.ndarray) -> np.ndarray:
    """Return curb edges from drivable mask using Canny on inverse region."""

    if mask.ndim == 3:
        mask = mask.squeeze()
    kernel = np.ones((3, 3), np.uint8)
    dilated = cv2.dilate(mask, kernel, iterations=1)
    eroded = cv2.erode(mask, kernel, iterations=1)
    edges = cv2.Canny(dilated - eroded, 50, 150)
    return edges
