from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import six
import os
from functools import partial
from itertools import chain

import numpy as np
from slicerator import pipeline
from pims import FramesSequence, FramesSequenceND

from pimsviewer.widgets import (CheckBox, DockWidget, VideoTimer, Slider)
from pimsviewer.qt import (Qt, QtWidgets, QtGui, QtCore, Signal,
                           init_qtapp, start_qtapp)
from pimsviewer.display import Display, DisplayMPL
from pimsviewer.utils import (FramesSequence_Wrapper, recursive_subclasses,
                              to_rgb_uint8)


class Viewer(QtWidgets.QMainWindow):
    """Viewer for displaying image sequences from pims readers.

    Parameters
    ----------
    reader : pims reader, optional
        Reader that loads images to be displayed.

    Notes
    -----
    The Viewer was partly based on `skimage.viewer.CollectionViewer`
    """
    dock_areas = {'top': Qt.TopDockWidgetArea,
                  'bottom': Qt.BottomDockWidgetArea,
                  'left': Qt.LeftDockWidgetArea,
                  'right': Qt.RightDockWidgetArea}
    _dropped = Signal(list)
    original_image_changed = Signal()

    def __init__(self, reader=None, width=800, height=600):
        self.pipelines = []
        self.plugins = []
        self.reader = None
        self.original_image = None
        self.renderer = None
        self.sliders = dict()
        self.channel_tabs = None
        self.slider_dock = None
        self.is_multichannel = False
        self.is_playing = False
        self.mpp = None
        self._index = dict()

        # Start main loop
        init_qtapp()
        super(Viewer, self).__init__()

        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle("Python IMage Sequence Viewer")

        open_with_menu = QtWidgets.QMenu('Open with', self)
        for cls in set(chain(recursive_subclasses(FramesSequence),
                             recursive_subclasses(FramesSequenceND))):
            open_with_menu.addAction(cls.__name__,
                                     partial(self.open_file, reader_cls=cls))

        self.file_menu = QtWidgets.QMenu('&File', self)
        self.file_menu.addAction('Open file', self.open_file,
                                 Qt.CTRL + Qt.Key_O)
        self.file_menu.addMenu(open_with_menu)
        self.file_menu.addAction('Quit', self.close,
                                 Qt.CTRL + Qt.Key_Q)
        self.menuBar().addMenu(self.file_menu)

        self.view_menu = QtWidgets.QMenu('&View', self)
        for cls in recursive_subclasses(Display):
            if cls.available:
                self.view_menu.addAction(cls.name,
                                         partial(self.update_display,
                                                 display_class=cls))
        self.menuBar().addMenu(self.view_menu)

        self.pipeline_menu = QtWidgets.QMenu('&Pipelines', self)
        from pimsviewer.plugins import ViewerPipeline
        for pipeline_obj in ViewerPipeline.instances:
            self.pipeline_menu.addAction(pipeline_obj.name,
                                         partial(self.add_plugin,
                                                 pipeline_obj))
        self.menuBar().addMenu(self.pipeline_menu)

        self.main_widget = QtWidgets.QWidget(self)
        self.setCentralWidget(self.main_widget)
        self.main_layout = QtWidgets.QGridLayout(self.main_widget)

        self.show_status_message = self.statusBar().showMessage

        self.resize(width, height)

        self.setAcceptDrops(True)
        self._dropped.connect(self._open_dropped)

        self._timer = VideoTimer(self)
        if reader is not None:
            self.update_reader(reader)

    def open_file(self, filename=None, reader_cls=None):
        """Open image file and display in viewer."""
        if filename is None:
            try:
                cur_dir = os.path.dirname(self.reader.filename)
            except AttributeError:
                cur_dir = ''
            filename = QtGui.QFileDialog.getOpenFileName(directory=cur_dir)
            if isinstance(filename, tuple):
                # Handle discrepancy between PyQt4 and PySide APIs.
                filename = filename[0]
        if filename is None or len(filename) == 0:
            return
        import pims
        if reader_cls is None:
            reader = pims.open(filename)
        else:
            reader = reader_cls(filename)
        if self.reader is not None:
            self.close_reader()
        self.update_reader(reader)
        self.show_status_message('Opened {}'.format(filename))

    def update_reader(self, reader):
        """Load a new reader into the Viewer."""
        if not isinstance(reader, FramesSequenceND):
            reader = FramesSequence_Wrapper(reader)
        self.reader = reader
        self.reader.iter_axes = ''
        index = reader.default_coords.copy()

        # try to readout calibration
        try:
            mpp = reader.calibration
        except AttributeError:
            mpp = 1.
        if mpp is None:
            mpp = 1.
        if 'z' in self.reader.sizes:
            try:
                mppZ = reader.calibrationZ
            except AttributeError:
                mppZ = mpp
            self.mpp = (mppZ, mpp, mpp)
        else:
            self.mpp = (mpp, mpp)

        # add color tabs
        if 'c' in reader.sizes:
            self.is_multichannel = True
            self.channel_tabs = QtWidgets.QTabBar(self)
            self.main_layout.addWidget(self.channel_tabs, 1, 0)
            self.channel_tabs.addTab('all')
            for c in range(reader.sizes['c']):
                self.channel_tabs.addTab(str(c))
                self.channel_tabs.setShape(QtWidgets.QTabBar.RoundedSouth)
                self.channel_tabs.currentChanged.connect(self.channel_tab_callback)
        else:
            self.is_multichannel = False

        # add sliders
        self.sliders = dict()
        for axis in reader.sizes:
            if axis in ['x', 'y', 'c'] or reader.sizes[axis] <= 1:
                continue
            self.sliders[axis] = Slider(axis, low=0, high=reader.sizes[axis] - 1,
                                        value=index[axis], update_on='release',
                                        value_type='int',
                                        callback=self.update_index)

        if len(self.sliders) > 0:
            slider_widget = QtWidgets.QWidget()
            slider_layout = QtWidgets.QGridLayout(slider_widget)
            for i, axis in enumerate(self.sliders):
                slider_layout.addWidget(self.sliders[axis], i, 0)
                if axis == 't':
                    checkbox = CheckBox('play', self.is_playing,
                                        callback=self.play_callback)
                    slider_layout.addWidget(checkbox, i, 1)

            self.slider_dock = QtWidgets.QDockWidget()
            self.slider_dock.setWidget(slider_widget)
            self.slider_dock.setWindowTitle('Axes sliders')
            self.slider_dock.setFeatures(QtGui.QDockWidget.DockWidgetFloatable |
                                         QtGui.QDockWidget.DockWidgetMovable)
            self.addDockWidget(Qt.BottomDockWidgetArea, self.slider_dock)

        self.update_display()
        self.index = index

    def close_reader(self):
        if self.is_playing:
            self.stop()
        self.reader.close()
        self.renderer.close()
        if self.slider_dock is not None:
            self.slider_dock.close()
        if self.channel_tabs is not None:
            self.channel_tabs.close()

    def update_display(self, display_class=None):
        """Change display mode."""
        if display_class is None:
            display_class = DisplayMPL

        shape = [self.reader.sizes['y'], self.reader.sizes['x']]
        if display_class.ndim == 3:
            try:
                shape = [self.reader.sizes['z']] + shape
            except KeyError:
                raise KeyError('z axis does not exist: cannot display in 3D')

        if self.renderer is not None:
            self.renderer.close()
        self.renderer = display_class(shape, self.mpp)

        # connect the statusbar, only for matplotlib display mode
        if hasattr(self.renderer, 'connect_event'):
            self.renderer.connect_event('motion_notify_event',
                                        self._update_mouse_position)

        self.renderer.widget.setSizePolicy(QtGui.QSizePolicy.Ignored,
                                           QtGui.QSizePolicy.Ignored)
        self.renderer.widget.updateGeometry()
        self.main_layout.addWidget(self.renderer.widget, 0, 0)
        #self.update_index()

    def update_reader_axes(self):
        """Make sure that the reader bundle_axes settings are correct"""
        try:
            ndim = self.renderer.ndim
        except AttributeError:
            ndim = 2
        if ndim == 3 and 'z' not in self.reader.sizes:
            raise ValueError('z axis does not exist: cannot display in 3D')
        if self.is_multichannel and 'c' not in self.reader.sizes:
            raise ValueError('c axis does not exist: cannot display multicolor')

        bundle_axes = ''
        if self.is_multichannel:
            bundle_axes += 'c'
        if ndim == 3:
            bundle_axes += 'z'
        self.reader.bundle_axes = bundle_axes + 'yx'

    def update_index(self, name, value):
        new_index = self.index.copy()
        new_index[name] = value
        self.index = new_index

    def update_image(self):
        """Update the image that is being viewed."""
        if self.original_image is None:
            return
        image = self.original_image.copy()
        for func in self.pipelines:
            image = func(image)
        self.image = image

    def update_pipeline(self, index, func):
        """This is called by the ViewerPipeline to update its effect."""
        self.pipelines[index] = func
        self.update_image()

    @property
    def index(self):
        return self._index
    @index.setter
    def index(self, index):
        for key in index:
            if key not in self.reader.sizes:
                return ValueError("Dimension '{}' not in reader".format(key))
            # clip value if necessary
            if index[key] < 0:
                index[key] = 0
            elif index[key] >= self.reader.sizes[key]:
                index[key] = self.reader.sizes[key] - 1
        try:
            if all((self._index[key] == index[key] for key in index)):
                return  # do nothing when no coordinate was changed
        except KeyError:
            pass  # but continue when a coordinate did not exist
        self._index.update(index)
        self.update_reader_axes()
        for name in self.sliders:
            self.sliders[name].val = index[name]
        self.reader.default_coords.update(index)
        image = self.reader[0]
        if 't' in index:
            image.frame_no = index['t']
        self.original_image = image
        self.update_image()

    @property
    def image(self):
        """The image that is being displayed"""
        return self._img

    @image.setter
    def image(self, image):
        self._img = image
        self.renderer.image = to_rgb_uint8(image, autoscale=True)
        self.original_image_changed.emit()

    def channel_tab_callback(self, index):
        """Callback function for channel tabs."""
        self.is_multichannel = index == 0
        if index > 0:  # monochannel: update channel field
            self.update_index('c', index - 1)  # because 0 is multichannel
        else:  # just update image
            self.update_image()

    def play_callback(self, name, value):
        """Callback function for play checkbox."""
        if value == self.is_playing:
            return
        if value:
            self.play()
        else:
            self.stop()

    def play(self, fps=None):
        """Start the movie."""
        if fps is None:
            try:
                self._timer.fps = self.reader.frame_rate
            except AttributeError:
                self._timer.fps = 25.

        self._timer.start(self.index['t'], self.reader.sizes['t'])
        self._timer.next_frame.connect(lambda x: self.update_index('t', x))
        self.is_playing = True

    def stop(self):
        """Stop the movie."""
        self._timer.stop()
        self.is_playing = False

    def add_plugin(self, plugin):
        """Add Plugin to the Viewer"""
        plugin.attach(self)

        if plugin.dock:
            location = self.dock_areas[plugin.dock]
            dock_location = Qt.DockWidgetArea(location)
            dock = DockWidget()
            dock.setWidget(plugin)
            dock.setWindowTitle(plugin.name)
            dock.close_event_signal.connect(plugin.close)
            dock.setSizePolicy(QtGui.QSizePolicy.Fixed,
                               QtGui.QSizePolicy.MinimumExpanding)
            self.addDockWidget(dock_location, dock)

    def __add__(self, plugin):
        self.add_plugin(plugin)
        return self

    def closeEvent(self, event):
        # obtain the result values before everything is closed
        result = [None] * (len(self.pipelines) + 1)
        result[0] = self.reader
        for i, func in enumerate(self.pipelines):
            result[i + 1] = pipeline(func)(result[i])
        self._result_value = result

        super(Viewer, self).closeEvent(event)

    def show(self, main_window=True):
        """Show Viewer and attached ViewerPipelines."""
        self.move(0, 0)
        for p in self.plugins:
            p.show()
        super(Viewer, self).show()
        self.activateWindow()
        self.raise_()
        if main_window:
            start_qtapp()

        return self._result_value

    def _update_mouse_position(self, event):
        if event.inaxes and event.inaxes.get_navigate():
            x = int(event.xdata + 0.5)
            y = int(event.ydata + 0.5)
            try:
                if self.is_multichannel:
                    val = self.image[:, y, x]
                else:
                    val = self.image[y, x]
                msg = "%4s @ [%4s, %4s]" % (val, x, y)
            except IndexError:
                msg = ""
            self.show_status_message(msg)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls:
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls:
            event.setDropAction(QtCore.Qt.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls:
            event.setDropAction(QtCore.Qt.CopyAction)
            event.accept()
            links = []
            for url in event.mimeData().urls():
                links.append(str(url.toLocalFile()))
            self._dropped.emit(links)
        else:
            event.ignore()

    def _open_dropped(self, links):
        for fn in links:
            if os.path.exists(fn):
                self.open_file(fn)
                break

    def keyPressEvent(self, event):
        if type(event) == QtWidgets.QKeyEvent:
            key = event.key()
            # Number keys (code: 0 = key 48, 9 = key 57) move to deciles
            if key in [QtCore.Qt.Key_N, QtCore.Qt.Key_Right]:
                self.update_index('t', self.index['t'] + 1)
                event.accept()
            elif key in [QtCore.Qt.Key_P, QtCore.Qt.Key_Left]:
                self.update_index('t', self.index['t'] - 1)
                event.accept()
            elif (key == QtCore.Qt.Key_R):
                index = np.random.randint(0, self.reader.sizes['t'] - 1)
                self.update_index('t', index)
                event.accept()
            elif key == QtCore.Qt.Key_Space:
                if self.is_playing:
                    self.stop()
                else:
                    self.play()
                event.accept()
            elif self.is_playing:
                if key == QtCore.Qt.Key_Plus:
                    self._timer.fps *= 1.2
                elif key == QtCore.Qt.Key_Minus:
                    self._timer.fps *= 0.8
                elif key == QtCore.Qt.Key_Equal:
                    try:
                        self._timer.fps = self.reader.frame_rate
                    except AttributeError:
                        self._timer.fps = 25.
            else:
                event.ignore()
        else:
            event.ignore()

    def wheelEvent(self, event):
        if 'z' in self.index:
            new_z = self.index['z'] + int(event.delta() // 120)
            if new_z < 0:
                new_z = 0
            if new_z >= self.reader.sizes['z'] - 1:
                new_z = self.reader.sizes['z'] - 1
            self.update_index('z', new_z)


class Plugin(QtWidgets.QDialog):
    def __init__(self, height=0, width=400, dock='bottom'):
        init_qtapp()
        super(Plugin, self).__init__()

        self.dock = dock

        self.image_viewer = None

        self.setWindowTitle(self.name)
        self.layout = QtWidgets.QGridLayout(self)
        self.resize(width, height)
        self.row = 0

        self.arguments = []
        self.keyword_arguments = {}

    def attach(self, image_viewer):
        """Attach the Plugin to an ImageViewer."""
        self.setParent(image_viewer)
        self.setWindowFlags(QtCore.Qt.Dialog)
        self.image_viewer = image_viewer

    def add_widget(self, widget):
        """Add widget to pipeline.

        Alternatively, you can use simple addition to add widgets:

            plugin += Slider('param_name', low=0, high=100)

        Widgets can adjust arguments of the pipeline function, as specified by
        the Widget's `ptype`.
        """
        if widget.ptype == 'kwarg':
            name = widget.name.replace(' ', '_')
            self.keyword_arguments[name] = widget
            widget.callback = self.process
        elif widget.ptype == 'arg':
            self.arguments.append(widget)
            widget.callback = self.process
        widget.plugin = self
        self.layout.addWidget(widget, self.row, 0)
        self.row += 1

    def __add__(self, widget):
        self.add_widget(widget)
        return self

    def process(self, *widget_arg):
        pass

    def _get_value(self, param):
        # If param is a widget, return its `val` attribute.
        return param if not hasattr(param, 'val') else param.val

    def show(self, main_window=True):
        """Show plugin."""
        super(Plugin, self).show()
        self.activateWindow()
        self.raise_()
