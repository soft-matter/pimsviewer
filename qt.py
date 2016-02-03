from skimage.viewer.qt import (Qt, QtWidgets, QtGui, QtCore, Signal,
                               _qt_version, has_qt, FigureCanvasQTAgg)
from skimage.viewer.utils import init_qtapp, start_qtapp

try:
    from qimage2ndarray import array2qimage, rgb_view
    has_qimage2ndarray = True
except:
    def no_qimage2ndarray_raiser(*args, **kwargs):
        raise ImportError('Please install qimage2ndarray for this function.')
    rgb_view = array2qimage = no_qimage2ndarray_raiser
    has_qimage2ndarray = False
