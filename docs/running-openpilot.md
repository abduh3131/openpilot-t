# Running openpilot on a Desktop

This guide walks through setting up openpilot on Ubuntu, launching the software, and monitoring actuator values from a second terminal. It complements the existing `README.md` by focusing on a reproducible local developer workflow.

## Prerequisites

* **Operating system:** Ubuntu 22.04 LTS or 24.04 LTS (desktop or server). Other Debian-based systems may work but are not covered here.
* **Hardware:** A machine with a recent NVIDIA GPU is recommended for real-time performance. The `one_step_openpilot.sh` helper runs equally well on bare metal, WSL2, or inside an Ubuntu container.
* **Network access:** The script downloads several gigabytes of Git LFS assets (neural network weights) the first time it runs.
* **Tools:** `git`, `git-lfs`, `curl`, and `tmux`. The provided setup script installs the missing packages automatically when run with sudo privileges.

## Quick-start (single command)

Run the helper script from any terminal:

```bash
./tools/one_step_openpilot.sh
```

If you prefer an integrated desktop experience, run the top-level setup script to install dependencies and then launch the GUI controller:

```bash
./setup_openpilot.sh
./tools/gui/openpilot_desktop.py
```

The GUI offers start/stop controls for the camera-driven launcher, lets you pick a USB or integrated camera, chooses where to log actuator CSV output, and surfaces actuator values in real time.

What the script does:

1. Creates `~/openpilot` if necessary and clones (or updates) the repository specified by `OPENPILOT_REPO_URL`.
2. Fetches Git LFS assets and initializes all submodules.
3. Calls `tools/ubuntu_setup.sh` to install Ubuntu packages and Python dependencies into `.venv`.
4. Starts a `tmux` session named `openpilot` with two windows:
   * **Window 0:** Runs `./launch_openpilot.sh`, which now feeds frames from the selected camera into the camera-only controller and writes actuator samples to the configured CSV file.
   * **Window 1:** Runs `tools/actuators/monitor_actuators.py` to print actuator commands in real time.

When the script finishes bootstrapping, it automatically attaches to the `tmux` session. Use `Ctrl+b` followed by `n` to switch between the windows. Detach with `Ctrl+b` then `d`.

### Environment variables

* `OPENPILOT_REPO_URL` – override the Git repository to clone. Defaults to `https://github.com/commaai/openpilot`.
* `OPENPILOT_DIR` – destination directory (default `~/openpilot`).
* `OPENPILOT_BRANCH` – branch or tag to checkout (default `master`).
* `OPENPILOT_TMUX_SESSION` – `tmux` session name (default `openpilot`).
* `OPENPILOT_CAMERA` – camera index or `/dev/video*` path to use when launching. Defaults to `0` (first detected camera).
* `OPENPILOT_ACTUATOR_CSV` – destination CSV path for actuator samples (default `~/openpilot/actuators.csv`).
* `OPENPILOT_CAMERA_FPS` – target loop frequency for the camera controller (default `20`).

## Viewing actuator values manually

If you prefer to control the terminals yourself, or if `tmux` is not installed, open a second terminal and activate the virtual environment created by the setup script:

```bash
cd ~/openpilot
source .venv/bin/activate
python tools/actuators/monitor_actuators.py
```

By default the monitor subscribes to the `carControl` message stream (controller commands before safety limits). To see the post-safety output, pass `--topic carOutput`. Adjust the print frequency with `--rate` (in Hz) if the output scrolls too quickly. The camera launcher also writes every actuator update to the CSV path you configure, making it easy to post-process steering and throttle requests.

Sample output:

```
logMonoTime=123456789012345678 | steering angle (deg):  0.012 | steering torque:  0.050 | raw steer command:  0.048 | steer rate:  0.005 | acceleration request:  0.100 | brake request:  - | longitudinal state: pid
```

## Stopping openpilot

Inside the `tmux` session press `Ctrl+C` in the window running `launch_openpilot.sh`. To stop the monitor, use `Ctrl+C` in its window as well. Detach from `tmux` with `Ctrl+b` then `d` if you want the processes to keep running in the background.

## Troubleshooting tips

* **Missing dependencies:** Re-run `tools/one_step_openpilot.sh` after installing missing packages or when switching machines. It is safe to run multiple times.
* **Git LFS failures:** Ensure `git-lfs` is installed and authenticated (for private forks). You can re-run `git lfs pull` manually inside the repository.
* **No actuator messages:** Ensure `launch_openpilot.sh` is pointed at a valid camera (use the desktop GUI or set `OPENPILOT_CAMERA`). When the camera feed is unavailable the launcher will pause until frames are received.
* **tmux not installed:** The helper script falls back to running openpilot in the foreground and prints the exact command to run in a second terminal.

## Related resources

* `README.md` – high-level overview of the project.
* `tools/op.sh` – swiss-army knife for advanced developers (building, testing, running tools).
* `tools/replay/` – utilities for log replay if you do not have hardware connected.
