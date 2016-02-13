from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
import six
from six import with_metaclass
from abc import ABCMeta, abstractmethod, abstractproperty

import numpy as np
from pimsviewer.qt import (QtGui, QtCore, QtWidgets, FigureCanvasQTAgg,
                           array2qimage, has_qimage2ndarray)

try:
    import matplotlib as mpl
    import matplotlib.pyplot as plt
    has_matplotlib = True
except ImportError:
    has_matplotlib = False

try:
    import pyqtgraph
    if ((QtCore.PYQT_VERSION_STR == pyqtgraph.Qt.QtCore.PYQT_VERSION_STR) and
        (QtCore.QT_VERSION_STR == pyqtgraph.Qt.QtCore.QT_VERSION_STR)):
        from pyqtgraph.opengl import GLViewWidget, GLVolumeItem, GLBoxItem
        has_pyqtgraph = True
    else:
        has_pyqtgraph = False
except ImportError:
    has_pyqtgraph = False


class Display(with_metaclass(ABCMeta, object)):
    name = 'base_class'
    ndim = 2
    available = False
    @abstractproperty
    def widget(self):
        pass

    @abstractmethod
    def close(self):
        pass

    @property
    def image(self):
        return self._image

    @image.setter
    def image(self, value):
        self.update_image(value)
        self._image = value

    @abstractmethod
    def update_image(self, value):
        pass

    def resize(self, w, h):
        self.widget.resize(w, h)
        self.widget.updateGeometry()
        self.viewer.main_widget.adjustSize()
        self.viewer.main_widget.updateGeometry()
        self.viewer.adjustSize()


class DisplayQt(Display):
    name = 'Qt'
    ndim = 2
    available = has_qimage2ndarray
    def __init__(self, viewer, shape):
        self.viewer = viewer
        self._widget = QtWidgets.QLabel()
        self._widget.setBackgroundRole(QtGui.QPalette.Base)
        self._widget.setScaledContents(True)
        self._widget.updateGeometry()

    def update_image(self, value):
        self._widget.setPixmap(QtGui.QPixmap.fromImage(array2qimage(value)))

    @property
    def widget(self):
        return self._widget

    def close(self):
        self._widget.close()


class DisplayMPL(Display):
    name = 'Matplotlib'
    ndim = 2
    available = has_matplotlib

    def __init__(self, viewer, shape):
        scale = 1
        dpi = mpl.rcParams['figure.dpi']
        self.shape = shape[:2]
        h, w = self.shape[:2]

        figsize = np.array((w, h), dtype=float) / dpi * scale
        self.viewer = viewer
        self.fig = plt.Figure(figsize=figsize, dpi=dpi)
        self.canvas = FigureCanvasQTAgg(self.fig)

        self.ax = self.fig.add_subplot(1, 1, 1)
        self.fig.subplots_adjust(left=0, bottom=0, right=1, top=1)
        self.ax.set_axis_off()
        self.ax.imshow(np.zeros((h, w, 3), dtype=np.bool),
                       interpolation='nearest', cmap='gray')
        self.ax.autoscale(enable=False)

        self._image_plot = self.ax.images[0]
        self._image_plot.set_clim((0, 255))
        self._image_plot.set_extent((0, w, h, 0))
        self.ax.set_xlim(0, w)
        self.ax.set_ylim(h, 0)

        self.canvas.mpl_connect('motion_notify_event', self.on_motion)
        self.canvas.mpl_connect('button_press_event', self.on_press)
        self.canvas.mpl_connect('scroll_event', self.on_scroll)

    def redraw(self):
        self.canvas.draw()

    def update_image(self, image):
        self._image_plot.set_array(image)
        self.redraw()

    @property
    def widget(self):
        return self.canvas

    def close(self):
        plt.close(self.fig)
        self.canvas.close()

    def zoom(self, step=None, center=None):
        # get the current x and y limits
        cur_xlim = self.ax.get_xlim()
        cur_ylim = self.ax.get_ylim()
        cur_width = cur_xlim[1] - cur_xlim[0]
        cur_height = cur_ylim[0] - cur_ylim[1]  # y-axis is inverted
        max_height, max_width = self.shape

        if center is None:
            y = (cur_ylim[0] + cur_ylim[1]) / 2
            x = (cur_xlim[0] + cur_xlim[1]) / 2
        else:
            y, x = center

        if x < 0 or y < 0 or x > max_width or y > max_height:
            return
        if step is None:
            scale_factor = min(max_width/cur_width, max_height/cur_height)
        else:
            scale_factor = min(0.8**step, max_width/cur_width,
                               max_height/cur_height)
        if scale_factor == 1.:
            return
        # calculate new limits
        w = scale_factor*(cur_xlim[1] - cur_xlim[0])
        h = scale_factor*(cur_ylim[0] - cur_ylim[1])  # y-axis is inverted
        x -= w / 2
        y -= h / 2

        # shift box if any corner is out of bounds
        if x < 0:
            x = 0
        if y < 0:
            y = 0
        if x + w > max_width:
            x = max_width - w
        if y + h > max_height:
            y = max_height - h

        # set new limits
        self.ax.set_xlim([x, x + w])
        self.ax.set_ylim([y + h, y])
        self.redraw()

    def shift(self, dy, dx):
        """Shifts the view with (dy, dx)"""
        cur_xlim = self.ax.get_xlim()
        cur_ylim = self.ax.get_ylim()
        max_height, max_width = self.shape

        x1 = cur_xlim[0] - dx
        y1 = cur_ylim[1] - dy
        x2 = cur_xlim[1] - dx
        y2 = cur_ylim[0] - dy

        if x1 < 0:
            x2 -= x1
            x1 = 0
        if y1 < 0:
            y2 -= y1
            y1 = 0
        if x2 > max_width:
            x1 -= (x2 - max_width)
            x2 = max_width
        if y2 > max_height:
            y1 -= (y2 - max_height)
            y2 = max_height

        # set new limits
        self.ax.set_xlim([x1, x2])
        self.ax.set_ylim([y2, y1])
        self.redraw()

    def center(self, y, x):
        """Centers the view on (y, x)"""
        cur_xlim = self.ax.get_xlim()
        cur_ylim = self.ax.get_ylim()
        self.shift((cur_ylim[0] + cur_ylim[1]) / 2 - y,
                   (cur_xlim[0] + cur_xlim[1]) / 2 - x)

    def on_press(self, event):
        if event.inaxes != self.ax:
            return
        if event.button == 1 and event.dblclick:  # double click: center
            self.center(event.ydata, event.xdata)

    def on_motion(self, event):
        try:
            x = int(event.xdata + 0.5)
            y = int(event.ydata + 0.5)
            if self.viewer.is_multichannel:
                val = self.viewer.image[:, y, x]
            else:
                val = self.viewer.image[y, x]
            self.viewer.status = "%4s @ [%4s, %4s]" % (val, x, y)
        except (TypeError, IndexError):
            self.viewer.status = ""

    def on_scroll(self, event):
        if event.inaxes != self.ax:
            return
        self.zoom(event.step, (event.ydata, event.xdata))


class DisplayMPL_mip(DisplayMPL):
    name = 'Matplotlib (MIP)'
    ndim = 3
    available = has_matplotlib
    def __init__(self, viewer, shape):
        super(DisplayMPL_mip, self).__init__(viewer, shape[1:])

    def update_image(self, image):
        super(DisplayMPL_mip, self).update_image(image.max(0))


class DisplayVolume(Display):
    name = 'OpenGL 3D'
    ndim = 3
    available = has_pyqtgraph

    def __init__(self, viewer, shape):
        if len(shape) != 3:
            raise ValueError('Invalid image dimensionality')
        self.viewer = viewer
        self.shape = shape

        # try to readout calibration
        reader = self.viewer.reader
        try:
            mpp = reader.calibration
        except AttributeError:
            mpp = 1
        if mpp is None:
            mpp = 1
        try:
            mppZ = reader.calibrationZ
        except AttributeError:
            mppZ = mpp
        shape_um = (self.shape[2] * mpp, self.shape[1] * mpp,
                    self.shape[0] * mppZ)

        self._widget = GLViewWidget()
        self.volume = GLVolumeItem(np.zeros(tuple(self.shape[-1:-4:-1]) + (4,),
                                            dtype=np.ubyte))
        # set aspect ratio and reverse y axis
        self.volume.scale(mpp, -mpp, mppZ)
        self.volume.translate(0, shape_um[1], 0)
        self.widget.addItem(self.volume)

        self.box = GLBoxItem(color=(255, 255, 255))
        self.box.setSize(*shape_um)
        self.widget.addItem(self.box)

        self.widget.setCameraPosition(azimuth=-45, elevation=30,
                                     distance=max(shape) * 1.5)
        self.widget.pan(*[s / 2 for s in shape_um], relative=False)

    def update_image(self, image):
        assert all([im == s for (im, s) in zip(image.shape[:3], self.shape)])
        new_image = np.empty(tuple(self.shape[-1:-4:-1]) + (4,), dtype=np.ubyte)
        new_image[:, :, :, :3] = image.transpose([2, 1, 0, 3])
        new_image[:, :, :, 3] = np.mean(image, axis=3).T
        self.volume.setData(new_image)

    def close(self):
        self.widget.close()

    @property
    def widget(self):
        return self._widget
