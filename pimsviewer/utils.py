from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import functools

import numpy as np
import pims
from pims import to_rgb, normalize
from pims.base_frames import FramesSequence, FramesSequenceND
from itertools import chain
from matplotlib.offsetbox import AnchoredOffsetbox
from matplotlib.patches import Rectangle
from matplotlib.offsetbox import AuxTransformBox, VPacker, HPacker, TextArea, DrawingArea


def memoize(obj):
    """Memoize the function call result"""
    cache = obj.cache = {}

    @functools.wraps(obj)
    def memoizer(*args, **kwargs):
        """Memoize by storing the results in a dict"""
        key = str(args) + str(kwargs)
        if key not in cache:
            cache[key] = obj(*args, **kwargs)
        return cache[key]

    return memoizer


def recursive_subclasses(cls):
    "Return all subclasses (and their subclasses, etc.)."
    # Source: http://stackoverflow.com/a/3862957/1221924
    return (cls.__subclasses__() +
            [g for s in cls.__subclasses__() for g in recursive_subclasses(s)])


def drop_dot(s):
    if s.startswith('.'):
        return s[1:]
    else:
        return s


@memoize
def get_available_readers():
    readers = set(chain(recursive_subclasses(FramesSequence),
                        recursive_subclasses(FramesSequenceND)))
    readers = [cls for cls in readers if not hasattr(cls, 'no_reader')]
    return readers


def get_supported_extensions():
    # list all readers derived from the pims baseclasses
    all_handlers = chain(recursive_subclasses(FramesSequence),
                         recursive_subclasses(FramesSequenceND))
    # keep handlers that support the file ext. use set to avoid duplicates.
    extensions = set(ext for h in all_handlers for ext in map(drop_dot, h.class_exts()))

    return extensions


def to_rgb_uint8(image, autoscale=True, force_color=None):
    ndim = image.ndim
    shape = image.shape
    try:
        colors = image.metadata['colors']
        if len(colors) != shape[0]:
            colors = None
    except (AttributeError, KeyError):
        colors = None

    # 2D, grayscale
    if ndim == 2:
        force_color = [force_color] if force_color is not None else None
        image = to_rgb(image, force_color)
    # 2D non-interleaved RGB
    elif ndim == 3 and shape[0] in [3, 4]:
        image = image.transpose([1, 2, 0])
        autoscale = False
    # 2D, has colors attribute
    elif ndim == 3 and colors is not None:
        image = to_rgb(image, colors, True)
    # 2D, RGB
    elif ndim == 3 and shape[2] in [3, 4]:
        pass
    # 2D, is multichannel
    elif ndim == 3 and shape[0] < 5:  # guessing; could be small z-stack
        image = to_rgb(image, None, True)
    # 3D, grayscale
    elif ndim == 3:
        grayscale = True
    # 3D, has colors attribute
    elif ndim == 4 and colors is not None:
        image = to_rgb(image, colors, True)
    # 3D, RGB
    elif ndim == 4 and shape[3] in [3, 4]:
        pass
    # 3D, is multichannel
    elif ndim == 4 and shape[0] < 5:
        image = to_rgb(image, None, True)
    else:
        raise ValueError("No display possible for frames of shape {0}".format(shape))

    if autoscale:
        image = (normalize(image) * 255).astype(np.uint8)
    elif not np.issubdtype(image.dtype, np.uint8):
        if np.issubdtype(image.dtype, np.integer):
            max_value = np.iinfo(image.dtype).max
            # sometimes 12-bit images are stored as unsigned 16-bit
            if max_value == 2 ** 16 - 1 and image.max() < 2 ** 12:
                max_value = 2 ** 12 - 1
            image = (image / max_value * 255).astype(np.uint8)
        else:
            if image.max() > 1:  # unnormalized floats! normalize anyway
                image = normalize(image)
            image = (image * 255).astype(np.uint8)

    return image


def df_add_row(df, default_float=np.nan, default_int=-1, default_bool=False):
    if np.isnan(df.index).any():
        raise ValueError('NaN index detected.')
    values = []
    for col, dtype in zip(df.columns, df.dtypes):
        if np.issubdtype(dtype, np.float):
            values.append(default_float)
        elif np.issubdtype(dtype, np.integer):
            values.append(default_int)
        elif np.issubdtype(dtype, np.bool):
            values.append(default_bool)
        else:
            raise ValueError()
    index = df.index.max() + 1
    if np.isnan(index):
        index = 0
    df.loc[index] = values
    return index


def wrap_frames_sequence(frames):
    shape = frames.frame_shape
    ndim = len(shape)

    try:
        colors = frames.metadata['colors']
        if len(colors) != shape[0]:
            colors = None
    except (KeyError, AttributeError):
        colors = None

    if ndim == 2:
        y, x = frames.frame_shape
        return ND_Wrapper(frames, 'yx', y=y, x=x, t=len(frames))
    elif ndim == 3 and colors is not None:
        c, y, x = frames.frame_shape
        return ND_Wrapper(frames, 'cyx', c=c, y=y, x=x, t=len(frames))
    elif ndim == 3 and shape[2] in [3, 4]:
        y, x, c = frames.frame_shape
        return ND_Wrapper(frames, 'yxc', c=c, y=y, x=x, t=len(frames))
    elif ndim == 3 and shape[0] < 5:  # guessing; could be small z-stack
        c, y, x = frames.frame_shape
        return ND_Wrapper(frames, 'cyx', c=c, y=y, x=x, t=len(frames))
    elif ndim == 3:
        z, y, x = frames.frame_shape
        return ND_Wrapper(frames, 'zyx', z=z, y=y, x=x, t=len(frames))
    elif ndim == 4 and colors is not None:
        c, z, y, x = frames.frame_shape
        return ND_Wrapper(frames, 'czyx', c=c, z=z, y=y, x=x, t=len(frames))
    elif ndim == 4 and shape[3] in [3, 4]:
        z, y, x, c = frames.frame_shape
        return ND_Wrapper(frames, 'zyxc', c=c, z=z, y=y, x=x, t=len(frames))
    elif ndim == 4 and shape[0] < 5:
        c, z, y, x = frames.frame_shape
        return ND_Wrapper(frames, 'czyx', c=c, z=z, y=y, x=x, t=len(frames))
    else:
        raise ValueError("Cannot interpret dimensions for a reader of "
                         "shape {0}".format(shape))


class ND_Wrapper(FramesSequenceND):
    no_reader = True
    propagate_attrs = ['sizes', 'default_coords', 'bundle_axes', 'iter_axes']

    def __init__(self, frames, reads_axes, **sizes):
        super(ND_Wrapper, self).__init__()
        self._reader = frames
        for ax in sizes:
            self._init_axis(ax, sizes[ax])
        self._register_get_frame(self._get_frame, reads_axes)

    @property
    def pixel_type(self):
        return self._reader.pixel_type

    def _get_frame(self, **ind):
        return self._reader[ind['t']]

    def __getattr__(self, attr):
        return getattr(self._reader, attr)


class AnchoredScaleBar(AnchoredOffsetbox):
    def __init__(self, transform, sizex=0, sizey=0, labelx=None, labely=None, loc=4,
                 pad=0.1, borderpad=0.1, sep=2, prop=None, barcolor="black", barwidth=None, fontproperties=None,
                 **kwargs):
        """
        Draw a horizontal and/or vertical  bar with the size in data coordinate
        of the give axes. A label will be drawn underneath (center-aligned).
        - transform : the coordinate frame (typically axes.transData)
        - sizex,sizey : width of x,y bar, in data units. 0 to omit
        - labelx,labely : labels for x,y bars; None to omit
        - loc : position in containing axes
        - pad, borderpad : padding, in fraction of the legend font size (or prop)
        - sep : separation between labels and bars in points.
        - **kwargs : additional arguments passed to base class constructor
        """
        bars = AuxTransformBox(transform)
        if sizex:
            bars.add_artist(Rectangle((0, 0), sizex, 0, ec=barcolor, lw=barwidth, fc="none"))
        if sizey:
            bars.add_artist(Rectangle((0, 0), 0, sizey, ec=barcolor, lw=barwidth, fc="none"))

        if fontproperties is None:
            fontproperties = {}

        if sizex and labelx:
            self.xlabel = TextArea(labelx, minimumdescent=False, textprops=fontproperties)
            bars = VPacker(children=[bars, self.xlabel], align="center", pad=0, sep=sep)
        if sizey and labely:
            self.ylabel = TextArea(labely, textprops=fontproperties)
            bars = HPacker(children=[self.ylabel, bars], align="center", pad=0, sep=sep)

        AnchoredOffsetbox.__init__(self, loc, pad=pad, borderpad=borderpad,
                                   child=bars, prop=prop, frameon=False, **kwargs)

