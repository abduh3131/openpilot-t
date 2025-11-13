# PWM Bridge

This document describes how to mirror openpilot's CAN traffic as PWM samples so
that development boards or other embedded controllers can interface with the
system without implementing a CAN stack.

## Overview

The bridge is implemented in `selfdrive/pwm_bridge`.  It subscribes to the
standard `can` messaging channel and converts every byte of each CAN frame into
a PWM value.  The conversion is deterministic: bytes in the CAN payload are
linearly mapped to a configurable pulse width (defaulting to 1000–2000 μs at
50 Hz).  The generated PWM samples are written to a CSV file that can be tailed
or streamed to downstream tooling.

```
CAN frame 0x123 -> [0x10, 0x80, 0xFF]
            │
            ├──> PWM channel 0: 1062 μs (10 % duty @ 50 Hz)
            ├──> PWM channel 1: 1500 μs (50 % duty @ 50 Hz)
            └──> PWM channel 2: 2000 μs (100 % duty @ 50 Hz)
```

## Setup

Openpilot already ships with a helper that bootstraps the Python environment.
The following one-line command creates the environment and installs openpilot in
editable mode, making the PWM bridge available immediately:

```bash
./scripts/setup_pwm_bridge.sh
```

This script creates a dedicated virtual environment in `./pwm-env` and installs
openpilot along with the minimal extra dependencies required to access a USB or
laptop webcam via OpenCV.

## Running the Webcam-Enabled Autopilot Stack

Once the environment is ready, the entire stack (openpilot, webcam ingestion,
and the PWM bridge) can be launched with a single command:

```bash
./scripts/run_webcam_pwm_autopilot.sh
```

The script performs the following steps:

1. Activates the virtual environment created during setup.
2. Starts openpilot in **webcam** mode with the simulator loopback enabled so it
   behaves as if it were connected to a real vehicle.
3. Launches `selfdrive.pwm_bridge.bridge`, writing PWM samples to
   `~/openpilot_pwm/pwm_capture.csv` by default.

The bridge prints progress updates every 500 PWM samples.  You can halt the
stack at any time with <kbd>Ctrl</kbd> + <kbd>C</kbd>; both the openpilot
processes and the PWM bridge shut down gracefully.

## Consuming the CSV Output

Each row in the CSV file contains:

| Column        | Description                                                |
|---------------|------------------------------------------------------------|
| `logMonoTime` | nanosecond timestamp from the openpilot messaging system.  |
| `address`     | CAN frame address (identifier).                            |
| `src`         | Source bus index.                                          |
| `busTime`     | Raw bus timing from the CAN message.                       |
| `channel`     | PWM channel number derived from the payload index.         |
| `dutyCycle`   | Duty cycle expressed as a fraction (0–1).                  |
| `pulseWidthUs`| Pulse width for the current channel in microseconds.       |

The CSV can be analysed in real time (for example via `tail -f`) or fed into a
microcontroller over serial/USB for hardware-in-the-loop experiments.

## Customisation

`selfdrive.pwm_bridge.bridge` exposes several CLI flags for tuning:

* `--frequency` — PWM output frequency (Hz), default `50`.
* `--min-us` / `--max-us` — Minimum/maximum pulse widths (μs), default
  `1000` and `2000`.
* `--no-console` — Suppress progress messages on `stderr`.

Refer to the module docstring or run `python -m selfdrive.pwm_bridge.bridge -h`
for the full list of options.

