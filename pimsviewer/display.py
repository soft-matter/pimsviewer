from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

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
        self.canvas.mpl_connect('scroll_event', self.on_scroll)

        self.canvas.setFocusPolicy(Qt.ClickFocus)
        self.canvas.setFocus()

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
        self.canvas.resize(w, h)
        self.canvas.updateGeometry()
        self.viewer.main_widget.adjustSize()
        self.viewer.main_widget.updateGeometry()
        self.viewer.adjustSize()

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
        elif 'z' in self.viewer.sizes:
            self.viewer.set_index(self.viewer.index['z'] - int(event.step), 'z')


class Display_MIP(Display):
    name = 'Max intensity projection'
    ndim = 3

    def __init__(self, viewer, shape):
        super(Display_MIP, self).__init__(viewer, shape[1:])

    def update_image(self, image):
        super(Display_MIP, self).update_image(image.max(0))
