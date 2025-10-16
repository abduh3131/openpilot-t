from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PIDConfig:
    kp: float = 1.2
    ki: float = 0.1
    kd: float = 0.05
    max_accel: float = 1.0
    max_decel: float = 1.5


class SpeedController:
    def __init__(self, config: PIDConfig | None = None) -> None:
        self.cfg = config or PIDConfig()
        self.integral = 0.0
        self.last_error: float | None = None

    def reset(self) -> None:
        self.integral = 0.0
        self.last_error = None

    def step(self, target: float, current: float, dt: float) -> float:
        error = target - current
        self.integral = max(-5.0, min(5.0, self.integral + error * dt))
        derivative = 0.0 if self.last_error is None else (error - self.last_error) / max(dt, 1e-3)
        self.last_error = error
        accel = self.cfg.kp * error + self.cfg.ki * self.integral + self.cfg.kd * derivative
        accel = max(-self.cfg.max_decel, min(self.cfg.max_accel, accel))
        return accel
