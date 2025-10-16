from setuptools import setup

package_name = 'scootpilot_localization'

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
    description='Localization nodes for ScootPilot.',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'ekf_fusion_node = scootpilot_localization.ekf_fusion_node:main',
            'vio_fallback = scootpilot_localization.vio_fallback:main',
        ],
    },
)
