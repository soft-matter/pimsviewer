import numpy as np
from collections import deque
from pims.display import to_rgb
from os import path

from PyQt5.QtCore import QDir, Qt, QRectF
from PyQt5.QtGui import QImage, QPainter, QPalette, QPixmap
from PyQt5.QtWidgets import (QHBoxLayout, QSlider, QWidget, QAction, QApplication, QFileDialog, QLabel, QMainWindow, QMenu, QMessageBox, QScrollArea, QSizePolicy, QStatusBar, QVBoxLayout, QDockWidget, QPushButton, QStyle, QLineEdit, QDialog, QGraphicsEllipseItem)

import pandas as pd

class Plugin(QDialog):
    name = 'Plugin'
    _active = False

    def __init__(self, parent=None):
        super(Plugin, self).__init__(parent)
        self.app = parent

    def activate(self):
        self.active = True
        self.show()

    @property
    def active(self):
        return self._active

    @active.setter
    def active(self, active):
        self._active = bool(active)

    def showFrame(self, image_widget):
        pass

class AnnotatePlugin(Plugin):
    name = 'Annotate plugin'

    def __init__(self, parent=None, positions_df=None):
        super(AnnotatePlugin, self).__init__(parent)

        self.positions_df = positions_df

        self.vbox = QVBoxLayout()
        self.setLayout(self.vbox)

        self.vbox.addWidget(QLabel('Annotate Plugin'))

        browseBtn = QPushButton('Open trajectories...')
        browseBtn.clicked.connect(self.open)
        self.vbox.addWidget(browseBtn)

        self.items = []

    def clearAll(self, image_widget):
        for item in self.items:
            image_widget.removeItemFromScene(item)

        self.items = []

    def rect_from_xyr(self, x, y, r, scaleFactor):
        x_top_left = (x - r)*scaleFactor
        y_top_left = (y - r)*scaleFactor
        size = 2.0*r*scaleFactor
        return QRectF(x_top_left, y_top_left, size, size)

    def showFrame(self, image_widget, dimensions):
        scaleFactor = image_widget.scaleFactor
        self.clearAll(image_widget)
        frame_no = dimensions['t'].position

        selection = self.positions_df[self.positions_df['frame'] == frame_no]

        for i, row in selection.iterrows():
            x = float(row['x'])
            y = float(row['y'])
            r = float(row['r'])
            ellipse = QGraphicsEllipseItem(self.rect_from_xyr(x, y, r, scaleFactor))
            pen = ellipse.pen()
            pen.setWidth(2)
            pen.setColor(Qt.red)
            ellipse.setPen(pen)
            image_widget.addItemToScene(ellipse)
            self.items.append(ellipse)

    def open(self):
        currentDir = QDir.currentPath()
        if self.app is not None:
            parentFile = self.app.filename
            currentDir = path.dirname(parentFile)

        fileName, _ = QFileDialog.getOpenFileName(self, "Open trajectories", currentDir)
        if fileName:
            try:
                self.positions_df = pd.read_csv(fileName)
            except Exception as exception:
                QMessageBox.critical(self, "Error", "Cannot load %s: %s" % (fileName, exception))
                return

        if self.app is not None:
            self.app.refreshPlugins()



