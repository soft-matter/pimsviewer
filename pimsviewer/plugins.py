from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import numpy as np
from .utils import df_add_row, AnchoredScaleBar
from collections import deque
import tkinter as tk
import tkinter.ttk as ttk
import tkinter.font as font
from tkinter.colorchooser import askcolor
from pims.display import to_rgb

def remove_artists(artists):
    """Call artist.remove() on a nested list of artists."""
    if isinstance(artists, list):
        for artist in artists:
            remove_artists(artist)
    else:
        artists.remove()


def get_frame_no(indices, frame_axes):
    iter_size = 1
    frame_no = 0
    for ax in reversed(frame_axes):
        coord = indices[ax]
        frame_no += iter_size * coord
        iter_size *= coord
    return frame_no


class Plugin(tk.Toplevel):
    name = None
    init_menu = False

    def __init__(self, viewer, func=None, name=None, **kwargs):
        self.func = func

        if name is None and self.name is None:
            if self.func is not None:
                self.name = func.__name__
            else:
                self.name = ''
        else:
            self.name = name

        self.parent = viewer.mainwindow
        self.viewer = viewer
        super().__init__(self.parent, **kwargs)

        if 'width' in kwargs or 'height' in kwargs:
            width = kwargs['width'] if 'width' in kwargs else 100
            height = kwargs['height'] if 'height' in kwargs else 100
            self.wm_geometry("%dx%d" % (width, height))

        self.attributes('-topmost', 'true')

        self.widgets = []
        self.update()

    @classmethod
    def add_menu_item(cls, viewer, menu):
        if cls.name is None or not cls.init_menu:
            return

        menu.add_command(label=cls.name, command=lambda: cls.menu_item_callback(viewer))

    @classmethod
    def menu_item_callback(cls, viewer):
        instance = cls(viewer)

    def close(self):
        """Close the plugin and clean up."""
        self.viewer.show_frame()

        self.destroy()

    def add_widget(self, widget, add_command=True):
        """Add widget to pipeline.

        Widgets can adjust arguments of the pipeline function, as specified by
        the Widget's `ptype`.
        """
        widget.plugin = self
        widget.grid()
        if add_command:
            widget.config(command=self.process)
        widget.update()
        self.widgets.append(widget)

    def __add__(self, widget):
        self.add_widget(widget)
        return self

    def process(self, event=None):
        """Notify the viewer that the processing function has been changed. """
        self.viewer.add_process_function('process_plugin_%s' % self.name, self.process_image)
        self.viewer.show_frame()

    def process_image(self, image):
        if self.func is not None:
            values = {}
            for w in self.widgets:
                name = str(w).split('.')[-1]
                values[name] = w.get()
            return self.func(image, values)
        else:
            return image

class ColorPlugin(Plugin):
    init_menu = True
    name = 'Adjust colors'

    colors = {0: [1, 0, 1], 1: [0, 1, 0]}
    buttons = {}
    num_channels = 0

    def __init__(self, viewer):
        super().__init__(viewer, name=self.name)

        try:
            self.num_channels = self.viewer.reader.sizes['c']
        except KeyError:
            self.num_channels = 1

        # add widgets
        for c in range(self.num_channels):
            l = tk.Label(self, text='Channel %d' % c)
            l.grid(row=c, column=1)
            self.add_widget(l, add_command=False)

            self.buttons[c] = tk.Button(self)
            if c in self.colors:
                color = np.floor(np.multiply(self.colors[c], 255.0)).astype(int)
                self.buttons[c].config(bg='#%02x%02x%02x' % tuple(color))

            self.buttons[c].config(command=lambda i=c: self.select_color(i))
            self.buttons[c].grid(row=c, column=2)
            self.add_widget(self.buttons[c], add_command=False)

        btn = tk.Button(self, text='Close', command=self.close)
        self.add_widget(btn, add_command=False)

        self.process()

    def select_color(self, c):
        if c in self.colors:
            previous_color = tuple(np.floor(np.multiply(self.colors[c], 255.0)).astype(int))
        else:
            previous_color = None

        selected = askcolor(previous_color)[0]
        
        if selected is not None:
            selected = np.divide(selected, 255.0)
            # something goes wrong with the tk color selector
            selected[selected < 0] = 0
            selected[selected > 1] = 1.0
            self.colors[c] = selected

        color = np.floor(np.multiply(self.colors[c], 255.0)).astype(int)
        self.buttons[c].config(bg='#%02x%02x%02x' % tuple(color))

        self.process()

    def process_image(self, image):
        if len(image.shape) == 2:
            if 'c' in image.metadata['coords']:
                c = image.metadata['coords']['c']
            else:
                c = 0

            try:
                color = self.colors[c]
            except KeyError:
                color = np.ones(3)

            rgb_img = to_rgb(image, colors=color, normed=True)
        else:
            colors = list(self.colors.values())
            rgb_img = to_rgb(image, colors=colors, normed=True)

        return rgb_img


class PlottingPlugin(Plugin):
    def __init__(self, viewer, plot_func, name=None, height=100, width=400):
        super().__init__(viewer, func=plot_func, name=name, height=height, width=width)

    def process_image(self, image):
        values = {}
        for w in self.widgets:
            name = str(w).split('.')[-1]
            values[name] = w.get()
        return self.func(image, values, self.viewer.ax)


class AnnotatePlugin(Plugin):
    name = 'Annotate Features'
    default_msg = 'Click a particle to display its properties.\n'

    def __init__(self, viewer, features, frame_axes='t', plot_style=None,
                 text_style=None, picking_tolerance=5, z_width=0.5):
        super().__init__(viewer)
        self.viewer = viewer
        self.artist = None
        if features.index.is_unique:
            self.features = features.copy()
        else:
            self.features = features.reset_index(inplace=False, drop=True)

        self._no_pick = None
        self._no_click = None
        self._selected = None
        self._frame_axes = frame_axes
        self.z_width = z_width
        self.plot_style = dict(s=200, linewidths=2, edgecolors='r',
                               facecolors='none', marker='o')
        if plot_style is not None:
            self.plot_style.update(plot_style)
        # disable tex
        self.text_style = dict(usetex=False, color='r')
        if text_style is not None:
            self.text_style.update(text_style)

        self.picking_tolerance = picking_tolerance

        self.canvas = self.viewer.canvas
        self.ax = self.viewer.ax

        if self.canvas is not None:
            self.canvas.mpl_connect('pick_event', self.on_pick)

        self._out = tk.StringVar()
        self._out_w = tk.Label(self, textvariable=self._out)
        self.add_widget(self._out_w, add_command=False)
        self._out.set(self.default_msg)

        self.process()

    def process_image(self, image):
        frame_no = get_frame_no(self.viewer.index, self._frame_axes)
        text_offset = 2
        if 'z' in self.viewer.index:
            z = self.viewer.index['z'] + 0.5
            f_frame = self.features[(self.features['frame'] == frame_no) &
                                    (np.abs(self.features['z'] - z) <= self.z_width)]
        else:
            f_frame = self.features[self.features['frame'] == frame_no]
        f_frame = f_frame[~np.isnan(f_frame[['x', 'y']]).any(1)].copy()
        self.indices = f_frame.index
        if self.artist is not None:
            remove_artists(self.artist)
        if len(f_frame) == 0:
            self.artist = None
        else:
            self.artist = self.ax.scatter(f_frame['x'] + 0.5,
                                          f_frame['y'] + 0.5,
                                          picker=self.picking_tolerance,
                                          **self.plot_style)
            texts = []
            if 'particle' in self.features:
                for i in self.indices:
                    x, y, p = self.features.loc[i, ['x', 'y', 'particle']]
                    try:
                        p = str(int(p))
                    except ValueError:
                        pass
                    else:
                        texts.append(self.ax.text(x + text_offset, y - text_offset,
                                                  p, **self.text_style))
            self.artist = [self.artist, texts]
        return image

    @property
    def selected(self):
        return self._selected

    @selected.setter
    def selected(self, value):
        self._selected = value
        if value is None:
            msg = self.default_msg
        else:
            msg = 'index     {}\n'.format(int(value)) + \
                  self.features.loc[value].to_string()
        self._out.set(msg)

    def on_pick(self, event):
        if event.mouseevent is self._no_pick:
            return
        self._no_click = event.mouseevent  # no click events
        index = self.indices[event.ind[0]]
        button = event.mouseevent.button
        dblclick = event.mouseevent.dblclick
        if button == 1 and not dblclick:  # left mouse: select
            if self.selected is None:
                self.selected = index
            else:
                self.selected = None
            self._no_click = event.mouseevent
            self.process()


class SelectionPlugin(AnnotatePlugin):
    name = 'Select Features'
    default_msg = 'Click a particle to display its properties.\n' \
                  'Rightclick to hide/unhide\n' \
                  'Select and drag with middle mouse to move\n' \
                  'Select and double click with right mouse to hide the full trajectory\n' \
                  'Double click with right mouse to add\n'

    def __init__(self, viewer, *args, **kwargs):
        super().__init__(viewer, *args, **kwargs)
        if 'hide' not in self.features:
            self.features['hide'] = False
        self.dragging = False

        self._undo = deque([], 10)
        self._redo = deque([], 10)

        if 'edgecolors' in self.plot_style:
            del self.plot_style['edgecolors']
        if 'color' in self.text_style:
            del self.text_style['color']

        self.canvas.mpl_connect('button_press_event', self.on_press)
        self.canvas.mpl_connect('button_release_event', self.on_release)

    def process_image(self, image):
        frame_no = get_frame_no(self.viewer.index, self._frame_axes)
        text_offset = 2
        if 'z' in self.viewer.index:
            z = self.viewer.index['z'] + 0.5
            f_frame = self.features[(self.features['frame'] == frame_no) &
                                    (np.abs(self.features['z'] - z) <= self.z_width)]
        else:
            f_frame = self.features[self.features['frame'] == frame_no]
        f_frame = f_frame[~np.isnan(f_frame[['x', 'y']]).any(1)].copy()
        self.indices = f_frame.index
        if self.selected not in self.indices:
            self.selected = None
            self.dragging = False
        else:
            self.selected = self.selected
        if self.artist is not None:
            remove_artists(self.artist)
        if len(f_frame) == 0:
            self.artist = None
        else:
            colors = []
            for i in f_frame.index:
                try:
                    if self.selected == i:
                        colors.append('yellow')
                    elif f_frame.loc[i, 'hide']:
                        colors.append('grey')
                    else:
                        colors.append('red')
                except KeyError:
                    colors.append('red')
            if 'edgecolors' in self.plot_style:
                del self.plot_style['edgecolors']
            self.artist = self.ax.scatter(f_frame['x'] + 0.5,
                                          f_frame['y'] + 0.5,
                                          edgecolors=colors,
                                          picker=self.picking_tolerance,
                                          **self.plot_style)
            texts = []
            if 'particle' in self.features:
                for i, color in zip(self.indices, colors):
                    x, y, p = self.features.loc[i, ['x', 'y', 'particle']]
                    try:
                        p = str(int(p))
                    except ValueError:
                        pass
                    else:
                        if 'color' in self.text_style:
                            del self.text_style['color']
                        texts.append(self.ax.text(x + text_offset, y - text_offset,
                                                  p, color=color,
                                                  **self.text_style))
            self.artist = [self.artist, texts]
        return image

    def output(self):
        return self.features

    def set_features(self, new_f):
        self._undo.append(self.features.copy())
        self.features = new_f
        self._redo.clear()
        self.process()

    def undo(self):
        if len(self._undo) == 0:
            return
        self._redo.append(self.features)
        self.features = self._undo.pop()
        self.process()

    def redo(self):
        if len(self._redo) == 0:
            return
        self._undo.append(self.features)
        self.features = self._redo.pop()
        self.process()

    def on_pick(self, event):
        if event.mouseevent is self._no_pick:
            return
        self._no_click = event.mouseevent  # no click events
        index = self.indices[event.ind[0]]
        button = event.mouseevent.button
        dblclick = event.mouseevent.dblclick
        if button == 1 and not dblclick:  # left mouse: select
            if self.selected is None:
                self.selected = index
            else:
                self.selected = None
            self._no_click = event.mouseevent
            self.process()
        elif button == 2 and not dblclick:  # middle mouse on selected: drag
            if self.selected is not None:
                self.dragging = True
        elif button == 3 and not dblclick:  # right mouse: hide
            self.selected = None
            f = self.features.copy()
            f.loc[index, 'hide'] = not f.loc[index, 'hide']
            self.set_features(f)
        elif button == 3 and dblclick:  # right mouse double: hide track
            if 'particle' in self.features:
                f = self.features.copy()
                particle_id = f.loc[index, 'particle']
                was_hidden = not f.loc[index, 'hide']
                if was_hidden:
                    f.loc[f['particle'] == particle_id, 'hide'] = False
                else:
                    f.loc[f['particle'] == particle_id, 'hide'] = True
                self.set_features(f)

    def on_press(self, event):
        if (event.inaxes != self.ax) or (event is self._no_click):
            return
        if event.button == 1 and not event.dblclick:
            if self.selected is not None:
                self.selected = None
                self.process()
        elif event.button == 3 and event.dblclick:
            f = self.features.copy()
            new_index = df_add_row(f)
            f.loc[new_index, ['x', 'y']] = event.xdata, event.ydata
            if 'z' in self.viewer.index:
                f.loc[new_index, 'z'] = self.viewer.index['z'] + 0.5
            f.loc[new_index, 'frame'] = \
                get_frame_no(self.viewer.index, self._frame_axes)
            self.set_features(f)

    def on_release(self, event):
        if ((not self.dragging) or (event.inaxes != self.ax)
            or (self.selected is None) or (event is self._no_click)):
            return
        self.dragging = False
        if event.button == 2:
            f = self.features.copy()
            f.loc[self.selected, ['x', 'y']] = event.xdata, event.ydata
            if 'gaussian' in f:
                f.loc[self.selected, 'gaussian'] = False
            if 'particle' in f:
                f.loc[self.selected, 'particle'] = -1
            self.set_features(f)

