import pims
import numpy as np
from PyQt5.QtCore import QDir, Qt, QSize, QRectF, pyqtSignal, QPointF
from PyQt5.QtGui import QImage, QPainter, QPalette, QPixmap
from PyQt5.QtWidgets import (QAction, QApplication, QFileDialog, QLabel, QMainWindow, QMenu, QMessageBox, QScrollArea, QSizePolicy, QGraphicsView, QGraphicsScene)

from pimsviewer.pims_image import PimsImage
from pimsviewer.utils import image_to_pixmap

class ImageWidget(QGraphicsView):

    hover_event = pyqtSignal(QPointF)

    def __init__(self, parent=None):
        super(ImageWidget, self).__init__(parent)

        self.scene = QGraphicsScene(self)
        self.scene.setSceneRect(QRectF())
        self.setScene(self.scene)

        self.image = PimsImage(self)
        self.scene.addItem(self.image)

        self.setDragMode(QGraphicsView.ScrollHandDrag)

        self.fitWindow = True

        self.doResize()

    def addItemToScene(self, item):
        self.scene.addItem(item)

    def removeItemFromScene(self, item):
        self.scene.removeItem(item)

    def setPixmap(self, pixmap):
        if pixmap is None:
            self.image.setVisible(False)
            return

        if isinstance(pixmap, QImage):
            pixmap = image_to_pixmap(image)

        if not self.image.isVisible():
            self.image.setVisible(True)

        if not isinstance(pixmap, QPixmap):
            pixmap = self.image.array_to_pixmap(pixmap)

        self.image.setPixmap(pixmap)
        self.doResize()

    def resizeEvent(self, event):
        super(ImageWidget, self).resizeEvent(event)
        self.doResize()

    def doResize(self):
        self.scaleImage(1.0)

    def adjustSize(self):
        super(ImageWidget, self).adjustSize()
        self.doResize()

    def scaleImage(self, factor, absolute=False):
        if not absolute:
            factor = self.image.scale() * factor

        if not self.fitWindow:
            self.image.setScale(factor)
        else:
            self.fitInView(self.image, Qt.KeepAspectRatio)

    @property
    def scaleFactor(self):
        return self.image.scale()


