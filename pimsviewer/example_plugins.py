import numpy as np
from collections import deque
from pims.display import to_rgb
from os import path

from PIL import Image, ImageQt
from PyQt5.QtCore import QDir, Qt, QRectF
from PyQt5.QtGui import QImage, QPainter, QPalette, QPixmap
from PyQt5.QtWidgets import (QHBoxLayout, QSlider, QWidget, QAction, QApplication, QFileDialog, QLabel, QMainWindow, QMenu, QMessageBox, QScrollArea, QSizePolicy, QStatusBar, QVBoxLayout, QDockWidget, QPushButton, QStyle, QLineEdit, QDialog, QGraphicsEllipseItem, QCheckBox)

import pandas as pd

from pimsviewer.utils import pixmap_from_array
from pimsviewer.plugins import Plugin

class AnnotatePlugin(Plugin):
    name = 'Annotate plugin'

    def __init__(self, parent=None, positions_df=None):
        super(AnnotatePlugin, self).__init__(parent)

        self.x_name = 'x'
        self.y_name = 'y'
        self.r_name = 'r'

        self.unit_scaling = 1.0
        self.positions_df = positions_df

        self.vbox = QVBoxLayout()
        self.setLayout(self.vbox)

        self.label = QLabel('Annotate Plugin')
        self.vbox.addWidget(self.label)

        self.browseBtn = QPushButton('Open trajectories...')
        self.browseBtn.clicked.connect(self.open)
        self.vbox.addWidget(self.browseBtn)

        self.unitSwitch = QCheckBox('Convert to pixels using scaling')
        self.unitSwitch.stateChanged.connect(self.set_unit_scaling)
        self.unitSwitch.setChecked(True)
        self.vbox.addWidget(self.unitSwitch)

        self.swapXYSwitch = QCheckBox('Swap X and Y columns')
        self.swapXYSwitch.stateChanged.connect(self.swap_xy)
        self.swapXYSwitch.setChecked(False)
        self.vbox.addWidget(self.swapXYSwitch)

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
        if self.positions_df is None:
            return
        self.set_unit_scaling()

        scaleFactor = image_widget.scaleFactor
        self.clearAll(image_widget)
        frame_no = dimensions['t'].position

        selection = self.positions_df[self.positions_df['frame'] == frame_no]

        for i, row in selection.iterrows():
            x = float(row[self.x_name]) * self.unit_scaling
            y = float(row[self.y_name]) * self.unit_scaling

            r = float(row[self.r_name]) * self.unit_scaling
            if np.isnan(r):
                r = 10.0

            ellipse = QGraphicsEllipseItem(self.rect_from_xyr(x, y, r, scaleFactor))
            pen = ellipse.pen()
            pen.setWidth(2)
            pen.setColor(Qt.red)
            ellipse.setPen(pen)
            image_widget.addItemToScene(ellipse)
            self.items.append(ellipse)

    def swap_xy(self):
        if not self.swapXYSwitch.isChecked():
            self.x_name = 'x'
            self.y_name = 'y'
        else:
            self.x_name = 'y'
            self.y_name = 'x'

    def set_unit_scaling(self):
        if not self.unitSwitch.isChecked():
            self.unit_scaling = 1.0
        else:
            if self.app.reader:
                try:
                    self.unit_scaling = 1.0 / self.app.reader.metadata['pixel_microns']
                except:
                    self.unit_scaling = 1.0
                    print('Warning: AnnotatePlugin: file type not implemented for automatic coordinate scaling')

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

class ProcessingPlugin(Plugin):
    name = 'Processing plugin (example)'
    noise_level = 50

    def __init__(self, parent=None):
        super(ProcessingPlugin, self).__init__(parent)

        self.vbox = QVBoxLayout()
        self.setLayout(self.vbox)

        self.vbox.addWidget(QLabel('Example processing plugin'))
        self.vbox.addWidget(QLabel('Add noise:'))

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(10)
        self.slider.setMaximum(100)
        self.slider.setValue(50)
        self.slider.setTickPosition(QSlider.TicksBelow)
        self.slider.setTickInterval(10)
        self.slider.valueChanged.connect(self.update_noise)
        self.vbox.addWidget(self.slider)

    def update_noise(self):
        self.noise_level = self.slider.value()
        self.showFrame(self.parent().imageView, self.parent().dimensions)

    def activate(self):
        super(ProcessingPlugin, self).activate()

        self.showFrame(self.parent().imageView, self.parent().dimensions)

    def showFrame(self, image_widget, dimensions):
        arr = self.parent().get_current_frame()

        arr = arr + np.random.random(arr.shape) * self.noise_level / 100 * arr.max()
        arr = arr / np.max(arr)

        arr = (arr * 255.0).astype(np.uint8)
        
        image = pixmap_from_array(arr)

        image_widget.setPixmap(image)

