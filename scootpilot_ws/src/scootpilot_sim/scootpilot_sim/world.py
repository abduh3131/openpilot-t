from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

import numpy as np


@dataclass
class Obstacle:
    x: float
    y: float
    radius: float


@dataclass
class SimWorld:
    width: float = 20.0
    height: float = 5.0
    obstacles: List[Obstacle] = field(default_factory=list)

    def costmap(self, resolution: float = 0.1) -> np.ndarray:
        grid_x = int(self.width / resolution)
        grid_y = int(self.height / resolution)
        grid = np.zeros((grid_y, grid_x), dtype=np.float32)
        for obs in self.obstacles:
            gx = int(obs.x / resolution)
            gy = int(obs.y / resolution)
            rr = int(obs.radius / resolution)
            grid[max(0, gy - rr): min(grid_y, gy + rr), max(0, gx - rr): min(grid_x, gx + rr)] = 1.0
        return grid

    def synthetic_mask(self, resolution: float = 0.1) -> np.ndarray:
        grid = self.costmap(resolution)
        drivable = np.ones_like(grid) * 255
        drivable[grid > 0.5] = 0
        return drivable.astype('uint8')
