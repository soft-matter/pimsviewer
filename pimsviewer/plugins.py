import numpy as np
from collections import deque
from pims.display import to_rgb
from os import path

from PIL import Image, ImageQt
from PyQt5.QtCore import QDir, Qt, QRectF
from PyQt5.QtGui import QImage, QPainter, QPalette, QPixmap
from PyQt5.QtWidgets import (QHBoxLayout, QSlider, QWidget, QAction, QApplication, QFileDialog, QLabel, QMainWindow, QMenu, QMessageBox, QScrollArea, QSizePolicy, QStatusBar, QVBoxLayout, QDockWidget, QPushButton, QStyle, QLineEdit, QDialog, QGraphicsEllipseItem)

import pandas as pd

from pimsviewer.utils import pixmap_from_array

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
