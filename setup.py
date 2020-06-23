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
    install_requires=['click', 'pims', 'PyQt5>=5.13.1', 'pandas', 'numpy', 'Pillow'],
    python_requires='>=3.0',
    packages=['pimsviewer'],
    package_dir={'pimsviewer': 'pimsviewer'},
    package_data={'': ['*.ui']},
    long_description=descr,
    long_description_content_type="text/markdown",
    entry_points={
        'gui_scripts': [
            'pimsviewer=pimsviewer.gui:run',
        ],
    },
)

setup(**setup_parameters)
