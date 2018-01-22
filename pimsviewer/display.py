from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
import six

import numpy as np
from pimsviewer.qt import Qt, FigureCanvasQTAgg

import matplotlib as mpl
import matplotlib.pyplot as plt


class Display(object):
    name = 'Matplotlib'
    ndim = 2
    available = True

    def __init__(self, viewer, shape):
        scale = 1
        dpi = mpl.rcParams['figure.dpi']
        self.shape = shape[:2]
        h, w = self.shape[:2]

        figsize = np.array((w, h), dtype=float) / dpi * scale
        self.viewer = viewer

        # LaTeX rendering will be too slow. For some reason, matplotlib does
        # many (costly) calls to texmanager.py's get_text_width_height_descent
        # also when no axes and no text are drawn. This can only be disabled via
        # the global rcParam, like so:
        mpl.rcParams['text.usetex'] = False

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

        self.canvas.setFocusPolicy(Qt.ClickFocus)
        self.canvas.setFocus()
        self.control_is_held = False

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

    def resize(self, w, h):
        self.set_fullscreen(False)
        self.canvas.resize(w, h)
        self.canvas.updateGeometry()
        self.viewer.main_widget.adjustSize()
        self.viewer.main_widget.updateGeometry()
        self.viewer.adjustSize()

    def set_fullscreen(self, value=None):
        is_fullscreen = self.canvas.isFullScreen()
        if value is None:
            value = not is_fullscreen
        elif value == is_fullscreen:
            return
        if value:
            self.canvas.setWindowFlags(Qt.Window)
            self.canvas.setWindowState(Qt.WindowFullScreen)
            self.canvas.show()
        else:
            self.canvas.setWindowState(Qt.WindowNoState)
            self.canvas.setWindowFlags(Qt.Widget)
            self.canvas.show()

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
        if self.control_is_held:
            self.zoom(event.step, (event.ydata, event.xdata))
        elif 'z' in self.viewer.sizes:
            self.viewer.set_index(self.viewer.index['z'] - int(event.step), 'z')

    def toggle_control_key(self):
        self.control_is_held = not self.control_is_held

class Display_MIP(Display):
    name = 'Max intensity projection'
    ndim = 3
    def __init__(self, viewer, shape):
        super(Display_MIP, self).__init__(viewer, shape[1:])

    def update_image(self, image):
        super(Display_MIP, self).update_image(image.max(0))
