# pimsviewer
[![Anaconda-Server Badge](https://anaconda.org/conda-forge/pimsviewer/badges/version.svg)](https://anaconda.org/conda-forge/pimsviewer)

A graphical user interface (GUI) for PIMS (screenshot below)

This viewer is based on [PyQt5](https://www.riverbankcomputing.com/software/pyqt/intro) and is able to work with N-dimensional image files that are opened by PIMS.

Also, it has a plugin infrastructure that can be used to extend the main functionality.

## Installation

Pimsviewer can be installed using conda:

```
conda install -c conda-forge pimsviewer
```

Alternatively, it can also be installed using pip:

```
pip install pimsviewer 
```

When installing the latest source version, always install it with `pip` (and not with `python setup.py develop`, this will lead to dependency errors for `PyQt`):

Normal installation:

```
pip install .
```

Development installation:

```
pip install . -e
```

## Starting the viewer

After installing the viewer, an executable `pimsviewer` is available. Simply run the command via your terminal/command line interface.

```
$ pimsviewer --help
Usage: pimsviewer [OPTIONS] [FILEPATH]
Options:
--example-plugins / --no-example-plugins
Load additional example plugins
--help                          Show this message and exit.
```

## Screenshot

![Screenshot](/screenshot.png?raw=true)

## Examples

All examples below are also available as script files in the `examples` folder.
By running `pimsviewer --example-plugins`, you can preview the example plugins used below.

## Example 00: Using the viewer from Python

You can use the viewer in a Python script as follows:

```
import sys
from pimsviewer import GUI
from PyQt5.QtWidgets import QApplication

filepath = 'path/to/file'

# Class names of extra plugins to add
plugins = []

app = QApplication(sys.argv)
gui = GUI(extra_plugins=plugins)
gui.open(fileName=filepath)
gui.show()

sys.exit(app.exec_())
```

## Example 01: Using the viewer from Python (the shorter way)

Or, if you do not need a reference to the actual object but you just want to start the program:

```
from pimsviewer import run

run('path/to/file')
```

In both cases, you can omit the file path.

## Example 02: evaluating the effect of a processing function

This example adds a processing function that adds an adjustable amount of noise
to an image. The amount of noise is tunable with a slider.

```
from pimsviewer import run
from pimsviewer.plugins import ProcessingPlugin

run('path/to/file', [ProcessingPlugin])
```

## Example 03: annotating features on a video

This example annotates features that were obtained via trackpy onto a video.
Tracked positions are loaded from a pandas DataFrame CSV file by the user.

```
from pimsviewer import run
from pimsviewer.plugins import AnnotatePlugin

run('path/to/file', [AnnotatePlugin])
```

## Your own plugin?

By looking at the code for the example plugins, it should be fairly easy to
extend pimsviewer using your own plugins. Contact one of the maintainers if you
have any trouble writing your own plugins.

# Authors

Pimsviewer version 1.0 was written by [Casper van der Wel](https://github.com/caspervdw), versions starting from 2.0 are written by [Ruben Verweij](https://github.com/rbnvrw). 
