from setuptools import setup

package_name = 'scootpilot_planning'

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
    description='Planning nodes for ScootPilot.',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'global_planner = scootpilot_planning.global_planner:main',
            'local_planner = scootpilot_planning.local_planner:main',
        ],
    },
)
