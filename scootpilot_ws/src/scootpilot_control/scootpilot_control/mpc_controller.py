from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import numpy as np


@dataclass
class MPCConfig:
    horizon: int = 10
    dt: float = 0.1
    max_steer: float = 0.5


class SimpleMPC:
    """A tiny MPC stub that solves a least-squares steering problem."""

    def __init__(self, config: MPCConfig | None = None) -> None:
        self.cfg = config or MPCConfig()

    def compute(self, pose: Tuple[float, float, float], path: List[Tuple[float, float]]) -> float:
        if len(path) < 2:
            return 0.0
        x, y, yaw = pose
        waypoints = np.array(path[: self.cfg.horizon])
        diffs = waypoints - np.array([x, y])
        desired_heading = np.arctan2(diffs[:, 1], diffs[:, 0])
        heading_error = desired_heading - yaw
        heading_error = (heading_error + np.pi) % (2 * np.pi) - np.pi
        steer = np.mean(heading_error)
        return float(np.clip(steer, -self.cfg.max_steer, self.cfg.max_steer))
