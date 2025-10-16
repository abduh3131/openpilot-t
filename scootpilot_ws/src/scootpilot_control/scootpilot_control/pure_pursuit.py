from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import numpy as np


@dataclass
class PurePursuitConfig:
    wheelbase: float = 0.9
    lookahead: float = 1.5


class PurePursuit:
    def __init__(self, config: PurePursuitConfig | None = None) -> None:
        self.cfg = config or PurePursuitConfig()

    def compute(self, pose: Tuple[float, float, float], path: List[Tuple[float, float]]) -> float:
        if not path:
            return 0.0
        x, y, yaw = pose
        lookahead_point = self._select_point((x, y), path)
        dx = lookahead_point[0] - x
        dy = lookahead_point[1] - y
        target_angle = np.arctan2(dy, dx)
        alpha = self._normalize_angle(target_angle - yaw)
        curvature = 2.0 * np.sin(alpha) / self.cfg.lookahead
        steering_angle = np.arctan(curvature * self.cfg.wheelbase)
        return float(np.clip(steering_angle, -0.5, 0.5))

    def _select_point(self, pose_xy: Tuple[float, float], path: List[Tuple[float, float]]) -> Tuple[float, float]:
        coords = np.array(path)
        dists = np.linalg.norm(coords - np.array(pose_xy), axis=1)
        idx = int(np.argmin(dists))
        lookahead_idx = min(len(coords) - 1, idx + int(self.cfg.lookahead * 5))
        return tuple(coords[lookahead_idx])

    @staticmethod
    def _normalize_angle(angle: float) -> float:
        return float((angle + np.pi) % (2 * np.pi) - np.pi)
