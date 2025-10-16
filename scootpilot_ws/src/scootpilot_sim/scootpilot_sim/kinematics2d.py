from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np


@dataclass
class BicycleState:
    x: float = 0.0
    y: float = 0.0
    yaw: float = 0.0
    v: float = 0.0


@dataclass
class BicycleParams:
    wheelbase: float = 0.9


def step(state: BicycleState, throttle: float, steer: float, dt: float, params: BicycleParams | None = None) -> BicycleState:
    params = params or BicycleParams()
    accel = np.clip(throttle, -1.5, 1.0)
    state.v = np.clip(state.v + accel * dt, 0.0, 4.0)
    state.x += state.v * np.cos(state.yaw) * dt
    state.y += state.v * np.sin(state.yaw) * dt
    state.yaw += state.v / params.wheelbase * np.tan(np.clip(steer, -0.5, 0.5)) * dt
    return state
