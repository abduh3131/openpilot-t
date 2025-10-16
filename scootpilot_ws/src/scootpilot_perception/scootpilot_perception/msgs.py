from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class HazardRegion:
    label: str
    polygon: List[Tuple[float, float]]
    confidence: float
