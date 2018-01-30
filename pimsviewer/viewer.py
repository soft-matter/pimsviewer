from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
from os import listdir, path
from os.path import isfile, join
from functools import partial
from fractions import Fraction
import warnings

import numpy as np
from PIL import Image

import pims
from pims import FramesSequenceND, pipeline
from pims.utils.sort import natural_keys
from pims import export

from .widgets import CheckBox, DockWidget, VideoTimer, Slider
from .qt import (Qt, QtWidgets, QtGui, QtCore, Signal,
                 init_qtapp, start_qtapp, NavigationToolbar, QShortcut, QKeySequence)
from .display import Display
from .utils import (wrap_frames_sequence, recursive_subclasses,
                    to_rgb_uint8, memoize, get_supported_extensions, drop_dot, get_available_readers)

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
    The Viewer was based on `skimage.viewer.CollectionViewer`
    """
    dock_areas = {'top': Qt.TopDockWidgetArea,
                  'bottom': Qt.BottomDockWidgetArea,
                  'left': Qt.LeftDockWidgetArea,
                  'right': Qt.RightDockWidgetArea}
    _dropped = Signal(list)

    # signal on image change, so that plotting plugins can process the change
    original_image_changed = Signal()

    window_title = "Python IMage Sequence Viewer"

    def __init__(self, reader=None, close_reader=True):
        self.plugins = []
        self._images = []
        self._img = None
        self._display = None
        self.sliders = dict()
        self.channel_tabs = None
        self.slider_dock = None
        self.is_multichannel = False
        self.is_playing = False
        self._index = dict()
        self.return_val = []
        self.reader = None
        self._close_reader = close_reader
        self.filename = None

        # Start main loop
        init_qtapp()
        super(Viewer, self).__init__()

        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle(self.window_title)

        # list all pims reader classed in the "Open with" menu
        open_with_menu = QtWidgets.QMenu('Open with', self)
        for cls in get_available_readers():
            open_with_menu.addAction(cls.__name__,
                                     partial(self.open_file, reader_cls=cls))

        self.file_menu = QtWidgets.QMenu('&File', self)
        self.file_menu.addAction('Open', self.open_file,
                                 Qt.CTRL + Qt.Key_O)
        self.file_menu.addMenu(open_with_menu)
        self.file_menu.addAction('Open next', self.open_next_file,
                                 Qt.CTRL + Qt.SHIFT + Qt.Key_O)
        self.file_menu.addAction('Open previous', self.open_previous_file,
                                 Qt.ALT + Qt.SHIFT + Qt.Key_O)
        self.file_menu.addAction('Close', self.close_reader)
        self.file_menu.addAction('Export image', self.export_image,
                                 Qt.CTRL + Qt.SHIFT + Qt.Key_S)
        self.file_menu.addAction('Export video', self.export_video,
                                 Qt.CTRL + Qt.Key_S)
        self.file_menu.addAction('Copy', self.to_clipboard,
                                 Qt.CTRL + Qt.Key_C)
        self.file_menu.addAction('Quit', self.close,
                                 Qt.CTRL + Qt.Key_Q)
        self.menuBar().addMenu(self.file_menu)

        self.view_menu = QtWidgets.QMenu('&View', self)
        self._autoscale = QtWidgets.QAction('&Autoscale', self.view_menu,
                                            checkable=True)
        self._autoscale.setChecked(True)
        self._autoscale.toggled.connect(self.update_view)
        self.view_menu.addAction(self._autoscale)

        # Color menu
        self._available_colors = {
            'Greyscale': None,
            'Magenta': [1, 0, 1],
            'Green': [0, 1, 0],
            'Cyan': [0, 1, 1],
            'Red': [1, 0, 0]
        }
        self.force_color = None
        self._color_menu = QtWidgets.QMenu('&Color', self)
        self._color_menu.setDisabled(True)
        color_group = QtWidgets.QActionGroup(self._color_menu)
        for color in self._available_colors:
            color_action = QtWidgets.QAction(color, self._color_menu, checkable=True)
            color_action.toggled.connect(partial(self.update_color_mode, color=color))
            color_group.addAction(color_action)
            self._color_menu.addAction(color_action)
            if color == 'Greyscale':
                color_action.setChecked(True)
        self.view_menu.addMenu(self._color_menu)

        # list all Display subclasses in the View menu
        mode_menu = QtWidgets.QMenu('&Mode', self)
        mode_menu.addAction(Display.name + ' (default)',
                            partial(self.update_display,
                                    display_class=Display))
        for cls in recursive_subclasses(Display):
            if cls.available:
                mode_menu.addAction(cls.name, partial(self.update_display,
                                                      display_class=cls))
        self.view_menu.addMenu(mode_menu)

        resize_menu = QtWidgets.QMenu('&Resize', self)
        resize_menu.addAction('33 %', partial(self.resize_display, factor=1 / 3))
        resize_menu.addAction('50 %', partial(self.resize_display, factor=1 / 2))
        resize_menu.addAction('100 %', partial(self.resize_display, factor=1))
        resize_menu.addAction('200 %', partial(self.resize_display, factor=2))
        resize_menu.addAction('300 %', partial(self.resize_display, factor=3))
        self.view_menu.addMenu(resize_menu)

        play_menu = QtWidgets.QMenu('&Play', self)

        def _mult_fps(factor):
            self.fps *= factor

        play_menu.addAction('Start / stop', lambda: self.play(not self.is_playing))
        play_menu.addAction('Switch direction', partial(_mult_fps, factor=-1))
        play_menu.addAction('Faster', partial(_mult_fps, factor=1.2))
        play_menu.addAction('Slower', partial(_mult_fps, factor=0.8))
        self.view_menu.addMenu(play_menu)

        self.menuBar().addMenu(self.view_menu)

        # self.pipeline_menu = QtWidgets.QMenu('&Pipelines', self)
        # from pimsviewer.plugins import PipelinePlugin
        # for pipeline_obj in PipelinePlugin.instances:
        #     self.pipeline_menu.addAction(pipeline_obj.name,
        #                                  partial(self.add_plugin,
        #                                          pipeline_obj))
        # self.menuBar().addMenu(self.pipeline_menu)

        self.main_widget = QtWidgets.QWidget(self)
        self.setCentralWidget(self.main_widget)
        self.setMinimumSize(800, 600)
        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred,
                           QtWidgets.QSizePolicy.Preferred)
        self.main_layout = QtWidgets.QGridLayout(self.main_widget)

        self.mpl_toolbar = None

        # make file dragging & dropping work
        self.setAcceptDrops(True)
        self._dropped.connect(self._open_dropped)

        self._status_bar = self.statusBar()

        # initialize the timer for video playback
        self._timer = VideoTimer(self)
        self._play_checkbox = None

        self.add_keyboard_shortcuts()

        if reader is not None:
            self.update_reader(reader)

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
            dock.setSizePolicy(QtWidgets.QSizePolicy.Fixed,
                               QtWidgets.QSizePolicy.MinimumExpanding)
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

    def closeEvent(self, event):
        for p in self.plugins:
            if hasattr(p, 'output'):
                self.return_val.append(p.output())
                p.close()
            else:
                self.return_val.append(None)
        if self._close_reader:
            self.close_reader()
        if self._display is not None:
            self._display.close()
        super(Viewer, self).closeEvent(event)

    # the update cascade: open_file -> update_reader -> update_display ->
    # update_original_image -> image -> update_view. Any function calls the next one,
    # but you can call for instance update_original_image to only update the image.

    def open_file(self, filename=None, reader_cls=None):
        """Open image file and update the viewer's reader"""
        if filename is None:
            try:
                cur_dir = os.path.dirname(self.reader.filename)
            except AttributeError:
                cur_dir = ''
            filename = QtWidgets.QFileDialog.getOpenFileName(directory=cur_dir)
            if isinstance(filename, tuple):
                # Handle discrepancy between PyQt4 and PySide APIs.
                filename = filename[0]
        if filename is None or len(filename) == 0:
            return

        filename = path.abspath(filename)
        if reader_cls is None:
            try:
                reader = pims.open(filename)
            except pims.api.UnknownFormatError:
                reader = None
        else:
            reader = reader_cls(filename)

        if self.reader is not None:
            self.close_reader()

        if reader is not None:
            self.update_reader(reader)
            self.status = 'Opened {}'.format(filename)
            self.setWindowTitle('{} - '.format(path.basename(filename)) + self.window_title)
            self.filename = filename
        else:
            self.status = 'No suitable reader was found to open {}'.format(filename)

    def open_next_file(self, forward=True):
        """
        Opens the next file in the current directory

        Parameters
        ----------
        forward : bool
            Cycle forward or backwards

        """
        if self.filename is None:
            self.open_file()

        supported_extensions = get_supported_extensions()

        current_directory = path.dirname(self.filename)
        file_list = self._get_all_files_in_dir(current_directory, extensions=supported_extensions)
        if len(file_list) < 2:
            self.status = 'No file found for opening'
            return

        try:
            current_file_index = file_list.index(path.basename(self.filename))
        except ValueError:
            self.status = 'No file found for opening'
            return

        next_index = current_file_index + 1 if forward else current_file_index - 1
        try:
            next_file = file_list[next_index]
        except IndexError:
            next_index = 0 if forward else -1
            next_file = file_list[next_index]

        self.open_file(filename=path.join(current_directory, next_file))

    def open_previous_file(self):
        """
        Opens the previous file in the current directory
        """
        self.open_next_file(forward=False)

    def update_reader(self, reader):
        """Load a new reader into the Viewer."""
        if not isinstance(reader, FramesSequenceND):
            reader = wrap_frames_sequence(reader)
        self.reader = reader
        reader.iter_axes = 't'
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
            self.sliders[axis] = Slider(axis, low=0, high=reader.sizes[axis] - 1,
                                        value=self._index[axis], update_on='release', value_type='int',
                                        callback=lambda x, y: self.set_index(y, x))

        if len(self.sliders) > 0:
            slider_widget = QtWidgets.QWidget()
            slider_layout = QtWidgets.QGridLayout(slider_widget)
            for i, axis in enumerate(self.sliders):
                slider_layout.addWidget(self.sliders[axis], i, 0)
                if axis == 't':
                    self._play_checkbox = CheckBox('play', self.is_playing,
                                                   callback=self.play_callback)
                    slider_layout.addWidget(self._play_checkbox, i, 1)

            self.slider_dock = QtWidgets.QDockWidget()
            self.slider_dock.setWidget(slider_widget)
            self.slider_dock.setWindowTitle('Axes sliders')
            self.slider_dock.setFeatures(QtWidgets.QDockWidget.DockWidgetFloatable |
                                         QtWidgets.QDockWidget.DockWidgetMovable)
            self.addDockWidget(Qt.BottomDockWidgetArea, self.slider_dock)

        # set playback speed
        try:
            self._timer.fps = self.reader.frame_rate
        except (AttributeError, KeyError):
            self._timer.fps = 25.

        self.update_display()
        self.resize_display()

    def update_display(self, display_class=None):
        """Change display mode."""
        if display_class is None:
            display_class = Display

        shape = [self.reader.sizes['y'], self.reader.sizes['x']]
        if display_class.ndim == 3 and 'z' in self.reader.sizes:
            shape = [self.reader.sizes['z']] + shape
        elif display_class.ndim == 3:
            # Display class does not support 2D images
            display_class = Display
            self.status = 'Requested display mode only supports 3D images'

        if self._display is not None:
            self._display.close()
        self._display = display_class(self, shape)

        self.canvas.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                                  QtWidgets.QSizePolicy.Expanding)
        self.canvas.updateGeometry()
        self.mpl_toolbar = NavigationToolbar(self.canvas, self.main_widget)
        self.main_layout.addWidget(self.mpl_toolbar, 0, 0)
        self.main_layout.addWidget(self.canvas, 1, 0)
        self.update_original_image()

    def update_original_image(self):
        """Update the original image that is being viewed."""
        if self._display.ndim == 3 and 'z' not in self.reader.sizes:
            raise ValueError('z axis does not exist: cannot display in 3D')
        if self.is_multichannel and 'c' not in self.reader.sizes:
            raise ValueError('c axis does not exist: cannot display multicolor')

        # Make sure that the reader bundle_axes settings are correct
        bundle_axes = ''
        if self.is_multichannel:
            bundle_axes += 'c'
        if self._display.ndim == 3:
            bundle_axes += 'z'
        self.reader.bundle_axes = bundle_axes + 'yx'

        # Update slider positions
        for name in self.sliders:
            self.sliders[name].val = self._index[name]

        # Update image
        self.reader.default_coords.update(self._index)
        image = self.reader[self._index['t']]

        if len(self._images) == 0:
            self._images = [image] + [None] * len(self.plugins)
        else:
            self._images[0] = image

        self.update_processed_image()

    def update_processed_image(self, plugin=None):
        """Update the processing function stack starting from `plugin`."""
        if self.original_image is None:
            return

        if plugin is None:
            first_plugin = 0
        else:
            first_plugin = self.plugins.index(plugin)

        # reset the image stack if necessary
        required_len = len(self.plugins) + 1
        if len(self._images) != required_len:
            first_plugin = 0  # we will need to reform the entire stack
            self._images = [self.original_image] + [None] * (required_len - 1)

        for i, p in enumerate(self.plugins[first_plugin:], start=first_plugin):
            processed = p.process_image(self._images[i])
            if processed is None:
                processed = self._images[i]
            self._images[i + 1] = processed
        self.update_view()

    def update_view(self):
        """Emit processed image to display."""
        if self.image is None:
            return

        self._display.update_image(to_rgb_uint8(self.image, autoscale=self.autoscale, force_color=self.force_color))
        self.original_image_changed.emit()
        self._disable_or_enable_menus()

    def _disable_or_enable_menus(self):
        """Disable/Enable menu actions based on the current image"""
        if self.image is None or self.is_multichannel:
            self._color_menu.setDisabled(True)
        else:
            self._color_menu.setEnabled(True)

    @property
    def original_image(self):
        """The original image"""
        if len(self._images) == 0:
            return
        return self._images[0]

    @property
    def image(self):
        """The image that is being displayed"""
        if len(self._images) == 0:
            return
        return self._images[-1]

    @property
    def canvas(self):
        try:
            return self._display.canvas
        except AttributeError:
            return None

    @property
    def ax(self):
        try:
            return self._display.ax
        except AttributeError:
            return None

    @property
    def fig(self):
        try:
            return self._display.fig
        except AttributeError:
            return None

    # Change the current index

    @property
    def index(self):
        """The current index (dictionary). Setting this has no effect."""
        return self._index.copy()  # copy the dict to make it read only

    def _set_index(self, value, name):
        """Set the index without checks. Mainly for timer callback."""
        try:
            if self._index[name] == value:
                return  # do nothing when no coordinate was changed
        except KeyError:
            pass  # but continue when a coordinate did not exist
        self._index[name] = value
        self.update_original_image()

    def set_index(self, value=0, name='t'):
        """Update the index along a specific axis"""
        if name not in self.reader.sizes:
            return ValueError("Axis '{}' not in reader".format(name))
        # clip value if necessary
        if value < 0:
            value = 0
        elif value >= self.reader.sizes[name]:
            value = self.reader.sizes[name] - 1
        if self.is_playing and name == 't':
            self._timer.reset(value)
        self._set_index(value, name)

    def channel_tab_callback(self, index):
        """Callback function for channel tabs."""
        if index == 0 and self.is_multichannel:
            return  # do nothing: already multichannel
        elif not self.is_multichannel and (self._index['c'] == index - 1):
            return  # do nothing: correct monochannel
        self.is_multichannel = index == 0
        if index > 0:  # monochannel: update channel field
            self._index['c'] = index - 1  # because 0 is multichannel
        self.update_original_image()

    # Access to the reader and its properties

    @property
    def sizes(self):
        return self.reader.sizes.copy()

    @property
    def autoscale(self):
        return self._autoscale.isChecked()

    @autoscale.setter
    def autoscale(self, value):
        self._autoscale.setChecked(value)

    def close_reader(self):
        """Close the current reader"""
        if self.reader is None:
            return
        if self.is_playing:
            self.stop()
        if self.slider_dock is not None:
            self.slider_dock.close()
        if self.channel_tabs is not None:
            self.channel_tabs.close()
        self.reader.close()
        self.reader = None
        self._display.close()

    # Video playback

    def play_callback(self, name, value):
        """Callback function for play checkbox."""
        if value == self.is_playing:
            return
        if value:
            self.play()
        else:
            self.stop()

    def play(self, start=True, fps=None, toggle=False):
        """Control movie playback."""
        if toggle:
            start = not self.is_playing
        if self._play_checkbox is not None:
            self._play_checkbox.val = start
        if start == self.is_playing:
            return
        if start:
            self._timer.start(self._index['t'], self.reader.sizes['t'])
            self._timer.next_frame.connect(lambda x: self._set_index(x, 't'))
            if fps is not None:
                self.fps = fps
        else:
            self._timer.stop()
        self.is_playing = start

    @property
    def fps(self):
        return self._timer.fps

    @fps.setter
    def fps(self, value):
        if self.is_playing:
            self._timer.fps = value

    def stop(self):
        """Stop the movie."""
        self.play(False)

    # File drag & drop

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

    # Handling user input

    def resize_display(self, w=None, h=None, factor=1):
        """Resize the image display widget to a certain size or by a factor."""
        h_im, w_im = self.sizes['y'], self.sizes['x']
        h_im *= factor
        w_im *= factor
        if h is None and w is None:
            h = h_im
            w = w_im
        elif h is None:
            h = int(w * h_im / w_im)
        elif w is None:
            w = int(h * w_im / h_im)
        self.showNormal()  # make sure not to be in maximized mode
        self._display.resize(w, h)

    def make_shortcut(self, key, connect):
        shortcut = QShortcut(QKeySequence(key), self)
        shortcut.activated.connect(connect)

    def update_t_index_key(self, key, fraction=True, random=False):
        """
        Update the time index based on a pressed number key
        Args:
            random:
            fraction:
            key:

        Returns:

        """
        if random:
            key = np.random.random() * 10.0

        if fraction:
            index = int(self.reader.sizes['t'] * key / 10)
        else:
            index = int(self._index['t'] + key)

        if index < 0:
            index = 0
        elif index >= self.reader.sizes['t']:
            index = self.reader.sizes['t'] - 1

        self.set_index(index, 't')

    def update_c_index_key(self, key):
        if key <= self.reader.sizes['c']:
            self.channel_tabs.setCurrentIndex(key)

    def change_fps_key(self, increment):
        if increment == 0:
            try:
                self.fps = self.reader.frame_rate
            except AttributeError:
                self.fps = 25.
        else:
            self.fps *= increment

    @property
    def calibration(self):
        try:
            # For ND2Reader
            calibration = 1.0 / self.reader.metadata['pixel_microns']
        except AttributeError or KeyError:
            calibration = None
        return calibration

    def set_fullscreen_key(self, escape=False):
        if not escape:
            is_fullscreen = self.isFullScreen()
        else:
            is_fullscreen = True

        if not is_fullscreen:
            self.setWindowState(Qt.WindowFullScreen)
        else:
            self.setWindowState(Qt.WindowNoState)

    def add_keyboard_shortcuts(self):
        # number keys: change t index
        for i in range(10):
            self.make_shortcut(str(i), partial(self.update_t_index_key, i, True))

        # F8-F12: change channel
        for i, k in enumerate(('F8', 'F9', 'F10', 'F11', 'F12')):
            self.make_shortcut(k, partial(self.update_c_index_key, i))

        # n / right keys change time index
        self.make_shortcut('n', partial(self.update_t_index_key, 1, False))
        self.make_shortcut('right', partial(self.update_t_index_key, 1, False))
        self.make_shortcut('shift+n', partial(self.update_t_index_key, 10, False))
        self.make_shortcut('shift+right', partial(self.update_t_index_key, 10, False))
        self.make_shortcut('ctrl+n', partial(self.update_t_index_key, 25, False))
        self.make_shortcut('ctrl+right', partial(self.update_t_index_key, 25, False))
        self.make_shortcut('ctrl+shift+n', partial(self.update_t_index_key, 100, False))
        self.make_shortcut('ctrl+shift+right', partial(self.update_t_index_key, 100, False))

        # p / left keys change time index
        self.make_shortcut('p', partial(self.update_t_index_key, -1, False))
        self.make_shortcut('left', partial(self.update_t_index_key, -1, False))
        self.make_shortcut('shift+p', partial(self.update_t_index_key, -10, False))
        self.make_shortcut('shift+left', partial(self.update_t_index_key, -10, False))
        self.make_shortcut('ctrl+p', partial(self.update_t_index_key, -25, False))
        self.make_shortcut('ctrl+left', partial(self.update_t_index_key, -25, False))
        self.make_shortcut('ctrl+shift+p', partial(self.update_t_index_key, -100, False))
        self.make_shortcut('ctrl+shift+left', partial(self.update_t_index_key, -100, False))

        # random index
        self.make_shortcut('r', partial(self.update_t_index_key, 0, True, True))

        # Play/pause
        self.make_shortcut('space', partial(self.play, toggle=True))

        # Play speed
        self.make_shortcut(']', partial(self.change_fps_key, 1.2))
        self.make_shortcut('[', partial(self.change_fps_key, 0.8))
        self.make_shortcut('\\', partial(self.change_fps_key, -1))
        self.make_shortcut('=', partial(self.change_fps_key, 0))

        # Fullscreen
        self.make_shortcut('f', partial(self.set_fullscreen_key))
        self.make_shortcut('Escape', partial(self.set_fullscreen_key, True))

        # Resizing
        self.make_shortcut('a', partial(self.resize_display, factor=1 / 2))
        self.make_shortcut('s', partial(self.resize_display, factor=1))
        self.make_shortcut('d', partial(self.resize_display, factor=2))

    @property
    def status(self):
        return None

    @status.setter
    def status(self, value):
        self._status_bar.showMessage(str(value))

    # # Output data (EXPERIMENTAL)
    #
    def to_pixmap(self):
        pixmap = QtWidgets.QPixmap(self.canvas.size())
        self.canvas.render(pixmap)
        return pixmap

    def to_clipboard(self):
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setPixmap(self.to_pixmap())

    @staticmethod
    @memoize
    def _get_all_files_in_dir(directory, extensions=None):
        if extensions is None:
            file_list = [f for f in listdir(directory) if isfile(join(directory, f))]
        else:
            file_list = [f for f in listdir(directory) if isfile(join(directory, f))
                         and drop_dot(os.path.splitext(f)[1]) in extensions]

        return sorted(file_list, key=natural_keys)

    def update_color_mode(self, color=None):
        """Updates the color mode (full color/greyscale) of the current image.
        """
        self.force_color = self._available_colors[color]
        self.update_view()

    def export_image(self, filename=None, **kwargs):
        """For a list of kwargs, see pims.export"""
        # TODO Save the canvas instead of the reader (including annotations)
        str_filter = ";;".join(['All files (*.*)',
                                'PNG image (*.png)',
                                'JPEG image (*.jpg)',
                                'TIFF image (*.tif)',
                                'Bitmap image (*.bmp)'])

        if filename is None:
            try:
                cur_dir = os.path.dirname(self.reader.filename)
            except AttributeError:
                cur_dir = ''
            filename = QtWidgets.QFileDialog.getSaveFileName(self,
                                                             "Export Image",
                                                             cur_dir,
                                                             str_filter)
            if isinstance(filename, tuple):
                # Handle discrepancy between PyQt4 and PySide APIs.
                filename = filename[0]

        self.status = 'Saving to {}'.format(filename)
        Image.fromarray(to_rgb_uint8(self.image, autoscale=self.autoscale, force_color=self.force_color)).save(filename)
        self.status = 'Done saving {}'.format(filename)

    def export_video(self, filename=None, rate=None, **kwargs):
        """For a list of kwargs, see pims.export"""
        # TODO Save the canvas instead of the reader (including annotations)
        presets = dict(avi=dict(codec='libx264', quality=23),
                       mp4=dict(codec='mpeg4', quality=5),
                       mov=dict(codec='mpeg4', quality=5),
                       wmv=dict(codec='wmv2', quality=0.005))

        str_filter = ";;".join(['All files (*.*)',
                                'H264 video (*.avi)',
                                'MPEG4 video (*.mp4 *.mov)',
                                'Windows Media Player video (*.wmv)'])

        if filename is None:
            try:
                cur_dir = os.path.dirname(self.reader.filename)
            except AttributeError:
                cur_dir = ''
            filename = QtWidgets.QFileDialog.getSaveFileName(self,
                                                             "Export Movie",
                                                             cur_dir,
                                                             str_filter)
            if isinstance(filename, tuple):
                # Handle discrepancy between PyQt4 and PySide APIs.
                filename = filename[0]

        ext = os.path.splitext(filename)[-1]
        if ext[0] == '.':
            ext = ext[1:]
        try:
            _kwargs = presets[ext]
        except KeyError:
            raise ValueError("Extension '.{}' is not a known format.".format(ext))

        _kwargs.update(kwargs)

        if rate is None:
            try:
                rate = float(self.reader.frame_rate)
            except AttributeError or ValueError:
                rate = 25.

        self.reader.iter_axes = 't'
        self.status = 'Saving to {}'.format(filename)

        # PIMS v0.4 export() has a bug having to do with float precision
        # fix that here using limit_denominator() from fractions
        export(pipeline(to_rgb_uint8)(self.reader, autoscale=self.autoscale, force_color=self.force_color), filename,
               Fraction(rate).limit_denominator(66535), **kwargs)
        self.status = 'Done saving {}'.format(filename)

        #
        # def to_frame(self):
        #     return Frame(rgb_view(self.to_pixmap().toImage()),
        #                  frame_no=self.index['t'])
