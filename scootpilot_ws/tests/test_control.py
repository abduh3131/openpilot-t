import pytest

np = pytest.importorskip('numpy')

from scootpilot_control.pure_pursuit import PurePursuit
from scootpilot_control.speed_controller import SpeedController


def test_pure_pursuit_heading():
    controller = PurePursuit()
    path = [(i * 0.5, 0.0) for i in range(10)]
    steer = controller.compute((0.0, -0.5, 0.0), path)
    assert steer > 0.0


def test_speed_controller_no_overshoot():
    controller = SpeedController()
    speed = 0.0
    for _ in range(20):
        accel = controller.step(2.0, speed, 0.1)
        speed = max(0.0, speed + accel * 0.1)
    assert speed <= 3.0
