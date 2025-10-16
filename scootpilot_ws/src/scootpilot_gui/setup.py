from setuptools import setup

package_name = 'scootpilot_gui'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name, f'{package_name}.widgets'],
    package_data={
        f'{package_name}.icons': ['*.svg'],
    },
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='ScootPilot Dev',
    maintainer_email='dev@scootpilot.ai',
    description='PyQt6 operator GUI for ScootPilot.',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'scootpilot_gui = scootpilot_gui.main:main',
        ],
    },
)
