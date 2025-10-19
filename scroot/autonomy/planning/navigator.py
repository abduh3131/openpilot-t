from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional

import numpy as np

from autonomy.utils.data_structures import DetectedObject, HighLevelCommand, NavigationDecision


@dataclass
class NavigatorConfig:
    target_speed_mps: float = 4.0  # ~14 km/h
    collision_area_threshold: float = 8_000.0
    emergency_brake_threshold: float = 15_000.0
    central_band_ratio: float = 0.25
    hysteresis: float = 0.1
    turn_bias_strength: float = 0.75


class Navigator:
    """Generates high level navigation goals using obstacle detections and operator commands."""

    def __init__(self, config: NavigatorConfig | None = None) -> None:
        self.config = config or NavigatorConfig()
        self._last_bias = 0.0

    def plan(
        self,
        detections: Iterable[DetectedObject],
        frame_size: tuple[int, int],
        command: Optional[HighLevelCommand] = None,
    ) -> NavigationDecision:
        width, height = frame_size
        if width <= 0 or height <= 0:
            raise ValueError("Invalid frame size provided to navigator")

        occupancy = {"left": 0.0, "center": 0.0, "right": 0.0}
        hazard_level = 0.0
        metadata: Dict[str, float] = {
            "obstacle_left": 0.0,
            "obstacle_center": 0.0,
            "obstacle_right": 0.0,
        }

        x_left = width / 3.0
        x_right = 2.0 * width / 3.0
        center_band = (
            width * (0.5 - self.config.central_band_ratio / 2.0),
            width * (0.5 + self.config.central_band_ratio / 2.0),
        )

        for detection in detections:
            x_center = detection.center_x
            area = detection.area
            if x_center < x_left:
                occupancy["left"] += area
            elif x_center > x_right:
                occupancy["right"] += area
            else:
                occupancy["center"] += area

            if center_band[0] <= x_center <= center_band[1]:
                hazard_level = max(hazard_level, min(1.0, area / self.config.emergency_brake_threshold))

        metadata.update({
            "obstacle_left": occupancy["left"],
            "obstacle_center": occupancy["center"],
            "obstacle_right": occupancy["right"],
        })

        best_direction = min(occupancy, key=occupancy.get)
        bias_lookup = {"left": -1.0, "center": 0.0, "right": 1.0}
        steering_bias = bias_lookup[best_direction]

        if occupancy["center"] > self.config.collision_area_threshold:
            steering_bias = bias_lookup[best_direction]
        else:
            steering_bias = steering_bias * 0.5  # prefer gentle adjustments when the path is clear

        if abs(steering_bias - self._last_bias) < self.config.hysteresis:
            steering_bias = self._last_bias
        else:
            self._last_bias = steering_bias

        desired_speed = self.config.target_speed_mps * (1.0 - 0.7 * hazard_level)
        goal_context = "cruise"

        if command:
            goal_context = command.raw_text or command.command_type
            if command.command_type == "stop":
                desired_speed = 0.0
                hazard_level = max(hazard_level, 1.0)
            elif command.command_type == "move_distance" and command.distance_m:
                metadata["goal_distance_m"] = command.distance_m
            elif command.command_type == "turn" and command.target:
                if command.target == "left":
                    steering_bias = -self.config.turn_bias_strength
                elif command.target == "right":
                    steering_bias = self.config.turn_bias_strength
                else:  # turn around
                    desired_speed = 0.0
                    hazard_level = max(hazard_level, 0.8)

        decision = NavigationDecision(
            steering_bias=float(np.clip(steering_bias, -1.0, 1.0)),
            desired_speed=float(max(0.0, desired_speed)),
            hazard_level=float(np.clip(hazard_level, 0.0, 1.0)),
            metadata=metadata,
            goal_context=goal_context,
        )
        return decision
