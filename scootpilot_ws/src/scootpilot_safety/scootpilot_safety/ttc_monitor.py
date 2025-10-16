from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np


@dataclass
class TTCResult:
    min_ttc: float
    hazardous: bool


def compute_ttc(distances: Iterable[float], speed: float, threshold: float) -> TTCResult:
    distances = np.array(list(distances), dtype=np.float32)
    if distances.size == 0:
        return TTCResult(min_ttc=float('inf'), hazardous=False)
    relative_speeds = np.maximum(speed, 0.01)
    ttcs = distances / relative_speeds
    min_ttc = float(np.min(ttcs))
    return TTCResult(min_ttc=min_ttc, hazardous=min_ttc < threshold)
