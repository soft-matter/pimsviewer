import os
from setuptools import setup

try:
    descr = open(os.path.join(os.path.dirname(__file__), 'README.md')).read()
except IOError:
    descr = ''

try:
    from pypandoc import convert

    descr = convert(descr, 'rst', format='md')
except ImportError:
    pass

setup_parameters = dict(
    name="pimsviewer",
    version='2.0',
    description="Viewer for Python IMage Sequence (PIMS).",
    author="Ruben Verweij",
    author_email="ruben@lighthacking.nl",
    url="https://github.com/soft-matter/pimsviewer",
    install_requires=['scikit-image>=0.11', 'matplotlib>=2.2.2', 'pims>=0.4',
                      'pillow', 'click', 'slicerator', 'pygubu'],
    python_requires='>=3.0',
    packages=['pimsviewer'],
    package_data={
        'pimsviewer': [
            'interface.ui',
            ]
    },
    long_description=descr,
    entry_points={
        'gui_scripts': [
            'pimsviewer=pimsviewer.run_gui:run',
        ],
    },
)

setup(**setup_parameters)
