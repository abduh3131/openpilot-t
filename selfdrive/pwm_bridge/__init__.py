"""Utilities for translating openpilot CAN traffic to PWM samples.

This package exposes helper classes that make it easy to mirror CAN bus
messages on a set of virtual PWM channels.  The modules are intentionally
lightweight so they can be imported by external tooling or executed as a
standalone script.  See :mod:`selfdrive.pwm_bridge.bridge` for the command
line entry point.
"""

