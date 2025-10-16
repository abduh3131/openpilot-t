from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import numpy as np


@dataclass
class BehaviorOutput:
    speed_limit: float
    stop: bool


class Behavior:
    def evaluate(self, costmap: np.ndarray, detections: List[Tuple[int, float, Tuple[float, float, float, float]]]) -> BehaviorOutput:
        raise NotImplementedError


class YieldToPedestrians(Behavior):
    def __init__(self, stop_distance: float = 2.5, max_speed: float = 3.0) -> None:
        self.stop_distance = stop_distance
        self.max_speed = max_speed

    def evaluate(self, costmap, detections):
        for _, score, bbox in detections:
            if score < 0.2:
                continue
            x1, y1, x2, y2 = bbox
            if y1 < costmap.shape[0] * 0.3:
                return BehaviorOutput(speed_limit=0.0, stop=True)
        return BehaviorOutput(speed_limit=self.max_speed, stop=False)


class SlowNearDriveways(Behavior):
    def __init__(self, slow_speed: float = 1.5) -> None:
        self.slow_speed = slow_speed

    def evaluate(self, costmap, detections):
        # Use curb edges as proxy; bright areas near bottom trigger slow down.
        bottom_band = costmap[-10:, :]
        if np.mean(bottom_band) > 0.5:
            return BehaviorOutput(speed_limit=self.slow_speed, stop=False)
        return BehaviorOutput(speed_limit=3.0, stop=False)


class StopOnDanger(Behavior):
    def __init__(self, threshold: float = 0.9) -> None:
        self.threshold = threshold

    def evaluate(self, costmap, detections):
        if np.max(costmap) > self.threshold:
            return BehaviorOutput(speed_limit=0.0, stop=True)
        return BehaviorOutput(speed_limit=3.0, stop=False)


class BehaviorTree:
    def __init__(self, behaviors: List[Behavior]) -> None:
        self.behaviors = behaviors

    def tick(self, costmap: np.ndarray, detections: List[Tuple[int, float, Tuple[float, float, float, float]]]) -> BehaviorOutput:
        speed = 3.0
        stop = False
        for behavior in self.behaviors:
            output = behavior.evaluate(costmap, detections)
            speed = min(speed, output.speed_limit)
            stop = stop or output.stop
        return BehaviorOutput(speed_limit=speed, stop=stop)
