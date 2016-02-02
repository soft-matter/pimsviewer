try:
    from .qt import has_qt
except ImportError:
    has_qt = False

if has_qt:
    from .viewer import Viewer, Plugin
    from .plugins import ViewerPipeline, ViewerPlotting, ViewerAnnotate
    from .widgets import CheckBox, Text, ComboBox, Slider, Button
else:
    def viewer_not_available(*args, **kwargs):
        raise ImportError(
            "The PIMS viewer requires scikit-image, matplotlib, and PyQt.")
    Viewer = ViewerPipeline = ViewerPlotting = viewer_not_available
