import os
import sys
import click
from PyQt5 import uic
from PyQt5.QtCore import QDir, Qt
from PyQt5.QtGui import QImage, QPainter, QPalette, QPixmap, QImageWriter
from PyQt5.QtWidgets import (QHBoxLayout, QSlider, QWidget, QAction, QApplication, QFileDialog, QLabel, QMainWindow, QMenu, QMessageBox, QScrollArea, QSizePolicy, QStatusBar, QVBoxLayout, QDockWidget, QPushButton, QStyle, QLineEdit)

from pimsviewer.plugins import AnnotatePlugin
from pimsviewer.imagewidget import ImageWidget
from pimsviewer.dimension import Dimension
from pimsviewer.wrapped_reader import WrappedReader
from pimsviewer.scroll_message_box import ScrollMessageBox
import pims
import numpy as np

try:
    from nd2reader import ND2Reader  # remove after pims update
except:
    pass

class GUI(QMainWindow):
    name = "Pimsviewer"

    def __init__(self):
        super(GUI, self).__init__()

        dirname = os.path.dirname(os.path.realpath(__file__))
        uic.loadUi(os.path.join(dirname, 'mainwindow.ui'), self)

        self.setWindowTitle(self.name)
        self.setCentralWidget(self.imageView)
        self.setStatusBar(self.statusbar)

        self.imageView.hover_event.connect(self.image_hover_event)
        self.reader = None
        self.dimensions = {}
        self.filename = None

        self.init_dimensions()

        self.plugins = []
        self.pluginActions = []
        self.init_plugins()

    def init_plugins(self):
        self.plugins = [AnnotatePlugin(parent=self)]
        
        for plugin in self.plugins:
            action = QAction(plugin.name, self, triggered=plugin.activate)
            self.pluginActions.append(action)
            self.menuPlugins.addAction(action)

    def add_to_dock(self, widget):
        self.dockLayout.addWidget(widget)

    def updateActions(self):
        hasfile = self.reader is not None
        self.actionClose.setEnabled(hasfile)
        self.actionFile_information.setEnabled(hasfile)
        self.actionSave.setEnabled(hasfile)

        fitWidth = self.actionFit_width.isChecked()
        self.actionZoom_in.setEnabled(not fitWidth)
        self.actionZoom_out.setEnabled(not fitWidth)
        self.actionNormal_size.setEnabled(not fitWidth)

        if not fitWidth:
            self.actionZoom_in.setEnabled(True)
            self.actionZoom_out.setEnabled(True)

    def zoomIn(self):
        self.imageView.scaleImage(1.25)
        self.refreshPlugins()

    def zoomOut(self):
        self.imageView.scaleImage(0.8)
        self.refreshPlugins()

    def normalSize(self):
        self.imageView.scaleImage(1.0, absolute=True)
        self.refreshPlugins()

    def fitToWindow(self):
        fitToWindow = self.actionFit_width.isChecked()
        self.imageView.fitWindow = fitToWindow

        self.imageView.doResize()
        self.updateActions()

        self.refreshPlugins()

    def about(self):
        QMessageBox.about(self, "About Pimsviewer",
                "<p>Viewer for Python IMage Sequence (PIMS).</p>" +
                "<p>See <a href='https://github.com/soft-matter/pimsviewer'>the Pimsviewer Github page</a> for more information.</p>")

    def export(self):
        allowed_formats = QImageWriter.supportedImageFormats()
        allowed_formats = [str(f.data(), encoding='utf-8') for f in allowed_formats]
        filter_string = 'Images ('
        for f in allowed_formats:
            filter_string += '*.%s ' % f
        filter_string = filter_string[:-1] + ')'

        fileName, _ = QFileDialog.getSaveFileName(self, "Export File", QDir.currentPath(), filter_string)
        if not fileName:
            return

        self.imageView.image.pixmap().save(fileName)
        self.statusbar.showMessage('Image exported to %s' % fileName)

    def show_file_info(self):
        items = []

        # Metadata
        for prop in self.reader.metadata:
            html = '<p><strong>%s:</strong></p><p><pre>%s</pre></p>' % (prop, self.reader.metadata[prop])
            items.append(html)

        # File path
        html = '<p><strong>Filename:</strong></p><p>%s</p>' % (self.filename)
        items.append(html)

        # Reader
        if isinstance(self.reader, WrappedReader):
            reader_type = type(self.reader.reader).__name__
        else:
            reader_type = type(self.reader).__name__
        html = '<p><strong>PIMS reader:</strong></p><p>%s</p><p><pre>%s</pre></p>' % (reader_type, self.reader.__repr__())
        items.append(html)

        ScrollMessageBox(items, parent=self)

    def open(self, checked=False, fileName=None):
        if self.reader is not None:
            self.close_file()

        if fileName is None:
            fileName, _ = QFileDialog.getOpenFileName(self, "Open File", QDir.currentPath())

        if fileName:
            try:
                self.reader = WrappedReader(pims.open(fileName))
            except:
                QMessageBox.critical(self, "Error", "Cannot load %s." % fileName)
                return

            self.filename = fileName
            self.update_dimensions()
            self.showFrame()

            self.actionFit_width.setEnabled(True)
            self.updateActions()

    def close_file(self):
        self.reader.close()
        self.reader = None
        self.filename = None
        self.showFrame()

    def init_dimensions(self):
        for dim in 'tzcxy':
            self.dimensions[dim] = Dimension(dim, 0)
            self.dimensions[dim].play_event.connect(self.play_event)
            if dim not in ['x', 'y']:
                self.add_to_dock(self.dimensions[dim])
                self.dimensions[dim].playable = True
            if dim in ['c']:
                self.dimensions[dim].mergeable = True

    def play_event(self, dimension):
        current_player = self.reader.iter_axes[0]
        if dimension.name != current_player:
            self.dimensions[current_player].playing = False

        self.reader.iter_axes = dimension.name
        self.showFrame()

    def image_hover_event(self, point):
        self.statusbar.showMessage('[%.1f, %.1f]' % (point.x(), point.y()))

    def update_dimensions(self):
        sizes = self.reader.sizes

        for dim in self.dimensions:
            if dim in sizes and sizes[dim] > 1:
                self.dimensions[dim].size = sizes[dim]
                self.dimensions[dim].enable()
            else:
                if dim in sizes:
                    self.dimensions[dim].size = sizes[dim]
                else:
                    self.dimensions[dim].size = 0

                self.dimensions[dim].disable()
                self.dimensions[dim].hide()

        # current playing axis
        self.reader.iter_axes = ''

        self.reader.bundle_axes = ''
        if 'y' in self.reader.sizes:
            self.reader.bundle_axes += 'y'
        if 'x' in self.reader.sizes:
            self.reader.bundle_axes += 'x'

    def get_current_frame(self):
        self.reader.default_coords = {}
        self.reader.bundle_axes = 'yx'
        for dim in self.dimensions:
            if dim not in self.reader.sizes:
                continue

            dim_obj = self.dimensions[dim]
            self.reader.default_coords[dim] = dim_obj.position
            if dim_obj.merge and dim not in self.reader.bundle_axes:
                self.reader.bundle_axes += dim

        # always one playing axis at a time
        if len(self.reader.iter_axes) == 0:
            self.reader.iter_axes = 't'
        elif len(self.reader.iter_axes) != 1:
            self.reader.iter_axes = self.reader.iter_axes[0]

        try:
            dim_obj = self.dimensions[self.reader.iter_axes[0]]
            i = dim_obj.position
        except KeyError:
            i = 0

        try:
            frame = self.reader[i]
        except IndexError:
            self.statusbar.showMessage('Unable to find %s=%d' % (dim_obj.name, i))
            frame = self.reader[0]

        return frame

    def refreshPlugins(self):
        for plugin in self.plugins:
            if plugin.active:
                plugin.showFrame(self.imageView, self.dimensions)

    def showFrame(self):
        if self.reader is None:
            self.imageView.setPixmap(None)
            return

        if len(self.dimensions) == 0:
            self.update_dimensions()

        image_data = self.get_current_frame()
        for bdim in self.reader.bundle_axes:
            if bdim in ['x', 'y']:
                continue
            image_data = self.dimensions[bdim].merge_image_over_dimension(image_data)

        self.imageView.setPixmap(image_data)

        self.refreshPlugins()


@click.command()
@click.argument('filepath', required=False, type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True, resolve_path=True))
def run(filepath):
    app = QApplication(sys.argv)
    gui = GUI()
    if filepath is not None:
        gui.open(fileName=filepath)
    gui.show()

    sys.exit(app.exec_())

if __name__ == '__main__':
    run()
