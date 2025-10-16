from __future__ import annotations

from typing import List, Tuple

import rclpy
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Path
from rclpy.node import Node

from .osm_loader import OSMMap, load_osm


class GlobalPlanner(Node):
    """Compute global path constrained to whitelist OSM ways."""

    def __init__(self) -> None:
        super().__init__('global_planner')
        self.declare_parameter('osm_map', 'config/map/area.osm.pbf')
        self._map: OSMMap | None = None
        self._path_pub = self.create_publisher(Path, '/planning/global_path', 1)
        self._timer = self.create_timer(2.0, self._update_path)

    def _load_map(self) -> OSMMap:
        if self._map is None:
            path = self.get_parameter('osm_map').get_parameter_value().string_value
            self._map = load_osm(path)
            self.get_logger().info(f'Loaded OSM map with {len(self._map.nodes)} nodes')
        return self._map

    def _update_path(self) -> None:
        osm = self._load_map()
        nodes = list(osm.nodes.values())
        if len(nodes) < 2:
            return
        start = nodes[0]
        goal = nodes[-1]
        path_ids = osm.shortest_path(start, goal)
        path_msg = Path()
        path_msg.header.frame_id = 'map'
        for node_id in path_ids:
            lat, lon = osm.nodes[node_id]
            pose = PoseStamped()
            pose.header = path_msg.header
            pose.pose.position.x = lon
            pose.pose.position.y = lat
            pose.pose.position.z = 0.0
            pose.pose.orientation.w = 1.0
            path_msg.poses.append(pose)
        self._path_pub.publish(path_msg)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = GlobalPlanner()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
