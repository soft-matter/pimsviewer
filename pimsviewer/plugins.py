from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import numpy as np
from .widgets import Text
from .display import DisplayMPL
from .utils import df_add_row
from .qt import QtWidgets, QtCore, init_qtapp
from collections import deque


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


class PipelinePlugin(Plugin):
    """Base class for viewing the result of image processing inside the Viewer.

    The PipelinePlugin class connects an image filter (or another function) to
    the Viewer. The Viewer returns a reader object that has the function applied
    with parameters set inside the Viewer.

    Parameters
    ----------
    pipeline_func : function
        Function that processes the image. It should not change the image shape.
    name : string
        Name of pipeline. This is displayed as the window title.
    height, width : int
        Size of plugin window in pixels. Note that Qt will automatically resize
        a window to fit components. So if you're adding rows of components, you
        can leave `height = 0` and just let Qt determine the final height.
    dock : {bottom, top, left, right}
        Default docking area

    Examples
    --------
    >>> import numpy as np
    >>> from pimsviewer import Viewer, PipelinePlugin, Slider
    >>>
    >>> def add_noise(img, noise_level):
    >>>     return img + np.random.random(img.shape) * noise_level
    >>>
    >>> image_reader = np.zeros((1, 512, 512), dtype=np.uint8)
    >>>
    >>> AddNoise = PipelinePlugin(add_noise) + Slider('noise_level', 0, 100, 0)
    >>> viewer = Viewer(image_reader)
    >>> viewer += AddNoise
    >>> original, noise_added = viewer.show()
    """
    # the class keeps a list of its instances
    instances = []
    def __init__(self, pipeline_func, name=None, height=0, width=400,
                 dock='bottom'):
        self.pipeline_func = pipeline_func

        if name is None:
            self.name = pipeline_func.__name__
        else:
            self.name = name

        super(PipelinePlugin, self).__init__(height, width, dock)

        PipelinePlugin.instances.append(self)

    def attach(self, viewer):
        """Attach the pipeline to an ImageViewer.

        Note that the ImageViewer will automatically call this method when the
        plugin is added to the ImageViewer. For example:

            viewer += Plugin(pipeline_func)

        Also note that `attach` automatically calls the filter function so that
        the image matches the filtered value specified by attached widgets.
        """
        super(PipelinePlugin, self).attach(viewer)
        self.viewer._readers += [None]
        self.reader_index = len(self.viewer._readers) - 1
        self.viewer._readers[self.reader_index] = self.viewer._readers[self.reader_index - 1]

        self.process()

    def _process(self):
        kwargs = dict([(name, self._get_value(a))
                       for name, a in self.keyword_arguments.items()])
        self.viewer._readers[self.reader_index] = \
            self.pipeline_func(self.viewer._readers[self.reader_index - 1],
                               *self.arguments, **kwargs)

    def process(self, *widget_arg):
        """Send the changed pipeline function to the Viewer. """
        # `widget_arg` is passed by the active widget but is unused since all
        # filter arguments are pulled directly from attached the widgets.
        to_process = [None] * (len(self.viewer._readers) - self.reader_index)
        for plugin in self.viewer.plugins:
            try:
                if plugin.reader_index >= self.reader_index:
                    to_process[plugin.reader_index - self.reader_index] = plugin
            except AttributeError:
                pass  # no pipeline_index
        for plugin in to_process:
            plugin._process()
        self.viewer.update_image()

    def close(self):
        """Close the plugin and clean up."""
        if self in self.viewer.plugins:
            self.viewer.plugins.remove(self)

        # delete the pipeline
        if self.reader_index is not None:
            del self.viewer._readers[self.reader_index]
        # decrease pipeline_index for the other pipelines
        for plugin in self.viewer.plugins:
            try:
                if plugin.reader_index > self.reader_index:
                    plugin.reader_index -= 1
            except AttributeError:
                pass  # no pipeline_index

        self.viewer.update_view()

        super(PipelinePlugin, self).close()

    def output(self):
        self.viewer._close_reader = False
        return self.viewer._readers[self.reader_index]


class PlottingPlugin(Plugin):
    def __init__(self, plot_func, name=None, height=0, width=400,
                 dock='bottom'):
        if name is None:
            self.name = plot_func.__name__
        else:
            self.name = name

        super(PlottingPlugin, self).__init__(height, width, dock)

        self.artist = None
        self.plot_func = plot_func

    def attach(self, viewer):
        super(PlottingPlugin, self).attach(viewer)

        if type(viewer.renderer) is not DisplayMPL:
            viewer.update_display(DisplayMPL)

        self.fig = viewer.renderer.fig
        self.ax = viewer.renderer.ax
        self.canvas = viewer.renderer.widget

        self.viewer.image_changed.connect(self.process)

        self.process()

    def process(self, *widget_arg):
        kwargs = dict([(name, self._get_value(a))
                       for name, a in self.keyword_arguments.items()])
        if self.artist is not None:
            remove_artists(self.artist)
        self.artist = self.plot_func(self.viewer.image, *self.arguments,
                                     ax=self.ax, **kwargs)
        self.canvas.draw_idle()


class AnnotatePlugin(Plugin):
    name = 'Annotate Features'
    def __init__(self, features, frame_axes='t', plot_style=None,
                 text_style=None, picking_tolerance=5):
        super(AnnotatePlugin, self).__init__(dock='left')
        self.artist = None
        if features.index.is_unique:
            self.features = features.copy()
        else:
            self.features = features.reset_index(inplace=False, drop=True)

        self._no_pick = None
        self._no_click = None
        self._selected = None
        self._frame_axes = frame_axes
        self.plot_style = dict(s=200, linewidths=2, edgecolors='r',
                               facecolors='none', marker='o')
        if plot_style is not None:
            self.plot_style.update(plot_style)
        # disable tex
        self.text_style = dict(usetex=False, color='r')
        if text_style is not None:
            self.text_style.update(text_style)

        self.picking_tolerance = picking_tolerance

    def attach(self, viewer):
        super(AnnotatePlugin, self).attach(viewer)
        if type(viewer.renderer) is not DisplayMPL:
            viewer.update_display(DisplayMPL)

        self.fig = viewer.renderer.fig
        self.ax = viewer.renderer.ax
        self.canvas = viewer.renderer.widget

        self.viewer.image_changed.connect(self.process)
        self.canvas.mpl_connect('pick_event', self.on_pick)

        self._out = Text()
        self.add_widget(self._out)
        self.process()

    def process(self, *widget_arg):
        frame_no = get_frame_no(self.viewer.index, self._frame_axes)
        text_offset = 2
        if 'z' in self.viewer.sizes:
            z = self.viewer.index['z'] + 0.5
            f_frame = self.features[(self.features['frame'] == frame_no) &
                                    (np.abs(self.features['z'] - z) <= 0.5)]
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
                        texts.append(self.ax.text(x+text_offset, y-text_offset,
                                                  p, **self.text_style))
            self.artist = [self.artist, texts]
        self.canvas.draw_idle()

    @property
    def selected(self):
        return self._selected

    @selected.setter
    def selected(self, value):
        self._selected = value
        if value is None:
            msg = ""
        else:
            msg = 'index     {}\n'.format(int(value)) + \
                  self.features.loc[value].to_string()
        self._out.text = msg

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

    def __init__(self, features, frame_axes='t', plot_style=None,
                 text_style=None, picking_tolerance=5):
        super(SelectionPlugin, self).__init__(features, frame_axes,
                                              plot_style, text_style,
                                              picking_tolerance)
        if 'hide' not in self.features:
            self.features['hide'] = False
        self.dragging = False

        self._undo = deque([], 10)
        self._redo = deque([], 10)

        if 'edgecolors' in self.plot_style:
            del self.plot_style['edgecolors']
        if 'color' in self.text_style:
            del self.text_style['color']

    def process(self, *widget_arg):
        frame_no = get_frame_no(self.viewer.index, self._frame_axes)
        text_offset = 2
        if 'z' in self.viewer.sizes:
            z = self.viewer.index['z'] + 0.5
            f_frame = self.features[(self.features['frame'] == frame_no) &
                                    (np.abs(self.features['z'] - z) <= 0.5)]
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
                if self.selected == i:
                    colors.append('yellow')
                elif f_frame.loc[i, 'hide']:
                    colors.append('grey')
                else:
                    colors.append('red')
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
                        texts.append(self.ax.text(x+text_offset, y-text_offset,
                                                  p, color=color,
                                                  **self.text_style))
            self.artist = [self.artist, texts]
        self.canvas.draw_idle()

    def attach(self, viewer):
        super(SelectionPlugin, self).attach(viewer)

        self.canvas.mpl_connect('button_press_event', self.on_press)
        self.canvas.mpl_connect('button_release_event', self.on_release)

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

    @property
    def selected(self):
        return self._selected
    @selected.setter
    def selected(self, value):
        self._selected = value
        if value is None:
            msg = ""
        else:
            msg = 'index     {}\n'.format(int(value)) + \
                  self.features.loc[value].to_string()
        self._out.text = msg

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
            if 'z' in self.viewer.sizes:
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
