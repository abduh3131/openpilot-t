from __future__ import annotations

import math
from typing import List

try:
    import cv2
except Exception:  # noqa: BLE001
    cv2 = None

import numpy as np
import rclpy
from cv_bridge import CvBridge
from geometry_msgs.msg import PoseStamped, Twist
from nav_msgs.msg import Odometry, Path
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import Bool
from vision_msgs.msg import Detection2D, Detection2DArray, ObjectHypothesisWithPose

from .kinematics2d import BicycleState, step
from .world import Obstacle, SimWorld


class SimNode(Node):
    def __init__(self) -> None:
        super().__init__('scootpilot_sim')
        self.declare_parameter('step_dt', 0.05)
        self._dt = float(self.get_parameter('step_dt').value)
        self._state = BicycleState(y=2.5)
        self._world = SimWorld(obstacles=[Obstacle(x=8.0, y=2.5, radius=0.3)])
        self._bridge = CvBridge()
        self._odom_pub = self.create_publisher(Odometry, '/sim/odom', 10)
        self._camera_pub = self.create_publisher(Image, '/camera/image_raw', 10)
        self._det_pub = self.create_publisher(Detection2DArray, '/perception/objects', 10)
        self._path_pub = self.create_publisher(Path, '/planning/global_path', 1)
        self._cmd_sub = self.create_subscription(Twist, '/control/cmd', self._on_cmd, 10)
        self._estop_pub = self.create_publisher(Bool, '/sim/estop', 10)
        self._desired_speed = 0.0
        self._desired_yaw = 0.0
        self._timer = self.create_timer(self._dt, self._step_sim)
        self._publish_global_path()

    def _publish_global_path(self) -> None:
        path = Path()
        path.header.frame_id = 'map'
        for x in np.linspace(0.0, self._world.width, 50):
            pose = PoseStamped()
            pose.header = path.header
            pose.pose.position.x = x
            pose.pose.position.y = self._world.height / 2.0
            pose.pose.orientation.w = 1.0
            path.poses.append(pose)
        self._path_pub.publish(path)

    def _on_cmd(self, msg: Twist) -> None:
        self._desired_speed = msg.linear.x
        self._desired_yaw = msg.angular.z

    def _step_sim(self) -> None:
        throttle = (self._desired_speed - self._state.v) * 0.5
        steer = self._desired_yaw
        self._state = step(self._state, throttle, steer, self._dt)
        self._publish_odom()
        self._publish_camera()
        self._publish_detections()

    def _publish_odom(self) -> None:
        odom = Odometry()
        odom.header.stamp = self.get_clock().now().to_msg()
        odom.header.frame_id = 'odom'
        odom.child_frame_id = 'base_link'
        odom.pose.pose.position.x = self._state.x
        odom.pose.pose.position.y = self._state.y
        odom.pose.pose.orientation.z = math.sin(self._state.yaw / 2.0)
        odom.pose.pose.orientation.w = math.cos(self._state.yaw / 2.0)
        odom.twist.twist.linear.x = self._state.v * math.cos(self._state.yaw)
        odom.twist.twist.linear.y = self._state.v * math.sin(self._state.yaw)
        self._odom_pub.publish(odom)

    def _publish_camera(self) -> None:
        width, height = 640, 360
        img = np.zeros((height, width, 3), dtype=np.uint8)
        if cv2 is not None:
            cv2.rectangle(img, (0, int(height * 0.3)), (width, int(height * 0.7)), (120, 200, 120), -1)
        else:
            img[int(height * 0.3): int(height * 0.7), :, 1] = 180
        rel_x = self._world.obstacles[0].x - self._state.x
        obstacle_px = int(width / 2 + rel_x * 15)
        if 0 <= obstacle_px < width:
            img[int(height * 0.5) - 15:int(height * 0.5) + 15, obstacle_px - 15:obstacle_px + 15, 2] = 255
        msg = self._bridge.cv2_to_imgmsg(img, encoding='bgr8')
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'camera'
        self._camera_pub.publish(msg)

    def _publish_detections(self) -> None:
        detections = Detection2DArray()
        detections.header.stamp = self.get_clock().now().to_msg()
        detections.header.frame_id = 'camera'
        for obs in self._world.obstacles:
            rel_x = obs.x - self._state.x
            if rel_x < 0 or rel_x > 6:
                continue
            detection = Detection2D()
            detection.header = detections.header
            hypothesis = ObjectHypothesisWithPose()
            hypothesis.hypothesis.class_id = 'person'
            hypothesis.hypothesis.score = 0.9
            detection.results.append(hypothesis)
            detection.bbox.center.position.x = 320
            detection.bbox.center.position.y = 160
            detection.bbox.size_x = 60
            detection.bbox.size_y = 120
            detections.detections.append(detection)
            if rel_x < 1.0:
                msg = Bool()
                msg.data = True
                self._estop_pub.publish(msg)
        self._det_pub.publish(detections)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = SimNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
