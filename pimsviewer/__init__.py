from .viewer import Viewer
from .plugins import (Plugin, ProcessPlugin, PlottingPlugin, AnnotatePlugin,
                      SelectionPlugin)
from .widgets import Button, Slider, CheckBox
from .run_gui import run

try:
    from pimsviewer.qt import has_qt
except ImportError:
    has_qt = False

if has_qt:
    pass
else:
    def viewer_not_available(*args, **kwargs):
        raise ImportError(
            "The PIMS viewer requires scikit-image, matplotlib, and PyQt.")
    Viewer = ViewerPipeline = ViewerPlotting = viewer_not_available
