from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
import functools
import numpy as np
import pims
from pims import to_rgb, normalize
from pims.base_frames import FramesSequence, FramesSequenceND
from pims.utils.sort import natural_keys
from itertools import chain
from os import listdir, path
from os.path import isfile, join

from PIL import Image, ImageQt
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QPixmap

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

def get_all_files_in_dir(directory, extensions=None):
    if extensions is None:
        file_list = [f for f in listdir(directory) if isfile(join(directory, f))]
    else:
        file_list = [f for f in listdir(directory) if isfile(join(directory, f))
                     and drop_dot(path.splitext(f)[1]) in extensions]

    return sorted(file_list, key=natural_keys)

def pixmap_from_array(array):
    # Convert to image
    image = Image.fromarray(array)
    pixmap = ImageQt.toqpixmap(image)

    return pixmap

def image_to_pixmap(image):
    flags = Qt.ImageConversionFlags(Qt.ColorOnly & Qt.DiffuseDither)
    pixmap = QPixmap.fromImage(image, flags)

    return pixmap
