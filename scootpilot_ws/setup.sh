#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "--help" ]]; then
  echo "Usage: ./setup.sh"
  exit 0
fi

ROOT_DIR=$(cd "$(dirname "$0")" && pwd)
WS_DIR="$ROOT_DIR"
ROS_DISTRO=${ROS_DISTRO:-humble}

sudo apt-get update
sudo apt-get install -y curl gnupg lsb-release
if ! dpkg -s ros-$ROS_DISTRO-desktop >/dev/null 2>&1; then
  sudo sh -c 'echo "deb [trusted=yes] http://packages.ros.org/ros2/ubuntu $(lsb_release -sc) main" > /etc/apt/sources.list.d/ros2-latest.list'
  curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.asc | sudo apt-key add -
fi
sudo apt-get update
sudo apt-get install -y \
  ros-$ROS_DISTRO-desktop \
  python3-rosdep python3-vcstool python3-colcon-common-extensions \
  ros-$ROS_DISTRO-navigation2 ros-$ROS_DISTRO-nav2-bringup \
  ros-$ROS_DISTRO-rmw-cyclonedds-cpp ros-$ROS_DISTRO-diagnostic-updater \
  ros-$ROS_DISTRO-vision-msgs ros-$ROS_DISTRO-rclpy ros-$ROS_DISTRO-cv-bridge \
  libeigen3-dev libyaml-cpp-dev qtbase5-dev libqt6svg6 libqt6widgets6 \
  python3-pyqt6 python3-opencv onnxruntime

sudo rosdep init 2>/dev/null || true
rosdep update

python3 -m venv "$WS_DIR/.venv"
source "$WS_DIR/.venv/bin/activate"
pip install --upgrade pip
pip install \
  onnxruntime==1.17.0 onnx==1.15.0 numpy==1.26.4 scipy==1.11.4 \
  opencv-python==4.9.0.80 pyyaml==6.0.1 networkx==3.2.1 matplotlib==3.8.2 \
  pyqtgraph==0.13.3 shapely==2.0.3 rtree==1.2.0 pytest==7.4.4 pytest-asyncio==0.21.1 \
  transforms3d==0.4.1 pyserial==3.5 psutil==5.9.7

cd "$WS_DIR"
rosdep install --from-paths src --ignore-src -y -r || true
colcon build --symlink-install

echo "source $WS_DIR/install/setup.bash" > "$WS_DIR/.env"

echo "Setup complete. Run 'source $WS_DIR/install/setup.bash' and ./run_sim.sh"
