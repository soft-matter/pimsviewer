from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import six

import os
import unittest
import nose
import numpy as np
from numpy.testing import (assert_equal, assert_almost_equal, assert_allclose)
from pimsviewer import Viewer, ViewerPipeline, Slider, ViewerAnnotate
from pims import FramesSequence, FramesSequenceND, Frame
import pandas as pd


class RandomReader(FramesSequence):
    def __init__(self, length=10, shape=(128, 128), dtype='uint8'):
        self._len = length
        self._dtype = dtype
        self._shape = shape

    def __len__(self):
        return self._len

    @property
    def frame_shape(self):
        return self._shape

    @property
    def pixel_type(self):
        return self._dtype

    def get_frame(self, i):
        if np.issubdtype(self._dtype, np.float):
            frame = np.random.random(self._shape).astype(self._dtype)
        else:
            frame = np.random.randint(0, np.iinfo(self._dtype).max,
                                     self._shape).astype(self._dtype)
        return Frame(frame, frame_no=i)


def add_noise(img, noise_level):
    return img + np.random.random(img.shape) * noise_level

AddNoise = ViewerPipeline(add_noise, 'Add noise', dock='right') + \
           Slider('noise_level', 0, 100, 0, orientation='vertical')

class TestViewer(unittest.TestCase):
    def test_viewer_noreader(self):
        viewer = Viewer()
        viewer.show()

    def test_viewer_reader(self):
        viewer = Viewer(RandomReader())
        viewer.show()

    def test_viewer_3d(self):
        viewer = Viewer(RandomReader(shape=(10, 128, 128)))
        viewer.show()

    def test_viewer_pipeline(self):
        viewer = Viewer(RandomReader()) + AddNoise
        viewer.show()

    def test_viewer_annotate(self):
        f = pd.DataFrame(np.random.random((100, 2)) * 128, columns=['x', 'y'])
        f['frame'] = np.repeat(np.arange(10), 10)
        (Viewer(RandomReader()) + ViewerAnnotate(f)).show()


if __name__ == '__main__':
    nose.runmodule(argv=[__file__, '-vvs'], exit=False)

import numpy as np
from pimsviewer import ViewerPipeline, Slider, ViewerPlotting


def convert_to_grey(img, r, g, b):
    color_axis = img.shape.index(3)
    img = np.rollaxis(img, color_axis, 3)
    grey = (img * [r, g, b]).sum(2)
    return grey.astype(img.dtype)  # coerce to original dtype


def add_noise(img, noise_level):
    return img + np.random.random(img.shape) * noise_level

def tp_locate(image, radius, minmass, separation, noise_size, ax):
    _plot_style = dict(markersize=15, markeredgewidth=2,
                       markerfacecolor='none', markeredgecolor='r',
                       marker='o', linestyle='none')
    from trackpy import locate
    f = locate(image, radius * 2 + 1, minmass, None, separation, noise_size)
    if len(f) == 0:
        return None
    else:
        return ax.plot(f['x'], f['y'], **_plot_style)

# TODO: this does not work because it changes the image shape
# RGBToGrey = ViewerPipeline(convert_to_grey, 'RGB to Grey', dock='right') + \
#             Slider('r', 0, 1, 0.2125, orientation='vertical') + \
#             Slider('g', 0, 1, 0.7154, orientation='vertical') + \
#             Slider('b', 0, 1, 0.0721, orientation='vertical')

Locate = ViewerPlotting(tp_locate, 'Locate', dock='right') + \
       Slider('radius', 1, 20, 7, value_type='int', orientation='vertical') + \
       Slider('separation', 1, 20, 7, value_type='float', orientation='vertical') + \
       Slider('noise_size', 1, 20, 1, value_type='int', orientation='vertical') + \
       Slider('minmass', 1, 10000, 100, value_type='int', orientation='vertical')
