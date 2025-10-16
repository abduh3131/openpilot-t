from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np
import rclpy
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import OccupancyGrid, Odometry, Path
from rclpy.node import Node
from std_msgs.msg import Float32
from vision_msgs.msg import Detection2DArray

from .behavior_layer import BehaviorTree, SlowNearDriveways, StopOnDanger, YieldToPedestrians
from .costmap_layers import DynamicCostmap


class LocalPlanner(Node):
    """Local planner that follows global path while respecting hazards."""

    def __init__(self) -> None:
        super().__init__('local_planner')
        self._global_path: Optional[Path] = None
        self._costmap: Optional[DynamicCostmap] = None
        self._detections: List[Tuple[int, float, Tuple[float, float, float, float]]] = []
        self._behavior = BehaviorTree([
            YieldToPedestrians(),
            SlowNearDriveways(),
            StopOnDanger(),
        ])
        self._local_pub = self.create_publisher(Path, '/planning/local_path', 10)
        self._speed_pub = self.create_publisher(Float32, '/planning/speed_limit', 10)
        self.create_subscription(Path, '/planning/global_path', self._on_global_path, 10)
        self.create_subscription(OccupancyGrid, '/perception/costmap', self._on_costmap, 10)
        self.create_subscription(Detection2DArray, '/perception/objects', self._on_detections, 10)
        self.create_subscription(Odometry, '/odom', self._on_odometry, 10)
        self._pose = (0.0, 0.0)
        self._timer = self.create_timer(0.1, self._plan)

    def _on_global_path(self, msg: Path) -> None:
        self._global_path = msg

    def _on_costmap(self, msg: OccupancyGrid) -> None:
        array = np.array(msg.data, dtype=np.float32).reshape(msg.info.height, msg.info.width)
        costmap = DynamicCostmap(msg.info.width, msg.info.height, msg.info.resolution)
        costmap.update_from_mask(255 - array.astype(np.uint8))
        costmap.add_inflation(2)
        self._costmap = costmap

    def _on_detections(self, msg: Detection2DArray) -> None:
        detections: List[Tuple[int, float, Tuple[float, float, float, float]]] = []
        for detection in msg.detections:
            if not detection.results:
                continue
            result = detection.results[0]
            label = hash(result.hypothesis.class_id) % 1000
            score = result.hypothesis.score
            bbox = detection.bbox
            x1 = bbox.center.position.x - bbox.size_x / 2.0
            y1 = bbox.center.position.y - bbox.size_y / 2.0
            x2 = bbox.center.position.x + bbox.size_x / 2.0
            y2 = bbox.center.position.y + bbox.size_y / 2.0
            detections.append((label, score, (x1, y1, x2, y2)))
        self._detections = detections

    def _on_odometry(self, msg: Odometry) -> None:
        self._pose = (msg.pose.pose.position.x, msg.pose.pose.position.y)

    def _plan(self) -> None:
        if self._global_path is None:
            return
        local_path = Path()
        local_path.header = self._global_path.header
        points = self._sample_path(self._global_path, self._pose)
        for point in points:
            pose = PoseStamped()
            pose.header = local_path.header
            pose.pose.position.x = point[0]
            pose.pose.position.y = point[1]
            pose.pose.orientation.w = 1.0
            local_path.poses.append(pose)
        self._local_pub.publish(local_path)

        if self._costmap is not None:
            speed = self._behavior.tick(self._costmap.data, self._detections)
            msg = Float32()
            msg.data = max(0.0, float(speed.speed_limit))
            self._speed_pub.publish(msg)
        else:
            msg = Float32()
            msg.data = 3.0
            self._speed_pub.publish(msg)

    def _sample_path(self, path: Path, pose: Tuple[float, float]) -> List[Tuple[float, float]]:
        if not path.poses:
            return []
        coords = np.array([[p.pose.position.x, p.pose.position.y] for p in path.poses])
        pose_array = np.array(pose)
        dists = np.linalg.norm(coords - pose_array, axis=1)
        idx = int(np.argmin(dists))
        lookahead = coords[idx: idx + 20]
        if lookahead.size == 0:
            lookahead = coords[-1:]
        return [tuple(pt) for pt in lookahead]


def main(args=None) -> None:
    rclpy.init(args=args)
    node = LocalPlanner()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
