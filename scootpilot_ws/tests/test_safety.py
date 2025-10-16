import pytest

np = pytest.importorskip('numpy')

from scootpilot_safety.fence_guard import road_violation
from scootpilot_safety.ttc_monitor import compute_ttc


def test_ttc_trigger():
    result = compute_ttc([0.5, 1.0], speed=1.0, threshold=1.0)
    assert result.hazardous


def test_road_violation_detects():
    mask = np.ones((100, 100), dtype=np.uint8) * 255
    mask[:10, :] = 0
    assert road_violation(mask)
