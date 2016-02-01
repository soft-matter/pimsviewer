from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import six
import numpy as np
from abc import abstractmethod
from warnings import warn

from pims import Frame, FramesSequence


class reads_axes(object):
    def __init__(self, axes):
        self.axes = tuple([ax for ax in axes])

    def __call__(self, func):
        func._axes = self.axes
        return func

def _iter_attr(obj):
    try:
        for ns in [obj] + obj.__class__.mro():
            for attr in ns.__dict__:
                yield ns.__dict__[attr]
    except AttributeError:
        raise StopIteration  # obj has no __dict__

class FramesSequenceND(FramesSequence):
    """ A base class defining a FramesSequence with an arbitrary number of
    axes. In the context of this reader base class, dimensions like 'x', 'y',
    't' and 'z' will be called axes. Indices along these axes will be called
    coordinates.

    The properties `bundle_axes`, `iter_axes`, and `default_coords` define
    to which coordinates each index points. See below for a description of
    each attribute.

    Subclassed readers only need to define `get_frame_2D`, `pixel_type` and
    `__init__`. In the `__init__`, at least axes y and x need to be
    initialized using `_init_axis(name, size)`.

    The attributes `__len__`, `frame_shape`, and `get_frame` are defined by
    this base_class; these are not meant to be changed.

    Attributes
    ----------
    axes : list of strings
        List of all available axes
    ndim : int
        Number of image axes
    sizes : dict of int
        Dictionary with all axis sizes
    frame_shape : tuple of int
        Shape of frames that will be returned by get_frame
    iter_axes : iterable of strings
        This determines which axes will be iterated over by the FramesSequence.
        The last element in will iterate fastest. x and y are not allowed.
    bundle_axes : iterable of strings
        This determines which axes will be bundled into one Frame. The axes in
        the ndarray that is returned by get_frame have the same order as the
        order in this list. The last two elements have to be ['y', 'x'].
    default_coords: dict of int
        When an axis is not present in both iter_axes and bundle_axes, the
        coordinate contained in this dictionary will be used.

    Examples
    --------
    >>> class MDummy(FramesSequenceND):
    ...    @property
    ...    def pixel_type(self):
    ...        return 'uint8'
    ...    def __init__(self, shape, **axes):
    ...        self._init_axis('y', shape[0])
    ...        self._init_axis('x', shape[1])
    ...        for name in axes:
    ...            self._init_axis(name, axes[name])
    ...    def get_frame_2D(self, **ind):
    ...        return np.zeros((self.sizes['y'], self.sizes['x']),
    ...                        dtype=self.pixel_type)

    >>> frames = MDummy((64, 64), t=80, c=2, z=10, m=5)
    >>> frames.bundle_axes = 'czyx'
    >>> frames.iter_axes = 't'
    >>> frames.default_coords['m'] = 3
    >>> frames[5]  # returns Frame at T=5, M=3 with shape (2, 10, 64, 64)
    """
    get_frame_dict = dict()
    def _clear_axes(self):
        self._sizes = {}
        self._default_coords = {}
        self._iter_axes = []
        self._bundle_axes = ['y', 'x']

    def _init_axis(self, name, size, default=0):
        # check if the axes have been initialized, if not, do it here
        if not hasattr(self, '_sizes'):
            self._clear_axes()
        elif name in self._sizes:
            raise ValueError("axis '{}' already exists".format(name))
        self._sizes[name] = int(size)
        if not (name == 'x' or name == 'y'):
            self.default_coords[name] = int(default)

    def __len__(self):
        return int(np.prod([self._sizes[d] for d in self._iter_axes]))

    @property
    def frame_shape(self):
        """ Returns the shape of the frame as returned by get_frame. """
        return tuple([self._sizes[d] for d in self._bundle_axes])

    @property
    def axes(self):
        """ Returns a list of all axes. """
        return [k for k in self._sizes]

    @property
    def ndim(self):
        """ Returns the number of axes. """
        return len(self._sizes)

    @property
    def sizes(self):
        """ Returns a dict of all axis sizes. """
        return self._sizes

    @property
    def bundle_axes(self):
        """ This determines which axes will be bundled into one Frame.
        The ndarray that is returned by get_frame has the same axis order
        as the order of `bundle_axes`.
        The last two elements have to be ['y', 'x'].
        """
        return self._bundle_axes

    @bundle_axes.setter
    def bundle_axes(self, value):
        invalid = [k for k in value if k not in self._sizes]
        if invalid:
            raise ValueError("axes %r do not exist" % invalid)

        if 'x' not in value or 'y' not in value:
            raise ValueError("bundle_axes should contain ['y', 'x']")

        for k in value:
            if k in self._iter_axes:
                del self._iter_axes[self._iter_axes.index(k)]

        self._bundle_axes = list(value)

    @property
    def iter_axes(self):
        """ This determines which axes will be iterated over by the
        FramesSequence. The last element will iterate fastest.
        x and y are not allowed. """
        return self._iter_axes

    @iter_axes.setter
    def iter_axes(self, value):
        invalid = [k for k in value if k not in self._sizes]
        if invalid:
            raise ValueError("axes %r do not exist" % invalid)

        if 'x' in value or 'y' in value:
            raise ValueError("axes 'y' and 'x' cannot be iterated")

        for k in value:
            if k in self._bundle_axes:
                del self._bundle_axes[self._bundle_axes.index(k)]

        self._iter_axes = list(value)

    @property
    def default_coords(self):
        """ When a axis is not present in both iter_axes and bundle_axes, the
        coordinate contained in this dictionary will be used. """
        return self._default_coords

    @default_coords.setter
    def default_coords(self, value):
        invalid = [k for k in value if k not in self._sizes]
        if invalid:
            raise ValueError("axes %r do not exist" % invalid)
        if 'x' in value or 'y' in value:
            raise ValueError("axes 'y' and 'x' cannot have a default "
                             "coordinate")
        self._default_coords.update(**value)

    @abstractmethod
    def get_frame_2D(self, **ind):
        """ The actual frame reader, defined by the subclassed reader.

        This method should take exactly one keyword argument per axis,
        reflecting the coordinate along each axis. It returns a two dimensional
        ndarray with shape (sizes['y'], sizes['x']) and dtype `pixel_type`. It
        may also return a Frame object, so that metadata will be propagated. It
        will only propagate metadata if every bundled frame gives the same
        fields.
        """
        pass

    def get_frame(self, i):
        """ Returns a Frame of shape determined by bundle_axes. The index value
        is interpreted according to the iter_axes property. Coordinates not
        present in both iter_axes and bundle_axes will be set to their default
        value (see default_coords). """
        if i > len(self):
            raise IndexError('index out of range')
        for method in _iter_attr(self):
            if hasattr(method, '_axes'):
                self.get_frame_dict[method._axes] = method.__name__

        # start with the default coordinates
        coords = self._default_coords.copy()

        # list sizes of iterate axes
        iter_sizes = [self._sizes[k] for k in self._iter_axes]
        # list how much i has to increase to get an increase of coordinate n
        iter_cumsizes = np.append(np.cumprod(iter_sizes[::-1])[-2::-1], 1)
        # calculate the coordinates and update the coords dictionary
        iter_coords = (i // iter_cumsizes) % iter_sizes
        coords.update(**{k: v for k, v in zip(self._iter_axes, iter_coords)})

        shape = self.frame_shape
        # search for get_frame methods that return the correct axes
        if tuple(self.bundle_axes) in self.get_frame_dict:
            get_frame = getattr(self, self.get_frame_dict[tuple(self.bundle_axes)])
            transpose = None
        else:
            bundle_axes_set = set(self.bundle_axes)
            # search for get_frame methods that return axes in different order
            for method_axes in self.get_frame_dict:
                if len(set(method_axes) ^ bundle_axes_set) == 0:
                    get_frame = getattr(self, self.get_frame_dict[method_axes])
                    transpose = [method_axes.index(b) for b in self.bundle_axes]
                    break
            # list all get_frame that do not return too many axes
            methods = [g for g in self.get_frame_dict if len(set(g) - bundle_axes_set) == 0]

            # search for get_frame methods that return axes in different order
            for method_axes in self.get_frame_dict:
                if len(set(method_axes) ^ set(self.bundle_axes)) == 0:
                    get_frame = getattr(self, self.get_frame_dict[method_axes])
                    transpose = [method_axes.index(b) for b in self.bundle_axes]
                    break

            result = get_frame(**coords)
            if hasattr(result, 'metadata'):
                metadata = result.metadata
            else:
                metadata = None
            result = result.transpose([method_axes.index(b) for b in self.bundle_axes])

        for method_axes in self.get_frame_dict:
            # search for get_frame methods with same axes
            if len(set(method_axes) ^ set(self.bundle_axes)) == 0:
                get_frame = getattr(self, self.get_frame_dict[method_axes])
                result = get_frame(**coords)
                if hasattr(result, 'metadata'):
                    metadata = result.metadata
                else:
                    metadata = None
                result = result.transpose([method_axes.index(b) for b in self.bundle_axes])
                break
        else:  # general case of N dimensional frame
            Nframes = int(np.prod(shape[:-2]))
            result = np.empty([Nframes] + list(shape[-2:]),
                              dtype=self.pixel_type)

            # zero out all coords that will be bundled
            coords.update(**{k: 0 for k in self._bundle_axes[:-2]})
            # read all 2D frames and properly iterate through the coordinates
            mdlist = [{}] * Nframes
            for n in range(Nframes):
                frame = self.get_frame_2D(**coords)
                result[n] = frame
                if hasattr(frame, 'metadata'):
                    mdlist[n] = frame.metadata
                for dim in self._bundle_axes[-3::-1]:
                    coords[dim] += 1
                    if coords[dim] >= self._sizes[dim]:
                        coords[dim] = 0
                    else:
                        break
            # reshape the array into the desired shape
            result.shape = shape


            # propagate metadata
            metadata = {}
            if not np.all([md == {} for md in mdlist]):
                keys = mdlist[0].keys()
                for k in keys:
                    try:
                        metadata[k] = [row[k] for row in mdlist]
                    except KeyError:
                        # if a field is not present in every frame, ignore it
                        warn('metadata field {} is not propagated')
                    else:
                        # if all values are equal, only return one value
                        if metadata[k][1:] == metadata[k][:-1]:
                            metadata[k] = metadata[k][0]
                        else:  # cast into ndarray
                            metadata[k] = np.array(metadata[k])
                            metadata[k].shape = shape[:-2]

        return Frame(result, frame_no=i, metadata=metadata)

    def __repr__(self):
        s = "<FramesSequenceND>\nAxes: {0}\n".format(self.ndim)
        for dim in self._sizes:
            s += "Axis '{0}' size: {1}\n".format(dim, self._sizes[dim])
        s += """Pixel Datatype: {dtype}""".format(dtype=self.pixel_type)
        return s
