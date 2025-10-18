from __future__ import annotations


class LowPassFilter:
    """Simple first-order low pass filter for smoothing control signals."""

    def __init__(self, alpha: float = 0.2, initial: float = 0.0):
        if not 0.0 < alpha <= 1.0:
            raise ValueError("alpha must be between 0 and 1")
        self.alpha = alpha
        self.value = initial

    def update(self, measurement: float) -> float:
        self.value = self.alpha * measurement + (1.0 - self.alpha) * self.value
        return self.value
