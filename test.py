from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import six

import os
import unittest
import nose
import numpy as np
from numpy.testing import (assert_equal, assert_almost_equal, assert_allclose)
from pimsviewer import Viewer, ViewerPipeline, Slider, ViewerAnnotate
from pims import FramesSequence, Frame, pipeline
from pimsviewer.base_frames import FramesSequenceND, reads_axes
import pandas as pd

from types import MethodType
from itertools import chain, permutations

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


@pipeline
def add_noise(img, noise_level):
    return img + (np.random.random(img.shape) * noise_level).astype(img.dtype)

AddNoise = ViewerPipeline(add_noise, 'Add noise', dock='right') + \
           Slider('noise_level', 0, 100, 0, orientation='vertical')

@pipeline
def no_red(img, level):
    img[:, :, 0] = level
    return img

NoRed = ViewerPipeline(no_red, 'No red', dock='left') + \
                       Slider('level', 0, 100, 0, orientation='vertical')


class RandomReaderND(FramesSequenceND):
    def __init__(self, mode, **sizes):
        self._dtype = np.uint8
        for key in sizes:
            self._init_axis(key, sizes[key])
        self.shape = tuple([sizes[key] for key in mode])
        def _get_frame(self, **inds):
            return np.random.randint(0, 255, shape).astype(self._dtype)
        self._get_frame = MethodType((_get_frame), self)
        self._get_frame = reads_axes(mode)(self._get_frame)

    @property
    def pixel_type(self):
        return self._dtype


class TestFramesSequenceND(unittest.TestCase):
    def test_reader_x(self):
        class RandomReader_x(FramesSequenceND):
            def __init__(self, **sizes):
                for key in sizes:
                    self._init_axis(key, sizes[key])

            @reads_axes('x')
            def _get_frame(self, **ind):
                return np.random.randint(0, 255, (128,)).astype(np.uint8)

            @property
            def pixel_type(self):
                return np.uint8

        sizes = dict(x=128, y=64, c=3, z=10)
        all_modes = chain(*[permutations(sizes, x)
                            for x in range(1, len(sizes) + 1)])
        reader = RandomReader_x(**sizes)
        for bundle in all_modes:
            reader.bundle_axes = bundle
            assert_equal(reader[0].shape, [sizes[k] for k in bundle])

    def test_reader_yx(self):
        class RandomReader_yx(FramesSequenceND):
            def __init__(self, **sizes):
                for key in sizes:
                    self._init_axis(key, sizes[key])

            @reads_axes('yx')
            def _get_frame(self, **ind):
                return np.random.randint(0, 255, (64, 128)).astype(np.uint8)

            @property
            def pixel_type(self):
                return np.uint8

        sizes = dict(x=128, y=64, c=3, z=10)
        all_modes = chain(*[permutations(sizes, x)
                            for x in range(1, len(sizes) + 1)])
        reader = RandomReader_yx(**sizes)
        for bundle in all_modes:
            reader.bundle_axes = bundle
            assert_equal(reader[0].shape, [sizes[k] for k in bundle])

    def test_reader_yxc(self):
        class RandomReader_yxc(FramesSequenceND):
            def __init__(self, **sizes):
                for key in sizes:
                    self._init_axis(key, sizes[key])

            @reads_axes('yxc')
            def _get_frame(self, **ind):
                return np.random.randint(0, 255, (64, 128, 3)).astype(np.uint8)

            @property
            def pixel_type(self):
                return np.uint8

        sizes = dict(x=128, y=64, c=3, z=10)
        all_modes = chain(*[permutations(sizes, x)
                            for x in range(1, len(sizes) + 1)])
        reader = RandomReader_yxc(**sizes)
        for bundle in all_modes:
            reader.bundle_axes = bundle
            assert_equal(reader[0].shape, [sizes[k] for k in bundle])

    def test_reader_compatibility(self):
        class RandomReader_2D(FramesSequenceND):
            def __init__(self, **sizes):
                for key in sizes:
                    self._init_axis(key, sizes[key])

            def get_frame_2D(self, **ind):
                return np.random.randint(0, 255, (64, 128)).astype(np.uint8)

            @property
            def pixel_type(self):
                return np.uint8

        sizes = dict(x=128, y=64, c=3, z=10)
        all_modes = chain(*[permutations(sizes, x)
                            for x in range(1, len(sizes) + 1)])
        reader = RandomReader_2D(**sizes)
        for bundle in all_modes:
            reader.bundle_axes = bundle
            assert_equal(reader[0].shape, [sizes[k] for k in bundle])


class TestViewer(unittest.TestCase):
    def test_viewer_noreader(self):
        viewer = Viewer()
        viewer.show()

    def test_viewer_2d(self):
        viewer = Viewer(RandomReader(shape=(128, 128)))
        viewer.show()

    def test_viewer_rgb(self):
        viewer = Viewer(RandomReader(shape=(128, 128, 3)))
        viewer.show()

    def test_viewer_multichannel(self):
        viewer = Viewer(RandomReader(shape=(2, 128, 128)))
        viewer.show()

    def test_viewer_3d(self):
        viewer = Viewer(RandomReader(shape=(10, 128, 128)))
        viewer.show()

    def test_viewer_3d_rgb(self):
        viewer = Viewer(RandomReader(shape=(10, 128, 128, 3)))
        viewer.show()

    def test_viewer_3d_multichannel(self):
        viewer = Viewer(RandomReader(shape=(3, 10, 128, 128)))
        viewer.show()

    def test_viewer_pipeline(self):
        viewer = Viewer(RandomReader()) + AddNoise
        viewer.show()

    def test_viewer_pipeline_multiple(self):
        viewer = Viewer(RandomReader(shape=(128, 128, 3))) + AddNoise + NoRed
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
