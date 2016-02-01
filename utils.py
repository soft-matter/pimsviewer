from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import numpy as np
from pims import Frame, to_rgb, normalize
from pimsviewer.base_frames import FramesSequenceND, reads_axes

def recursive_subclasses(cls):
    "Return all subclasses (and their subclasses, etc.)."
    # Source: http://stackoverflow.com/a/3862957/1221924
    return (cls.__subclasses__() +
        [g for s in cls.__subclasses__() for g in recursive_subclasses(s)])


def to_rgb_uint8(image, autoscale=True):
    ndim = image.ndim
    shape = image.shape
    try:
        colors = image.metadata['colors']
        if len(colors) != shape[0]:
            colors = None
    except (AttributeError, KeyError):
        colors = None

    grayscale = False
    # 2D, grayscale
    if ndim == 2:
        grayscale = True
    # 2D non-interleaved RGB
    elif ndim == 3 and shape[0] in [3, 4]:
        image = image.transpose([1, 2, 0])
        autoscale = False
    # 2D, has colors attribute
    elif ndim == 3 and colors is not None:
        image = to_rgb(image, colors, False)
    # 2D, RGB
    elif ndim == 3 and shape[2] in [3, 4]:
        pass
    # 2D, is multichannel
    elif ndim == 3 and shape[0] < 5:  # guessing; could be small z-stack
        image = to_rgb(image, None, False)
    # 3D, grayscale
    elif ndim == 3:
        grayscale = True
    # 3D, has colors attribute
    elif ndim == 4 and colors is not None:
        image = to_rgb(image, colors, False)
    # 3D, RGB
    elif ndim == 4 and shape[3] in [3, 4]:
        pass
    # 3D, is multichannel
    elif ndim == 4 and shape[0] < 5:
        image = to_rgb(image, None, False)
    else:
        raise ValueError("No display possible for frames of shape {0}".format(shape))

    if autoscale:
        image = (normalize(image) * 255).astype(np.uint8)
    elif not np.issubdtype(image.dtype, np.uint8):
        if np.issubdtype(image.dtype, np.integer):
            max_value = np.iinfo(image.dtype).max
            # sometimes 12-bit images are stored as unsigned 16-bit
            if max_value == 2**16 - 1 and image.max() < 2**12:
                max_value = 2**12 - 1
            image = (image / max_value * 255).astype(np.uint8)
        else:
            image = (image * 255).astype(np.uint8)

    if grayscale:
        image = np.repeat(image[..., np.newaxis], 3, axis=image.ndim)

    return image


class FramesSequence_Wrapper(FramesSequenceND):
    """This class wraps a FramesSequence so that it behaves as a
    FramesSequenceND. All attributes are forwarded to the containing reader."""
    colors_RGB = dict(colors=[(1., 0., 0.), (0., 1., 0.), (0., 0., 1.)])

    def __init__(self, frames_sequence):
        self._reader = frames_sequence
        self._last_i = None
        self._last_frame = None
        shape = frames_sequence.frame_shape
        ndim = len(shape)

        try:
            colors = self._reader.metadata['colors']
            if len(colors) != shape[0]:
                colors = None
        except (KeyError, AttributeError):
            colors = None

        c = None
        z = None
        self.is_RGB = False
        # 2D, grayscale
        if ndim == 2:
            y, x = shape
        # 2D, has colors attribute
        elif ndim == 3 and colors is not None:
            c, y, x = shape
        # 2D, RGB
        elif ndim == 3 and shape[2] in [3, 4]:
            y, x, c = shape
            self.is_RGB = True
        # 2D, is multichannel
        elif ndim == 3 and shape[0] < 5:  # guessing; could be small z-stack
            c, y, x = shape
        # 3D, grayscale
        elif ndim == 3:
            z, y, x = shape
        # 3D, has colors attribute
        elif ndim == 4 and colors is not None:
            c, z, y, x = shape
        # 3D, RGB
        elif ndim == 4 and shape[3] in [3, 4]:
            z, y, x, c = shape
            self.is_RGB = True
        # 3D, is multichannel
        elif ndim == 4 and shape[0] < 5:
            c, z, y, x = shape
        else:
            raise ValueError("Cannot interpret dimensions for a reader of "
                             "shape {0}".format(shape))

        self._init_axis('y', y)
        self._init_axis('x', x)
        self._init_axis('t', len(self._reader))
        if z is not None:
            self._init_axis('z', z)
        if c is not None:
            self._init_axis('c', c)

    @reads_axes('yx')
    def get_frame_2D(self, **ind):
        # do some cacheing
        if self._last_i != ind['t']:
            self._last_i = ind['t']
            self._last_frame = self._reader[ind['t']]
        frame = self._last_frame

        if 'z' in ind and 'c' in ind and self.is_RGB:
            return frame[ind['z'], :, :, ind['c']]
        elif 'z' in ind and 'c' in ind:
            return frame[ind['c'], ind['z'], :, :]
        elif 'z' in ind:
            return frame[ind['z'], :, :]
        elif 'c' in ind and self.is_RGB:
            return frame[:, :, ind['c']]
        elif 'c' in ind:
            return frame[ind['c'], :, :]
        else:
            return frame

    @reads_axes('yxc')
    def get_frame_RGB(self, **ind):
        # do some cacheing
        if self._last_i != ind['t']:
            self._last_i = ind['t']
            self._last_frame = self._reader[ind['t']]
        frame = self._last_frame

        if 'z' in ind and 'c' in ind and self.is_RGB:
            return frame[ind['z'], :, :, :]
        elif 'z' in ind and 'c' in ind:
            return frame[:, ind['z'], :, :].transpose([1, 2, 0])
        elif 'z' in ind:
            return frame[ind['z'], :, :]
        elif 'c' in ind and self.is_RGB:
            return frame[:, :, :]
        elif 'c' in ind:
            return frame[:, :, :].transpose([1, 2, 0])
        else:
            return frame

    @property
    def pixel_type(self):
        return self._reader.pixel_type

    def __getattr__(self, attr):
        return self._reader.__getattr__(attr)
