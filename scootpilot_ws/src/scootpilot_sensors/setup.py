from setuptools import setup

package_name = 'scootpilot_sensors'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='ScootPilot Dev',
    maintainer_email='dev@scootpilot.ai',
    description='Sensor abstraction layer drivers and stubs.',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'camera_node = scootpilot_sensors.camera_node:main',
            'lidar_node = scootpilot_sensors.lidar_node:main',
            'ultrasonic_node = scootpilot_sensors.ultrasonic_node:main',
            'imu_node = scootpilot_sensors.imu_node:main',
            'gnss_node = scootpilot_sensors.gnss_node:main',
        ],
    },
)
