try:
    from skimage.viewer.qt import has_qt
    viewer_available = has_qt
except ImportError:
    viewer_available = False

if viewer_available:
    from .viewer import Viewer, Plugin
    from .plugins import ViewerPipeline, ViewerPlotting, ViewerAnnotate
    from .widgets import CheckBox, Text, ComboBox, Slider
else:
    def viewer_not_available(*args, **kwargs):
        raise ImportError(
            "The PIMS viewer requires scikit-image, matplotlib, and PyQt.")
    Viewer = ViewerPipeline = ViewerPlotting = viewer_not_available
