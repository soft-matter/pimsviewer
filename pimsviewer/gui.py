from os import path
import sys
import click
from PyQt5 import uic
from PyQt5.QtCore import QDir, Qt, QMimeData
from PyQt5.QtGui import QImage, QPainter, QPalette, QPixmap, QImageWriter
from PyQt5.QtWidgets import (QHBoxLayout, QSlider, QWidget, QAction, QApplication, QFileDialog, QLabel, QMainWindow, QMenu, QMessageBox, QScrollArea, QSizePolicy, QStatusBar, QVBoxLayout, QDockWidget, QPushButton, QStyle, QLineEdit)

from pimsviewer.example_plugins import AnnotatePlugin, Plugin, ProcessingPlugin
from pimsviewer.imagewidget import ImageWidget
from pimsviewer.dimension import Dimension
from pimsviewer.wrapped_reader import WrappedReader
from pimsviewer.scroll_message_box import ScrollMessageBox
from pimsviewer.utils import get_supported_extensions, get_all_files_in_dir
import pims
import numpy as np

try:
    from nd2reader import ND2Reader  # remove after pims update
except:
    pass

class GUI(QMainWindow):
    name = "Pimsviewer"

    def __init__(self, extra_plugins=[]):
        super(GUI, self).__init__()

        dirname = path.dirname(path.realpath(__file__))
        uic.loadUi(path.join(dirname, 'mainwindow.ui'), self)

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
        self.init_plugins(extra_plugins)

    def init_plugins(self, extra_plugins=[]):
        self.plugins = []

        for plugin_name in extra_plugins:
            extra_plugin = plugin_name(parent=self)
            if isinstance(extra_plugin, Plugin):
                self.plugins.append(extra_plugin)
        
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
        self.actionOpen_next.setEnabled(hasfile)
        self.actionOpen_previous.setEnabled(hasfile)
        self.actionCopy.setEnabled(hasfile)

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

        try:
            html = '<p><strong>Framerate:</strong></p><p><pre>%.3f</pre></p>' % (self.reader.frame_rate)
            items.append(html)
            num_frames = self.reader.sizes['t']
            html = '<p><strong>Duration:</strong></p><p><pre>%.3f s</pre></p>' % (num_frames / self.reader.frame_rate)
            items.append(html)
        except (AttributeError):
            html = '<p><strong>Framerate:</strong></p><p><pre>Unknown</pre></p>'
            items.append(html)
            num_frames = self.reader.sizes['t']
            html = '<p><strong>Duration:</strong></p><p><pre>%d frames</pre></p>' % (num_frames)
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

    def open_next_prev(self):
        direction_next = True
        if self.sender().objectName() == "actionOpen_previous":
            direction_next = False

        supported_extensions = get_supported_extensions()

        current_directory = path.dirname(self.filename)
        file_list = get_all_files_in_dir(current_directory, extensions=supported_extensions)
        if len(file_list) < 2:
            self.statusbar.showMessage('No file found for opening')
            return

        try:
            current_file_index = file_list.index(path.basename(self.filename))
        except ValueError:
            self.statusbar.showMessage('No file found for opening')
            return

        next_index = current_file_index + 1 if direction_next else current_file_index - 1
        try:
            next_file = file_list[next_index]
        except IndexError:
            next_index = 0 if direction_next else -1
            next_file = file_list[next_index]

        self.open(fileName=path.join(current_directory, next_file))

    def copy_image_to_clipboard(self):
        data = QMimeData()
        data.setImageData(self.imageView.image.pixmap())
        app = QApplication.instance()
        app.clipboard().setMimeData(data)

    def close_file(self):
        self.reader.close()
        self.reader = None
        self.filename = None
        self.showFrame()

    def init_dimensions(self):
        for dim in 'tvzcxy':
            self.dimensions[dim] = Dimension(dim, 0)
            self.dimensions[dim].play_event.connect(self.play_event)
            if dim not in ['x', 'y']:
                self.add_to_dock(self.dimensions[dim])
                self.dimensions[dim].playable = True
            if dim in ['c', 'z', 'v']:
                self.dimensions[dim].mergeable = True
            else:
                self.dimensions[dim].mergeable = False
                self.dimensions[dim].merge = False

    def play_event(self, dimension):
        if not self.reader:
            return

        if len(self.reader.iter_axes) > 0:
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

        bundle_axes = ''
        if 'y' in self.reader.sizes:
            bundle_axes += 'y'
        if 'x' in self.reader.sizes:
            bundle_axes += 'x'

        self.reader.bundle_axes = bundle_axes

        if 't' in self.dimensions:
            try:
                self.dimensions['t'].fps = self.reader.frame_rate
            except AttributeError:
                self.statusbar.showMessage('Unable to read frame rate from file')

    def get_current_frame(self):
        self.reader.bundle_axes = 'xy'
        default_coords = {}

        for dim in self.dimensions:
            if dim not in self.reader.sizes:
                continue

            dim_obj = self.dimensions[dim]

            default_coords[dim] = dim_obj.position

            if dim_obj.merge and dim not in self.reader.bundle_axes:
                self.reader.bundle_axes += dim

        self.reader.default_coords = default_coords

        # always one playing axis at a time
        if len(self.reader.iter_axes) > 1:
            self.reader.iter_axes = self.reader.iter_axes[0]

        if len(self.reader.iter_axes) > 0:
            try:
                dim_obj = self.dimensions[self.reader.iter_axes[0]]
                i = dim_obj.position
            except KeyError:
                i = 0
        else:
            i = 0

        try:
            frame = self.reader[i]
        except IndexError:
            self.statusbar.showMessage('Unable to find %s=%d' % (dim_obj.name, i))
            frame = self.reader[0]

        if 'c' in self.reader.bundle_axes:
            cix = self.reader.bundle_axes.index('c')
            if cix != 0:
                frame = np.swapaxes(frame, 0, cix)
                frame = np.swapaxes(frame, 1, 2).copy()

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
@click.option('--example-plugins/--no-example-plugins', default=True, help='Load additional example plugins')
def run(filepath, example_plugins):
    app = QApplication(sys.argv)

    if example_plugins:
        extra_plugins = [AnnotatePlugin, ProcessingPlugin]
    else:
        extra_plugins = []

    gui = GUI(extra_plugins=extra_plugins)
    if filepath is not None:
        gui.open(fileName=filepath)
    gui.show()

    sys.exit(app.exec_())

if __name__ == '__main__':
    run()
