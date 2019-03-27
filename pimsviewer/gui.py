import sys
import click
from PyQt5.QtCore import QDir, Qt
from PyQt5.QtGui import QImage, QPainter, QPalette, QPixmap
from PyQt5.QtWidgets import (QHBoxLayout, QSlider, QWidget, QAction, QApplication, QFileDialog, QLabel, QMainWindow, QMenu, QMessageBox, QScrollArea, QSizePolicy, QStatusBar, QVBoxLayout, QDockWidget, QPushButton, QStyle, QLineEdit)

from pimsviewer.plugins import AnnotatePlugin
from pimsviewer.image_widget import ImageWidget
from pimsviewer.dimension import Dimension
from pimsviewer.wrapped_reader import WrappedReader
from nd2reader import ND2Reader  # remove after pims update
import pims
import numpy as np

class GUI(QMainWindow):
    name = "Pimsviewer"

    def __init__(self):
        super(GUI, self).__init__()

        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)

        self.createActions()
        self.createMenus()

        self.setWindowTitle(self.name)
        self.resize(500, 400)

        self.image = ImageWidget(parent=self)
        self.setCentralWidget(self.image)
        self.reader = None
        self.dimensions = {}
        self.filename = None

        self.dock_layout, docker = self.init_dock()
        self.addDockWidget(Qt.BottomDockWidgetArea, docker)
        self.init_dimensions()

        self.plugins = []
        self.pluginActions = []
        self.init_plugins()

    def init_plugins(self):
        self.plugins = [AnnotatePlugin(parent=self)]
        
        for plugin in self.plugins:
            action = QAction(plugin.name, self, triggered=plugin.activate)
            self.pluginActions.append(action)
            self.pluginMenu.addAction(action)

    def init_dock(self):
        docker = QDockWidget("Controls", self)
        vbox = QVBoxLayout()

        dock = QWidget()
        dock.setLayout(vbox)
        docker.setWidget(dock)

        return vbox, docker

    def add_to_dock(self, widget):
        self.dock_layout.addWidget(widget)

    def createActions(self):
        self.openAct = QAction("&Open...", self, shortcut="Ctrl+O", triggered=self.open)

        self.exitAct = QAction("E&xit", self, shortcut="Ctrl+Q", triggered=self.close)

        self.zoomInAct = QAction("Zoom &In (25%)", self, shortcut="Ctrl++", enabled=False, triggered=self.zoomIn)

        self.zoomOutAct = QAction("Zoom &Out (25%)", self, shortcut="Ctrl+-", enabled=False, triggered=self.zoomOut)

        self.normalSizeAct = QAction("&Normal Size", self, shortcut="Ctrl+0", enabled=False, triggered=self.normalSize)

        self.fitToWindowAct = QAction("&Fit to Window", self, enabled=False, checkable=True, shortcut="Ctrl+F", triggered=self.fitToWindow, checked=True)

        self.aboutAct = QAction("&About", self, triggered=self.about)

    def createMenus(self):
        self.fileMenu = QMenu("&File", self)
        self.fileMenu.addAction(self.openAct)
        self.fileMenu.addSeparator()
        self.fileMenu.addAction(self.exitAct)

        self.viewMenu = QMenu("&View", self)
        self.viewMenu.addAction(self.zoomInAct)
        self.viewMenu.addAction(self.zoomOutAct)
        self.viewMenu.addAction(self.normalSizeAct)
        self.viewMenu.addSeparator()
        self.viewMenu.addAction(self.fitToWindowAct)

        self.pluginMenu = QMenu("&Plugins", self)

        self.helpMenu = QMenu("&Help", self)
        self.helpMenu.addAction(self.aboutAct)

        self.menuBar().addMenu(self.fileMenu)
        self.menuBar().addMenu(self.viewMenu)
        self.menuBar().addMenu(self.pluginMenu)
        self.menuBar().addMenu(self.helpMenu)

    def updateActions(self):
        self.zoomInAct.setEnabled(not self.fitToWindowAct.isChecked())
        self.zoomOutAct.setEnabled(not self.fitToWindowAct.isChecked())
        self.normalSizeAct.setEnabled(not self.fitToWindowAct.isChecked())

        if not self.fitToWindowAct.isChecked():
            self.zoomInAct.setEnabled(True)
            self.zoomOutAct.setEnabled(True)

    def zoomIn(self):
        self.image.scaleImage(1.25)
        self.refreshPlugins()

    def zoomOut(self):
        self.image.scaleImage(0.8)
        self.refreshPlugins()

    def normalSize(self):
        self.image.scaleImage(1.0, absolute=True)
        self.refreshPlugins()

    def fitToWindow(self):
        fitToWindow = self.fitToWindowAct.isChecked()
        self.image.fitWindow = fitToWindow

        self.image.doResize()
        self.updateActions()

        self.refreshPlugins()

    def about(self):
        QMessageBox.about(self, "About Interactive Tracking",
                "<p><b>Interactive Tracking</b> allows you to track features interactively.</p>" +
                "<p>Created by Ruben Verweij. See <a href='https://github.com/rbnvrw/interactive-tracking'>GitHub</a> for more information.</p>")

    def open(self, fileName=None):
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

            self.fitToWindowAct.setEnabled(True)
            self.updateActions()

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

    def update_dimensions(self):
        sizes = self.reader.sizes

        for dim in sizes:
            self.dimensions[dim].size = sizes[dim]
            self.dimensions[dim].enable()

        # current playing axis
        self.reader.iter_axes = ''

        self.reader.bundle_axes = ''
        if 'c' in self.reader.sizes:
            self.reader.bundle_axes += 'c'
        if 'y' in self.reader.sizes:
            self.reader.bundle_axes += 'y'
        if 'x' in self.reader.sizes:
            self.reader.bundle_axes += 'x'

    def get_current_frame(self):
        frame = self.reader

        for dim in self.dimensions:
            if dim not in self.reader.sizes:
                continue

            dim_obj = self.dimensions[dim]
            if dim_obj.should_set_default_coord():
                self.reader.default_coords[dim] = dim_obj.position
                if dim in self.reader.bundle_axes:
                    self.reader.bundle_axes.remove(dim)

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

        frame = self.reader[i]

        colors = None
        if len(frame.shape) == 3:
            c_ix = np.argmin(frame.shape)
            if c_ix == 2:
                frame = frame.transpose((2, 0, 1))
            colors = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]

        frame = pims.to_rgb(frame, colors=colors)
        return frame

    def refreshPlugins(self):
        for plugin in self.plugins:
            if plugin.active:
                plugin.showFrame(self.image, self.dimensions)

    def showFrame(self):
        if len(self.dimensions) == 0:
            self.update_dimensions()

        image_data = self.get_current_frame()
        self.image.setPixmap(image_data)

        self.refreshPlugins()


@click.command()
@click.option('--filepath', '-f', 'filepath', type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True, resolve_path=True))
def run(filepath):
    app = QApplication(sys.argv)
    gui = GUI()
    if filepath is not None:
        gui.open(filepath)
    gui.show()

    sys.exit(app.exec_())

if __name__ == '__main__':
    run()
