from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import numpy as np
from pimsviewer.widgets import Text
from pimsviewer.viewer import Plugin
from pimsviewer.display import DisplayMPL
from pimsviewer.utils import df_add_row


def remove_artists(artists):
    """Call artist.remove() on a nested list of artists."""
    if isinstance(artists, list):
        for artist in artists:
            remove_artists(artist)
    else:
        artists.remove()


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
    >>> from pims.viewer import Viewer, ViewerPipeline, Slider
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
        self.viewer.plugins.append(self)
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
    name = 'Annotate'
    picking_tolerance = 5
    def __init__(self, features):
        super(AnnotatePlugin, self).__init__(dock='left')
        self.artist = None
        self.features = features
        self._selected = None
        self.dragging = False
        self.last_event = None
        self.select_event = None
        if 'hide' not in self.features:
            self.features['hide'] = False

    def attach(self, viewer):
        super(AnnotatePlugin, self).attach(viewer)
        if type(viewer.renderer) is not DisplayMPL:
            viewer.update_display(DisplayMPL)

        self.fig = viewer.renderer.fig
        self.ax = viewer.renderer.ax
        self.canvas = viewer.renderer.widget

        self.viewer.image_changed.connect(self.process)
        self.canvas.mpl_connect('pick_event', self.on_pick)
        self.canvas.mpl_connect('button_press_event', self.on_press)
        self.canvas.mpl_connect('button_release_event', self.on_release)

        self._out = Text()
        self.add_widget(self._out)
        self.process()

    def process(self, *widget_arg):
        frame_no = self.viewer.index['t']
        _plot_style = dict(s=200, linewidths=2, facecolors='none', marker='o')
        _text_style = dict()
        text_offset = 2
        f_frame = self.features[self.features['frame'] == frame_no]
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
                elif 'gaussian' not in f_frame:
                    colors.append('red')
                elif f_frame.loc[i, 'gaussian']:
                    colors.append('blue')
                else:
                    colors.append('red')
            self.artist = self.ax.scatter(f_frame['x'], f_frame['y'],
                                          edgecolors=colors,
                                          picker=self.picking_tolerance,
                                          **_plot_style)
            texts = []
            for i, color in zip(self.indices, colors):
                x, y, p = self.features.loc[i, ['x', 'y', 'particle']]
                try:
                    p = str(int(p))
                except ValueError:
                    pass
                else:
                    texts.append(self.ax.text(x+text_offset, y-text_offset, p,
                                              color=color, **_text_style))
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
        if event.mouseevent is self.last_event:
            self.last_event = None
            return
        index = self.indices[event.ind[0]]
        button = event.mouseevent.button
        dblclick = event.mouseevent.dblclick
        if button == 1 and not dblclick:  # left mouse: select
            if self.selected is None:
                self.selected = index
            else:
                self.selected = None
            self.select_event = event.mouseevent
            self.process()
        if button == 2 and not dblclick:  # middle mouse on selected: drag
            if self.selected is not None:
                self.dragging = True
        elif button == 3 and not dblclick:  # right mouse: hide
            self.selected = None
            self.features.loc[index, 'hide'] = not self.features.loc[index, 'hide']
            self.process()
        elif button == 3 and dblclick and 'particle' in self.features:  # right mouse double: hide track
            particle_id = self.features.loc[index, 'particle']
            was_hidden = self.features.loc[index, 'hide']
            if was_hidden:
                self.features.loc[self.features['particle'] == particle_id,
                                  'hide'] = False
            else:
                self.features.loc[self.features['particle'] == particle_id,
                                  'hide'] = True
            self.process()

    def on_press(self, event):
        if event.inaxes != self.ax:
            return
        if (event.button == 1) and (self.selected is not None) and (event is not self.select_event) and not event.dblclick:
            self.selected = None
            self.select_event = None
            self.process()
        if event.button == 3 and event.dblclick:
            self.last_event = event
            new_index = df_add_row(self.features)
            self.features.loc[new_index, ['x', 'y']] = event.xdata, event.ydata
            self.features.loc[new_index, 'frame'] = self.viewer.index['t']
            self.process()

    def on_release(self, event):
        if (not self.dragging) or (event.inaxes != self.ax) or (self.selected is None):
            return
        self.dragging = False
        if event.button == 2:
            self.features.loc[self.selected, ['x', 'y']] = event.xdata, event.ydata
            if 'gaussian' in self.features:
                self.features.loc[self.selected, 'gaussian'] = False
            if 'particle' in self.features:
                self.features.loc[self.selected, 'particle'] = -1
            self.process()

