from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np


@dataclass(frozen=True)
class DetectedObject:
    """Represents a single detection from the perception system."""

    label: str
    confidence: float
    bbox: Tuple[float, float, float, float]
    area: float

    @property
    def center_x(self) -> float:
        x_min, _, x_max, _ = self.bbox
        return (x_min + x_max) / 2.0

    @property
    def center_y(self) -> float:
        _, y_min, _, y_max = self.bbox
        return (y_min + y_max) / 2.0


@dataclass(frozen=True)
class HighLevelCommand:
    """Structured operator intent for the navigator and advisor."""

    command_type: str
    target: Optional[str] = None
    distance_m: Optional[float] = None
    raw_text: str = ""


@dataclass(frozen=True)
class NavigationDecision:
    """Simplified high-level plan for the controller."""

    steering_bias: float  # -1.0 (left) .. +1.0 (right)
    desired_speed: float  # meters per second
    hazard_level: float   # 0.0 (clear) .. 1.0 (imminent stop)
    metadata: Dict[str, float]
    enforced_stop: bool = False
    directive: str = ""
    caption: str = ""
    goal_context: str = ""


@dataclass(frozen=True)
class ActuatorCommand:
    """Low level command that maps directly to throttle/steer/brake actuators."""

    steer: float    # -1.0 .. +1.0
    throttle: float  # 0.0 .. 1.0
    brake: float     # 0.0 .. 1.0


@dataclass(frozen=True)
class PerceptionSummary:
    """Aggregate information from the perception stack for visualization/logging."""

    objects: List[DetectedObject]
    frame_size: Tuple[int, int]


@dataclass(frozen=True)
class AdvisorDirective:
    """Advisor feedback used for compliance and operator feedback."""

    directive: str
    enforced_stop: bool
    caption: str


@dataclass(frozen=True)
class PilotSnapshot:
    """Full-state snapshot produced on every pilot iteration for observers."""

    frame: np.ndarray
    perception: PerceptionSummary
    decision: NavigationDecision
    command: ActuatorCommand
    timestamp: float
