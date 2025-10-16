from __future__ import annotations

from typing import Any, Dict


def flatten_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten nested parameter maps for ROS 2 parameters.

    ROS 2 launch files accept nested dictionaries, but the sensor drivers expect
    parameters at the node level. This helper performs a shallow copy so the
    original configuration remains untouched.
    """

    flattened: Dict[str, Any] = {}
    for key, value in params.items():
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                flattened[f"{key}.{sub_key}"] = sub_value
        else:
            flattened[key] = value
    return flattened
