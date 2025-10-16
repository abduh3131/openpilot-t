from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import yaml
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction, SetEnvironmentVariable
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

from .param_utils import flatten_params


CONFIG_RELATIVE = 'config/sensors.example.yaml'


def _load_yaml(root: Path, relative: str) -> Dict[str, Any]:
    path = root / relative
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")
    with path.open('r', encoding='utf-8') as handle:
        return yaml.safe_load(handle)


def _configure_sensors(cfg: Dict[str, Any], use_sim: bool) -> Dict[str, Any]:
    sensors = cfg.get('sensors', {})
    if use_sim:
        for sensor_cfg in sensors.values():
            sensor_cfg['enabled'] = False
    return sensors


def _launch_nodes(context, use_sim: LaunchConfiguration, gui: LaunchConfiguration):
    root = Path(os.environ.get('SCOOTPILOT_ROOT', Path(__file__).resolve().parents[3]))
    cfg = _load_yaml(root, CONFIG_RELATIVE)
    sim_cfg = cfg.get('sim', {})
    sensors = _configure_sensors(cfg, use_sim=context.launch_configurations['use_sim'] == 'true')

    nodes = []

    for name, params in sensors.items():
        if not params.get('enabled', False):
            continue
        nodes.append(
            Node(
                package='scootpilot_sensors',
                executable=f'{name}_node',
                name=f'{name}_driver',
                output='screen',
                parameters=[flatten_params(params)],
            )
        )

    if context.launch_configurations['use_sim'] == 'true':
        nodes.append(
            Node(
                package='scootpilot_sim',
                executable='sim_node',
                name='scootpilot_simulator',
                output='screen',
                parameters=[sim_cfg],
            )
        )

    perception_params = [{'config_path': str(root / 'config/perception.yaml')}]
    safety_params = [{'config_path': str(root / 'config/safety.yaml')}]

    nodes.extend(
        [
            Node(package='scootpilot_perception', executable='drivable_seg_node', name='drivable_seg', parameters=perception_params),
            Node(package='scootpilot_perception', executable='object_det_node', name='object_detector', parameters=perception_params),
            Node(package='scootpilot_perception', executable='fusion_node', name='perception_fusion', parameters=perception_params),
            Node(package='scootpilot_localization', executable='ekf_fusion_node', name='ekf_fusion'),
            Node(package='scootpilot_planning', executable='global_planner', name='global_planner', parameters=[{'osm_map': str(root / 'config/map/area.osm.pbf') }]),
            Node(package='scootpilot_planning', executable='local_planner', name='local_planner'),
            Node(package='scootpilot_control', executable='control_node', name='control_node'),
            Node(package='scootpilot_safety', executable='supervisor_node', name='safety_supervisor', parameters=safety_params),
        ]
    )

    if context.launch_configurations['gui'] == 'true':
        nodes.append(
            Node(
                package='scootpilot_gui',
                executable='scootpilot_gui',
                name='scootpilot_gui',
                output='screen',
                parameters=[{'config_path': str(root / 'config/sensors.example.yaml')}],
            )
        )

    return nodes


def generate_launch_description() -> LaunchDescription:
    ld = LaunchDescription()
    use_sim_arg = DeclareLaunchArgument('use_sim', default_value='false')
    gui_arg = DeclareLaunchArgument('gui', default_value='true')
    ld.add_action(SetEnvironmentVariable('RCUTILS_COLORIZED_OUTPUT', '1'))
    ld.add_action(use_sim_arg)
    ld.add_action(gui_arg)
    ld.add_action(OpaqueFunction(function=_launch_nodes))
    return ld
