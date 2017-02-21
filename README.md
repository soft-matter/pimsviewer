# pimsviewer
A graphical user interface (GUI) for PIMS

This viewer is a reimplementation of the `skimage.viewer.CollectionViewer` ([docs](http://scikit-image.org/docs/dev/user_guide/viewer.html)) to be able to work with N-dimensional files (`pims.FramesSequenceND` subclasses).

It makes use of the `Plugin` infrastructure. For example, to annotate a `DataFrame` on a video:

```
import pims
from pimsviewer import Viewer, AnnotatePlugin

viewer = Viewer(pims.open(some_file_path))
viewer += AnnotatePlugin(some_feature_dataframe)
viewer.show()
```
