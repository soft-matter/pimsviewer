from skimage.viewer.qt import (Qt, QtWidgets, QtGui, QtCore, Signal,
                               _qt_version, has_qt, FigureCanvasQTAgg)
from skimage.viewer.utils import init_qtapp, start_qtapp
from PyQt5.QtWidgets import QShortcut
from PyQt5.QtGui import QKeySequence
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT


class NavigationToolbar(NavigationToolbar2QT):
    # only display the buttons we need
    toolitems = [t for t in NavigationToolbar2QT.toolitems if
                 t[0] in ('Home', 'Back', 'Forward', 'Pan', 'Zoom')]

    def __init__(self, canvas, parent):
        super().__init__(canvas, parent, coordinates=False)
