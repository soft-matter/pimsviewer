from PyQt5.QtCore import QDir, Qt, QSize, QRect
from PyQt5.QtGui import QImage, QPainter, QPalette, QPixmap, QPen
from PyQt5.QtWidgets import (QAction, QApplication, QFileDialog, QLabel,
                             QMainWindow, QMenu, QMessageBox, QScrollArea,
                             QSizePolicy, QGraphicsPixmapItem)


class PimsImage(QGraphicsPixmapItem):
    def __init__(self):
        super(PimsImage, self).__init__()

    def array_to_pixmap(self, array):
        height, width, colors = array.shape
        bytesPerLine = 3 * width

        image = QImage(array, width, height, bytesPerLine, QImage.Format_RGB888)

        return QPixmap(image)
