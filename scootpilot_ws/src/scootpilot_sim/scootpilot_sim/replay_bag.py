from __future__ import annotations

import argparse

import rclpy
from rclpy.node import Node


class ReplayNode(Node):
    def __init__(self, bag_path: str) -> None:
        super().__init__('bag_replay')
        self.get_logger().info(f'Replay stub for bag: {bag_path}')
        self.create_timer(1.0, self._tick)

    def _tick(self) -> None:
        self.get_logger().info('Replay stub tick - integrate with rosbag2 to play back data.')


def main(argv=None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('bag', help='Path to rosbag2 directory')
    args = parser.parse_args(argv)
    rclpy.init()
    node = ReplayNode(args.bag)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
