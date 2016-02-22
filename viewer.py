from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import six
import os
from functools import partial
from itertools import chain
import warnings

import numpy as np
import pims
from pims import FramesSequence, FramesSequenceND, Frame

from pimsviewer.widgets import (CheckBox, DockWidget, VideoTimer, Slider,
                                QWidgetMinSize)
from pimsviewer.qt import (Qt, QtWidgets, QtGui, QtCore, Signal,
                           init_qtapp, start_qtapp, rgb_view)
from pimsviewer.display import Display, DisplayMPL
from pimsviewer.utils import (wrap_frames_sequence, recursive_subclasses,
                              to_rgb_uint8)

try:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from moviepy.editor import VideoClip
except ImportError:
    VideoClip = None


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
    image_changed = Signal()
    undo = Signal()
    redo = Signal()

    def __init__(self, reader=None):
        self.plugins = []
        self._readers = []
        self._img = None
        self.renderer = None
        self.sliders = dict()
        self.channel_tabs = None
        self.slider_dock = None
        self.is_multichannel = False
        self.is_playing = False
        self._index = dict()
        self.return_val = []
        self._close_reader = True

        # Start main loop
        init_qtapp()
        super(Viewer, self).__init__()

        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle("Python IMage Sequence Viewer")

        open_with_menu = QtWidgets.QMenu('Open with', self)
        for cls in set(chain(recursive_subclasses(FramesSequence),
                             recursive_subclasses(FramesSequenceND))):
            if hasattr(cls, 'no_reader'):
                continue
            open_with_menu.addAction(cls.__name__,
                                     partial(self.open_file, reader_cls=cls))

        self.file_menu = QtWidgets.QMenu('&File', self)
        self.file_menu.addAction('Open', self.open_file,
                                 Qt.CTRL + Qt.Key_O)
        self.file_menu.addMenu(open_with_menu)
        self.file_menu.addAction('Close', self.close_reader)
        self.file_menu.addAction('Save', self.save_file,
                                 Qt.CTRL + Qt.Key_S)
        self.file_menu.addAction('Copy', self.to_clipboard,
                                 Qt.CTRL + Qt.Key_C)
        self.file_menu.addAction('Quit', self.close,
                                 Qt.CTRL + Qt.Key_Q)
        self.menuBar().addMenu(self.file_menu)

        self.view_menu = QtWidgets.QMenu('&View', self)
        for cls in recursive_subclasses(Display):
            if cls.available:
                self.view_menu.addAction(cls.name,
                                         partial(self.update_display,
                                                 display_class=cls))
        resize_menu = QtWidgets.QMenu('&Resize', self)
        resize_menu.addAction('33 %', partial(self.resize_display, factor=1/3))
        resize_menu.addAction('50 %', partial(self.resize_display, factor=1/2))
        resize_menu.addAction('100 %', partial(self.resize_display, factor=1))
        resize_menu.addAction('200 %', partial(self.resize_display, factor=2))
        resize_menu.addAction('300 %', partial(self.resize_display, factor=3))
        self.view_menu.addMenu(resize_menu)
        self.menuBar().addMenu(self.view_menu)

        self.pipeline_menu = QtWidgets.QMenu('&Pipelines', self)
        from pimsviewer.plugins import PipelinePlugin
        for pipeline_obj in PipelinePlugin.instances:
            self.pipeline_menu.addAction(pipeline_obj.name,
                                         partial(self.add_plugin,
                                                 pipeline_obj))
        self.menuBar().addMenu(self.pipeline_menu)

        self.main_widget = QtWidgets.QWidget(self)
        self.setCentralWidget(self.main_widget)
        self.setMinimumSize(200, 200)
        self.setSizePolicy(QtGui.QSizePolicy.Preferred,
                           QtGui.QSizePolicy.Preferred)
        self.main_layout = QtWidgets.QGridLayout(self.main_widget)

        self.setAcceptDrops(True)
        self._dropped.connect(self._open_dropped)

        self._status_bar = self.statusBar()

        self._timer = VideoTimer(self)
        if reader is not None:
            self.update_reader(reader)

    def resize_display(self, w=None, h=None, factor=1):
        h_im, w_im = self.image.shape[-2:]
        h_im *= factor
        w_im *= factor
        if h is None and w is None:
            h = h_im
            w = w_im
        elif h is None:
            h = int(w * h_im / w_im)
        elif w is None:
            w = int(h * w_im / h_im)
        self.renderer.resize(w, h)

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
        if reader_cls is None:
            reader = pims.open(filename)
        else:
            reader = reader_cls(filename)
        if self.reader is not None:
            self.close_reader()
        self.update_reader(reader)
        self.status = 'Opened {}'.format(filename)

    @property
    def reader(self):
        if len(self._readers) == 0:
            return None
        else:
            return self._readers[-1]

    def update_reader(self, reader):
        """Load a new reader into the Viewer."""
        if not isinstance(reader, FramesSequenceND):
            reader = wrap_frames_sequence(reader)
        self._readers = [reader]
        reader.iter_axes = ''
        self._index = reader.default_coords.copy()

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
            self.sliders[axis] = Slider(axis, low=0, high=reader.sizes[axis]-1,
             value=self._index[axis], update_on='release', value_type='int',
             callback=lambda x, y: self.set_index(y, x))

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

        # set playback speed
        try:
            self._timer.fps = self.reader.frame_rate
        except AttributeError:
            self._timer.fps = 25.

        self.update_display()
        self.resize_display()

    def close_reader(self):
        if self.reader is None:
            return
        if self.is_playing:
            self.stop()
        self.reader.close()
        self._readers = []
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
        self.renderer = display_class(self, shape)

        self.renderer.widget.setSizePolicy(QtGui.QSizePolicy.Expanding,
                                           QtGui.QSizePolicy.Expanding)
        self.renderer.widget.updateGeometry()
        self.main_layout.addWidget(self.renderer.widget, 0, 0)
        self.renderer.widget.keyPressEvent = self.keyPressEvent
        self.update_image()

    def update_image(self):
        """Update the image that is being viewed."""
        if self.renderer.ndim == 3 and 'z' not in self.reader.sizes:
            raise ValueError('z axis does not exist: cannot display in 3D')
        if self.is_multichannel and 'c' not in self.reader.sizes:
            raise ValueError('c axis does not exist: cannot display multicolor')

        # Make sure that the reader bundle_axes settings are correct
        bundle_axes = ''
        if self.is_multichannel:
            bundle_axes += 'c'
        if self.renderer.ndim == 3:
            bundle_axes += 'z'
        self.reader.bundle_axes = bundle_axes + 'yx'

        # Update slider positions
        for name in self.sliders:
            self.sliders[name].val = self._index[name]

        # Update image
        self.reader.default_coords.update(self._index)
        image = self.reader[0]
        if 't' in self._index:
            image.frame_no = self._index['t']
        self.image = image

    def update_view(self):
        """Emit image to display."""
        if self.image is None:
            return
        self.renderer.image = to_rgb_uint8(self.image, autoscale=True)
        self.image_changed.emit()

    @property
    def index(self):
        return self._index.copy()  # copy the dict to make it read only

    def set_index(self, value=0, name='t'):
        if name not in self.reader.sizes:
            return ValueError("Dimension '{}' not in reader".format(name))
        # clip value if necessary
        if value < 0:
            value = 0
        elif value >= self.reader.sizes[name]:
            value = self.reader.sizes[name] - 1
        try:
            if self._index[name] == value:
                return  # do nothing when no coordinate was changed
        except KeyError:
            pass  # but continue when a coordinate did not exist
        if self.is_playing and name == 't':
            self._timer.reset(value)
        self._index[name] = value
        self.update_image()

    @property
    def image(self):
        """The image that is being displayed"""
        return self._img

    @image.setter
    def image(self, image):
        self._img = image
        self.update_view()

    @property
    def sizes(self):
        return self.reader.sizes.copy()

    @property
    def axes(self):
        return self.reader.axes.copy()

    def channel_tab_callback(self, index):
        """Callback function for channel tabs."""
        if index == 0 and self.is_multichannel:
            return  # do nothing: already multichannel
        elif not self.is_multichannel and (self._index['c'] == index - 1):
            return  # do nothing: correct monochannel
        self.is_multichannel = index == 0
        if index > 0:  # monochannel: update channel field
            self._index['c'] = index - 1  # because 0 is multichannel
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
        self._timer.start(self._index['t'], self.reader.sizes['t'])
        self._timer.next_frame.connect(lambda x: self.set_index(x))
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

        return self.return_val

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

    @property
    def status(self):
        return None
    @status.setter
    def status(self, value):
        self._status_bar.showMessage(str(value))

    def keyPressEvent(self, event):
        if type(event) == QtWidgets.QKeyEvent:
            key = event.key()
            if key in range(0x30, 0x39 + 1):  # number keys: move to deciles
                self.set_index(int(self.reader.sizes['t'] * (key - 48) / 10))
            if key in range(0x01000037,       # F8-F12 keys: change channel
                            0x0100003b + 1) and 'c' in self.reader.sizes:
                index = key - 0x01000037
                print('key pressed to {}'.format(index))
                if index <= self.reader.sizes['c']:
                    self.channel_tabs.setCurrentIndex(index)
            if key in [QtCore.Qt.Key_N, QtCore.Qt.Key_Right]:
                self.set_index(self._index['t'] + 1)
                event.accept()
            elif key in [Qt.Key_P, Qt.Key_Left]:
                self.set_index(self._index['t'] - 1)
                event.accept()
            elif key == Qt.Key_R:
                index = np.random.randint(0, self.reader.sizes['t'] - 1)
                self.set_index(index)
                event.accept()
            elif key == Qt.Key_Space:
                if self.is_playing:
                    self.stop()
                else:
                    self.play()
                event.accept()
            elif key == Qt.Key_BracketRight:
                if self.is_playing:
                    self._timer.fps *= 1.2
            elif key == Qt.Key_BracketLeft:
                if self.is_playing:
                    self._timer.fps *= 0.8
            elif key == Qt.Key_Backslash:
                if self.is_playing:
                    self._timer.fps *= -1
            elif key == Qt.Key_Equal:
                if self.is_playing:
                    try:
                        self._timer.fps = self.reader.frame_rate
                    except AttributeError:
                        self._timer.fps = 25.
            elif key == Qt.Key_F:
                self.renderer.set_fullscreen()
            elif key == Qt.Key_Escape:
                self.renderer.set_fullscreen(False)
            elif key == Qt.Key_Plus:
                if hasattr(self.renderer, 'zoom'):
                    self.renderer.zoom(1)
            elif key == Qt.Key_Minus:
                if hasattr(self.renderer, 'zoom'):
                    self.renderer.zoom(-1)
            elif key == Qt.Key_R:
                if hasattr(self.renderer, 'zoom'):
                    self.renderer.zoom()
            elif key == Qt.Key_Z:
                self.undo.emit()
            elif key == Qt.Key_Y:
                self.redo.emit()
            elif key == Qt.Key_A:
                self.resize_display(factor=1/2)
            elif key == Qt.Key_S:
                self.resize_display(factor=1)
            elif key == Qt.Key_D:
                self.resize_display(factor=2)
            else:
                event.ignore()
        else:
            event.ignore()

    def wheelEvent(self, event):
        if 'z' in self._index:
            new_z = self._index['z'] + int(event.delta() // 120)
            if new_z < 0:
                new_z = 0
            if new_z >= self.reader.sizes['z'] - 1:
                new_z = self.reader.sizes['z'] - 1
            self.set_index(new_z, 'z')

    def to_pixmap(self):
        pixmap = QtWidgets.QPixmap(self.renderer.widget.size())
        self.renderer.widget.render(pixmap)
        return pixmap

    def to_clipboard(self):
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setPixmap(self.to_pixmap())

    def to_frame(self):
        return Frame(rgb_view(self.to_pixmap().toImage()),
                     frame_no=self.index['t'])

    def save_file(self, filename=None):
        if VideoClip is None:
            raise ImportError('The MoviePy exporter requires moviepy to work.')

        if filename is None:
            try:
                cur_dir = os.path.dirname(self.reader.filename)
            except AttributeError:
                cur_dir = ''
            filename = QtGui.QFileDialog.getSaveFileName(directory=cur_dir)
            if isinstance(filename, tuple):
                # Handle discrepancy between PyQt4 and PySide APIs.
                filename = filename[0]

        _, ext = os.path.splitext(os.path.basename(filename))
        ext = ext[1:].lower()
        if ext == 'wmv':
            codec = 'wmv'
        else:
            codec = None  # let moviepy decide
        if ext == '':
            filename += '.mp4'

        length = self.reader.sizes['t']
        try:
            rate = self.reader.frame_rate
        except AttributeError:
            rate = 25

        def _export_func(t):
            self.set_index(int(round(t*rate)))
            return self.to_frame()

        clip = VideoClip(_export_func)
        clip.duration = (length - 1) / rate

        self.status = 'Saving to {}'.format(filename)
        clip.write_videofile(filename, rate, codec=codec, audio=False)
        self.status = 'Done saving {}'.format(filename)

    def closeEvent(self, event):
        for p in self.plugins:
            if hasattr(p, 'output'):
                self.return_val.append(p.output())
                p.close()
            else:
                self.return_val.append(None)
        if self._close_reader:
            self.close_reader()
        self.renderer.close()
        super(Viewer, self).closeEvent(event)


class Plugin(QtWidgets.QDialog):
    def __init__(self, height=0, width=400, dock='bottom'):
        init_qtapp()
        super(Plugin, self).__init__()

        self.dock = dock

        self.viewer = None

        self.setWindowTitle(self.name)
        self.layout = QtWidgets.QGridLayout(self)
        self.resize(width, height)
        self.row = 0

        self.arguments = []
        self.keyword_arguments = {}

    def attach(self, viewer):
        """Attach the Plugin to a Viewer."""
        self.setParent(viewer)
        self.setWindowFlags(QtCore.Qt.Dialog)
        self.viewer = viewer
        self.viewer.plugins.append(self)

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

