from __future__ import annotations

import numpy as np


def road_violation(mask: np.ndarray, margin: float = 0.2) -> bool:
    if mask.size == 0:
        return True
    height, width = mask.shape
    boundary = int(height * margin)
    top_band = mask[:boundary, :]
    if np.mean(top_band) < 128:
        return True
    return False
