from setuptools import setup

package_name = 'scootpilot_sim'

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
    description='2D kinematic simulator and bag replay tools.',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'sim_node = scootpilot_sim.sim_node:main',
            'replay_bag = scootpilot_sim.replay_bag:main',
        ],
    },
)
