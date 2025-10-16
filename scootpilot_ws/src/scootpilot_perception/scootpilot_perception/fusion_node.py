from __future__ import annotations

from typing import List

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus
from geometry_msgs.msg import Polygon, PolygonStamped, Point32
from nav_msgs.msg import OccupancyGrid
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import Header
from vision_msgs.msg import Detection2DArray

from .curb_detector import detect_curbs


class PerceptionFusionNode(Node):
    """Fuse drivable mask and detections to costmaps and hazard polygons."""

    def __init__(self) -> None:
        super().__init__('perception_fusion')
        self._bridge = CvBridge()
        self._last_mask: np.ndarray | None = None
        self._mask_header: Header | None = None
        self._detections: Detection2DArray | None = None
        self._mask_sub = self.create_subscription(Image, '/perception/drivable_mask', self._on_mask, 10)
        self._det_sub = self.create_subscription(Detection2DArray, '/perception/objects', self._on_detections, 10)
        self._costmap_pub = self.create_publisher(OccupancyGrid, '/perception/costmap', 10)
        self._hazard_pub = self.create_publisher(PolygonStamped, '/perception/hazards', 10)
        self._diag_pub = self.create_publisher(DiagnosticArray, '/diagnostics', 10)
        self._timer = self.create_timer(0.1, self._publish_costmap)

    def _on_mask(self, msg: Image) -> None:
        mask = self._bridge.imgmsg_to_cv2(msg, desired_encoding='mono8')
        self._last_mask = mask
        self._mask_header = msg.header

    def _on_detections(self, msg: Detection2DArray) -> None:
        self._detections = msg

    def _publish_costmap(self) -> None:
        if self._last_mask is None or self._mask_header is None:
            return
        mask = self._last_mask
        costmap = OccupancyGrid()
        costmap.header = self._mask_header
        costmap.info.resolution = 0.05
        costmap.info.width = mask.shape[1]
        costmap.info.height = mask.shape[0]
        costmap.data = (255 - mask.flatten()).tolist()
        self._costmap_pub.publish(costmap)

        curbs = detect_curbs(mask)
        hazard_poly = Polygon()
        hazard_poly.points = self._detections_to_polygon(curbs)
        hazard_msg = PolygonStamped()
        hazard_msg.header = self._mask_header
        hazard_msg.polygon = hazard_poly
        self._hazard_pub.publish(hazard_msg)

        status = DiagnosticStatus()
        status.name = 'perception_fusion'
        status.hardware_id = 'fusion'
        status.level = DiagnosticStatus.OK
        status.message = 'OK'
        diag = DiagnosticArray()
        diag.header = self._mask_header
        diag.status = [status]
        self._diag_pub.publish(diag)

    def _detections_to_polygon(self, curb_edges: np.ndarray) -> List[Point32]:
        points: List[Point32] = []
        if self._detections is None:
            return points
        for detection in self._detections.detections:
            bbox = detection.bbox
            x = bbox.center.position.x
            y = bbox.center.position.y
            points.append(Point32(x=float(x), y=float(y), z=0.0))
        # Highlight curb segments where mask transitions.
        ys, xs = np.where(curb_edges > 0)
        for x, y in zip(xs[:: max(1, len(xs) // 20 + 1)], ys[:: max(1, len(ys) // 20 + 1)]):
            points.append(Point32(x=float(x), y=float(y), z=0.0))
        return points


def main(args=None) -> None:
    rclpy.init(args=args)
    node = PerceptionFusionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
