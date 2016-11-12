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
    version='0.1',
    description="PIMS viewer",
    author="Casper van der Wel",
    author_email="caspervdw@gmail.com",
    url="https://bitbucket.org/caspervdw/pimsviewer",
    install_requires=['scikit-image>=0.11', 'matplotlib', 'pims>=0.4'],
    packages=['pimsviewer'],
    long_description=descr,
)

setup(**setup_parameters)
