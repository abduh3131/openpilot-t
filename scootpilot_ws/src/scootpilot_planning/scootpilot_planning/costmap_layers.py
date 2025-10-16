from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product
from typing import List, Tuple

import numpy as np


@dataclass
class DynamicCostmap:
    width: int
    height: int
    resolution: float
    origin: Tuple[float, float] = (0.0, 0.0)
    data: np.ndarray = field(init=False)

    def __post_init__(self) -> None:
        self.data = np.zeros((self.height, self.width), dtype=np.float32)

    def update_from_mask(self, mask: np.ndarray) -> None:
        if mask.shape != self.data.shape:
            mask = np.resize(mask, self.data.shape)
        self.data = np.clip(mask.astype(np.float32) / 255.0, 0.0, 1.0)

    def add_inflation(self, radius: int = 5) -> None:
        padded = np.pad(self.data, radius, mode='edge')
        inflated = np.copy(self.data)
        for dx, dy in product(range(-radius, radius + 1), repeat=2):
            inflated = np.maximum(inflated, padded[radius + dy: radius + dy + self.height, radius + dx: radius + dx + self.width])
        self.data = np.clip(inflated, 0.0, 1.0)

    def mark_obstacles(self, detections: List[Tuple[int, float, Tuple[float, float, float, float]]]) -> None:
        for _, _, (x1, y1, x2, y2) in detections:
            x1 = int(np.clip(x1, 0, self.width - 1))
            y1 = int(np.clip(y1, 0, self.height - 1))
            x2 = int(np.clip(x2, 0, self.width - 1))
            y2 = int(np.clip(y2, 0, self.height - 1))
            self.data[y1:y2 + 1, x1:x2 + 1] = 1.0

    def cost_at(self, x: int, y: int) -> float:
        return float(self.data[int(np.clip(y, 0, self.height - 1)), int(np.clip(x, 0, self.width - 1))])
