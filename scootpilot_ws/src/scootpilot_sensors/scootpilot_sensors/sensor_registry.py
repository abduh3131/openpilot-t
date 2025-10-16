from __future__ import annotations

from typing import Callable, Dict

import rclpy


class SensorRegistry:
    """Simple registry to keep sensor node factories."""

    def __init__(self) -> None:
        self._factories: Dict[str, Callable[[rclpy.node.Node], None]] = {}

    def register(self, name: str, factory: Callable[[rclpy.node.Node], None]) -> None:
        self._factories[name] = factory

    def create(self, name: str, node: rclpy.node.Node) -> None:
        if name not in self._factories:
            raise KeyError(f"Sensor '{name}' is not registered")
        self._factories[name](node)


registry = SensorRegistry()
