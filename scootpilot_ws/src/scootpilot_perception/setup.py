from setuptools import setup

package_name = 'scootpilot_perception'

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
    description='Perception nodes for sidewalk/bike-lane autonomy.',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'drivable_seg_node = scootpilot_perception.drivable_seg_node:main',
            'object_det_node = scootpilot_perception.object_det_node:main',
            'fusion_node = scootpilot_perception.fusion_node:main',
        ],
    },
)
