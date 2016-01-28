from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import six

import os
import unittest
import nose
import numpy as np
from numpy.testing import (assert_equal, assert_almost_equal, assert_allclose)
from pimsviewer.viewer import Viewer, ViewerPipeline, Slider
from pims import FramesSequence, FramesSequenceND


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
            return np.random.random(self._shape).astype(self._dtype)
        else:
            return np.random.randint(0, np.iinfo(self._dtype).max,
                                     self._shape).astype(self._dtype)


def add_noise(img, noise_level):
    return img + np.random.random(img.shape) * noise_level

class TestViewer(unittest.TestCase):
    def test_viewer_noreader(self):
        viewer = Viewer()
        viewer.show()

    def test_viewer_reader(self):
        viewer = Viewer(RandomReader())
        viewer.show()

    def test_viewer_pipeline(self):
        AddNoise = ViewerPipeline(add_noise, 'Add noise', dock='right') + \
                   Slider('noise_level', 0, 100, 0, orientation='vertical')
        viewer = Viewer(RandomReader()) + AddNoise
        viewer.show()


if __name__ == '__main__':
    nose.runmodule(argv=[__file__, '-vvs'], exit=False)
