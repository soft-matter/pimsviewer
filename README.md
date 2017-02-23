# pimsviewer
A graphical user interface (GUI) for PIMS

This viewer was based on `skimage.viewer.CollectionViewer` ([docs](http://scikit-image.org/docs/dev/user_guide/viewer.html))
and is able to work with N-dimensional image files that are opened by PIMS.

Also, it exposes a matplotlib plotting area on which images can be (dynamically)
annotated, making use of the `Plugin` infrastructure.

## Starting the viewer
You can start the viewer as follows:

```
from pimsviewer import Viewer
viewer = Viewer()
viewer.show()
```
Optionally you may include a reader:

```
import pims
from pimsviewer import Viewer
viewer = Viewer(pims.open('path/to/file'))
viewer.show()
```

## Example: evaluating the effect of a processing function
This example adds a processing function that adds an adjustable amount of noise
to an image. The amount of noise is tunable with a slider, which is displayed
on the right of the image window.

```
from pims import pipeline, open
from pimsviewer import Viewer, PipelinePlugin, Slider

reader = pims.open('path/to/file')

@pipeline
def add_noise(img, noise_level):
    return img + (np.random.random(img.shape) * noise_level).astype(img.dtype)

AddNoise = PipelinePlugin(add_noise, 'Add noise', dock='right')
AddNoise += Slider('noise_level', 0, 100, 0, orientation='vertical')
viewer = Viewer(reader) + AddNoise
viewer.show()
```

## Example: annotating features on a video
This example annotates features that were obtained via trackpy onto a video.

```
import trackpy as tp
from pimsviewer import Viewer, AnnotatePlugin
reader = pims.open('path/to/file')
f = tp.batch(reader, diameter=15)
(Viewer(reader) + AnnotatePlugin(f)).show()
```

## Example: selecting features on a video
This example annotates features on a video, allows to hide and move
features, and returns the adapted dataframe.

```
import trackpy as tp
from pimsviewer import Viewer, SelectionPlugin
reader = pims.open('path/to/file')
f = tp.batch(reader, diameter=15)
f = tp.link_df(f, search_range=10)
viewer = Viewer(reader) + SelectionPlugin(f)
f_result = viewer.show()
```

## Example: designing a custom plotting function
This dynamically shows the effect of `tp.locate`.

```
import trackpy as tp
from pimsviewer import Viewer, AnnotatePlugin

def locate_and_plot(image, radius, minmass, separation, ax):
    f = tp.locate(image, radius * 2 + 1, minmass, None, separation, noise_size)
    if len(f) == 0:
        return
    return ax.plot(f['x'], f['y'], markersize=15, markeredgewidth=2,
                   markerfacecolor='none', markeredgecolor='r',
                   marker='o', linestyle='none')

reader = pims.open('path/to/file')
Locate = PlottingPlugin(locate_and_plot, 'Locate', dock='right')
Locate += Slider('radius', 1, 20, 7, value_type='int', orientation='vertical')
Locate += Slider('separation', 1, 20, 7, value_type='float', orientation='vertical')
Locate += Slider('minmass', 1, 10000, 100, value_type='int', orientation='vertical')
viewer = Viewer(reader) + Locate
viewer.show()
```