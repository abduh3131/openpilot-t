import pytest

pytest.importorskip('geometry_msgs')
pytest.importorskip('numpy')

from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Odometry, Path

from scootpilot_control.control_node import ControlNode


def build_path() -> Path:
    path = Path()
    path.header.frame_id = 'map'
    for i in range(10):
        pose = PoseStamped()
        pose.pose.position.x = float(i)
        pose.pose.position.y = 0.0
        pose.pose.orientation.w = 1.0
        path.poses.append(pose)
    return path


def test_control_pipeline_smoke():
    node = ControlNode()
    path = build_path()
    node._on_path(path)
    odom = Odometry()
    odom.pose.pose.position.x = 0.0
    odom.pose.pose.position.y = 0.0
    odom.pose.pose.orientation.w = 1.0
    odom.twist.twist.linear.x = 0.0
    node._on_odom(odom)
    node._on_speed_limit(type('msg', (), {'data': 2.0}))
    node._step()
    assert node._last_accel is not None
