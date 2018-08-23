# pimsviewer
[![Anaconda-Server Badge](https://anaconda.org/conda-forge/pimsviewer/badges/version.svg)](https://anaconda.org/conda-forge/pimsviewer)

A graphical user interface (GUI) for PIMS (screenshot below)

This viewer is based on [TkInter](https://wiki.python.org/moin/TkInter) and is able to work with N-dimensional image files that are opened by PIMS.

Also, it exposes a matplotlib plotting area on which images can be (dynamically)
annotated, making use of the `Plugin` infrastructure.

## Installation

Pimsviewer can be installed using conda:

```
conda install -c conda-forge pimsviewer
```

Alternatively, it can also be installed using pip:

```
pip install pimsviewer 
```

## Starting the viewer

After installing the viewer, an executable `pimsviewer` is available. Simply run the command via your terminal/command line interface.

```
$ pimsviewer --help
Usage: pimsviewer [OPTIONS] [FILENAME]

Options:
  --help  Show this message and exit.
```

## Screenshot

![Screenshot](/screenshot.png?raw=true)

## Examples

All examples below are also available as script files in the `examples` folder.

## Example 00 + 01: Using the viewer from Python
You can use the viewer in a Python script as follows:

```
from pimsviewer import Viewer
viewer = Viewer()
viewer.run()
```
Optionally you may include a filename:

```
from pimsviewer import Viewer
viewer = Viewer('path/to/file')
viewer.run()
```

## Example 02: evaluating the effect of a processing function
This example adds a processing function that adds an adjustable amount of noise
to an image. The amount of noise is tunable with a slider.

```
import tkinter as tk
import numpy as np
from os import path
import pims
from pimsviewer import Viewer, Plugin

def add_noise(img, widget_values):
    if 'noise_level' in widget_values:
        noise_level = widget_values['noise_level']
    else:
        noise_level = 0
    img = img + np.random.random(img.shape) * noise_level / 100 * img.max()
    return img / np.max(img)

filename = path.join(path.dirname(path.realpath(__file__)), '../screenshot.png')

viewer = Viewer(filename)
AddNoise = Plugin(viewer, add_noise, 'Add noise', width=200)
AddNoise += tk.Scale(AddNoise, from_=0, to=200, orient=tk.HORIZONTAL, name='noise_level')
viewer.run()
```

## Example 03: annotating features on a video
This example annotates features that were obtained via trackpy onto a video.
Note that you have to change the filepath to a video file that is supported by
pims.

```
import trackpy as tp
from os import path
from pimsviewer import Viewer, AnnotatePlugin
from pims import pipeline

@pipeline
def as_grey(frame):
    return 0.2125 * frame[:, :, 0] + 0.7154 * frame[:, :, 1] + 0.0721 * frame[:, :, 2]

filename = path.join(path.dirname(path.realpath(__file__)), '../screenshot.png')

viewer = Viewer(filename)

f = tp.batch(as_grey(viewer.reader), diameter=15)
plugin = AnnotatePlugin(viewer, f)

viewer.run()
```

## Example 04: selecting features on a video
This example annotates features on a video, allows to hide and move features,
and returns the adapted dataframe. Note that you have to change the filepath
to a video file that is supported by pims.

```
import trackpy as tp
from pimsviewer import Viewer, SelectionPlugin
from os import path
from pims import pipeline

@pipeline
def as_grey(frame):
    return 0.2125 * frame[:, :, 0] + 0.7154 * frame[:, :, 1] + 0.0721 * frame[:, :, 2]

filename = path.join(path.dirname(path.realpath(__file__)), '../screenshot.png')

viewer = Viewer(filename)

f = tp.batch(as_grey(viewer.reader), diameter=15)
f = tp.link_df(f, search_range=10)
plugin = SelectionPlugin(viewer, f)

viewer.run()
```

## Example 05: designing a custom plotting function
This dynamically shows the effect of `tp.locate`.

```
import trackpy as tp
from pimsviewer import Viewer, Slider, PlottingPlugin

def locate_and_plot(image, radius, minmass, separation, ax):
    f = tp.locate(image, diameter=radius * 2 + 1, minmass=minmass,
                  separation=separation)
    if len(f) == 0:
        return
    return ax.plot(f['x'], f['y'], markersize=15, markeredgewidth=2,
                   markerfacecolor='none', markeredgecolor='r',
                   marker='o', linestyle='none')

reader = pims.open('path/to/file')
Locate = PlottingPlugin(locate_and_plot, 'Locate', dock='right')
Locate += Slider('radius', 2, 20, 7, value_type='int', orientation='vertical')
Locate += Slider('separation', 1, 100, 7, value_type='float', orientation='vertical')
Locate += Slider('minmass', 1, 10000, 100, value_type='int', orientation='vertical')
viewer = Viewer(reader) + Locate
viewer.run()
```

