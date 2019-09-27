import pims
import numpy as np
from PyQt5.QtCore import QDir, Qt, QSize, QRect, pyqtSignal, QPointF
from PyQt5.QtGui import QImage, QPainter, QPalette, QPixmap, QPen
from PyQt5.QtWidgets import (QAction, QApplication, QFileDialog, QLabel,
                             QMainWindow, QMenu, QMessageBox, QScrollArea,
                             QSizePolicy, QGraphicsPixmapItem)

from pimsviewer.utils import pixmap_from_array, image_to_pixmap


class PimsImage(QGraphicsPixmapItem):

    def __init__(self, parent):
        super(PimsImage, self).__init__()

        self.setAcceptHoverEvents(True)

        self.parent = parent

    def hoverMoveEvent(self, event):
        self.parent.hover_event.emit(event.lastPos())

    def array_to_pixmap(self, array):
        array = np.swapaxes(pims.to_rgb(array), 0, 1)

        image = pixmap_from_array(array)

        return image

