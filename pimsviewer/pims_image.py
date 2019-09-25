import pims
from PyQt5.QtCore import QDir, Qt, QSize, QRect, pyqtSignal, QPointF
from PyQt5.QtGui import QImage, QPainter, QPalette, QPixmap, QPen
from PyQt5.QtWidgets import (QAction, QApplication, QFileDialog, QLabel,
                             QMainWindow, QMenu, QMessageBox, QScrollArea,
                             QSizePolicy, QGraphicsPixmapItem)


class PimsImage(QGraphicsPixmapItem):

    def __init__(self, parent):
        super(PimsImage, self).__init__()

        self.setAcceptHoverEvents(True)

        self.parent = parent

    def hoverMoveEvent(self, event):
        self.parent.hover_event.emit(event.lastPos())

    def array_to_pixmap(self, array):
        if len(array.shape) == 2:
            # probably only x, y
            array = pims.to_rgb(array)

        height, width, colors = array.shape

        bytesPerLine = 3 * width

        image = QImage(array, width, height, bytesPerLine, QImage.Format_RGB888)

        return QPixmap(image)
