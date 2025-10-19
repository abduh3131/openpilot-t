from __future__ import annotations

from dataclasses import dataclass

from autonomy.utils.data_structures import ActuatorCommand, NavigationDecision
from autonomy.utils.filters import LowPassFilter


@dataclass
class ControllerConfig:
    max_speed_mps: float = 6.0
    max_acceleration: float = 2.0
    steering_gain: float = 0.6
    brake_gain: float = 1.5
    throttle_gain: float = 0.8
    smoothing_alpha: float = 0.3


class Controller:
    """Produces raw actuator values from navigation decisions."""

    def __init__(self, config: ControllerConfig | None = None) -> None:
        self.config = config or ControllerConfig()
        self._steer_filter = LowPassFilter(alpha=self.config.smoothing_alpha)
        self._throttle_filter = LowPassFilter(alpha=self.config.smoothing_alpha)
        self._brake_filter = LowPassFilter(alpha=self.config.smoothing_alpha)

    def command(self, decision: NavigationDecision) -> ActuatorCommand:
        if decision.enforced_stop:
            steer = self._steer_filter.update(0.0)
            throttle = self._throttle_filter.update(0.0)
            brake = self._brake_filter.update(1.0)
            return ActuatorCommand(steer=steer, throttle=throttle, brake=brake)

        speed_ratio = min(1.0, decision.desired_speed / max(1e-3, self.config.max_speed_mps))
        throttle = speed_ratio * self.config.throttle_gain * (1.0 - decision.hazard_level)
        brake = decision.hazard_level * self.config.brake_gain
        steer = decision.steering_bias * self.config.steering_gain

        steer = max(-1.0, min(1.0, steer))
        throttle = max(0.0, min(1.0, throttle))
        brake = max(0.0, min(1.0, brake))

        steer = self._steer_filter.update(steer)
        throttle = self._throttle_filter.update(throttle)
        brake = self._brake_filter.update(brake)

        # Mutually exclusive throttle/brake preference
        if brake > 0.05:
            throttle = min(throttle, 0.1)

        return ActuatorCommand(steer=steer, throttle=throttle, brake=brake)
