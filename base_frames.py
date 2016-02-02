from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import six
import numpy as np
from abc import abstractmethod
from warnings import warn
from itertools import product

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


def _transpose(get_frame, transposition):
    def get_frame_T(self, **ind):
        return get_frame(self, **ind).transpose(transposition)
    return get_frame_T


def _bundle(get_frame, shape, names, dtype):
    iter_shape = shape[:len(names)]
    def get_frame_bundled(self, **ind):
        result = np.empty(shape, dtype=dtype)
        md_list = []
        for indices in product(*[range(s) for s in iter_shape]):
            ind.update({n: i for n, i in zip(names, indices)})
            frame = get_frame(self, **ind)
            result[indices] = frame

            if hasattr(frame, 'metadata'):
                if frame.metadata is not None:
                    md_list.append(frame.metadata)

        # propagate metadata
        if len(md_list) == np.prod(iter_shape):
            metadata = dict()
            keys = md_list[0].keys()
            for k in keys:
                try:
                    metadata[k] = [row[k] for row in md_list]
                except KeyError:
                    # if a field is not present in every frame, ignore it
                    warn('metadata field {} is not propagated')
                else:
                    # if all values are equal, only return one value
                    if metadata[k][1:] == metadata[k][:-1]:
                        metadata[k] = metadata[k][0]
                    else:  # cast into ndarray
                        metadata[k] = np.array(metadata[k])
                        metadata[k].shape = iter_shape
        else:
            metadata = None
        return Frame(result, metadata=metadata)
    return get_frame_bundled


def _drop(get_frame, axes, names):
    # sort axes in descending order for correct function of np.take
    indices = np.argsort(axes)
    axes = [axes[i] for i in reversed(indices)]
    names = [names[i] for i in reversed(indices)]

    def get_frame_dropped(self, **ind):
        result = get_frame(self, **ind)
        for (ax, name) in zip(axes, names):
            result = np.take(result, ind[name], axis=ax)
        return result
    return get_frame_dropped


def _make_get_frame(result_axes, get_frame_dict, sizes, dtype):
    if len(get_frame_dict) == 0:
        raise RuntimeError("No get_frame functions registered in this reader.")
    result_axes = tuple([a for a in result_axes])

    # search for methods that return the correct axes
    if result_axes in get_frame_dict:
        return get_frame_dict[result_axes]

    # search for get_frame methods that return axes in different order
    result_axes_set = set(result_axes)
    for axes in get_frame_dict:
        if len(set(axes) ^ result_axes_set) == 0:
            transposition = [axes.index(a) for a in result_axes]
            return _transpose(get_frame_dict[axes], transposition)

    # list all get_frame that do not return too many axes
    less = [gf for gf in get_frame_dict if len(set(gf) - result_axes_set) == 0]
    if len(less) > 0:
        # list missing axes for each method
        to_iter = [result_axes_set - set(gf) for gf in less]
        # count number of calls to get_frame necessary to build result
        n_iter = np.prod([[sizes[ax] for ax in it] for it in to_iter], 1)
        # use the one with the lowest number of iterations
        i = int(np.argmin(n_iter))
        get_frame_axes = less[i]
        to_iter = list(to_iter[i])
        bundled_axes = to_iter + list(get_frame_axes)
        shape = [sizes[a] for a in bundled_axes]
        get_frame = _bundle(get_frame_dict[get_frame_axes], shape, to_iter,
                            dtype)
        if not bundled_axes == list(result_axes):
            transposition = [bundled_axes.index(a) for a in result_axes]
            return _transpose(get_frame, transposition)
        else:
            return get_frame

    # list all that have too many axes, but do have all necessary ones
    more = [gf for gf in get_frame_dict if result_axes_set.issubset(set(gf))]
    if len(more) > 0:
        # list superfluous axes for each method
        to_drop = [set(gf) - result_axes_set for gf in more]
        # count number of superfluous frames that will be read
        n_drop = np.prod([[sizes[ax] for ax in dr] for dr in to_drop], 1)
        # use the one with the lowest number of superfluous frames
        i = int(np.argmin(n_drop))
        get_frame_axes = more[i]
        to_drop = list(to_drop[i])
        to_drop_inds = [list(get_frame_axes).index(a) for a in to_drop]
        result_axes_drop = [a for a in get_frame_axes if a in result_axes_set]
        get_frame = _drop(get_frame_dict[get_frame_axes], to_drop_inds, to_drop)

        if not result_axes_drop == list(result_axes):
            transposition = [result_axes_drop.index(a) for a in result_axes]
            return _transpose(get_frame, transposition)
        else:
            return get_frame

    # TODO: list all get_frame that do return too many axes
    raise NotImplemented("Not all possible get_frame methods have been implemented")


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
    def _clear_axes(self):
        self._sizes = {}
        self._default_coords = {}
        self._iter_axes = []
        self._bundle_axes = ['y', 'x']
        self._gf_wrapped = None

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
        self._gf_wrapped = _make_get_frame(self.bundle_axes, self._gf_dict,
                                           self.sizes, self.pixel_type)

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
    def _gf_dict(self):
        result = dict()
        for method in _iter_attr(self):
            if hasattr(method, '_axes'):
                result[method._axes] = method
        return result

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

    def get_frame(self, i):
        """ Returns a Frame of shape determined by bundle_axes. The index value
        is interpreted according to the iter_axes property. Coordinates not
        present in both iter_axes and bundle_axes will be set to their default
        value (see default_coords). """
        if i > len(self):
            raise IndexError('index out of range')
        if self._gf_wrapped is None:
            self._gf_wrapped = _make_get_frame(self.bundle_axes, self._gf_dict,
                                               self.sizes, self.pixel_type)

        # start with the default coordinates
        coords = self._default_coords.copy()

        # list sizes of iteration axes
        iter_sizes = [self._sizes[k] for k in self._iter_axes]
        # list how much i has to increase to get an increase of coordinate n
        iter_cumsizes = np.append(np.cumprod(iter_sizes[::-1])[-2::-1], 1)
        # calculate the coordinates and update the coords dictionary
        iter_coords = (i // iter_cumsizes) % iter_sizes
        coords.update(**{k: v for k, v in zip(self._iter_axes, iter_coords)})

        result = self._gf_wrapped(self, **coords)
        result.frame_no = i
        return result

    def __repr__(self):
        s = "<FramesSequenceND>\nAxes: {0}\n".format(self.ndim)
        for dim in self._sizes:
            s += "Axis '{0}' size: {1}\n".format(dim, self._sizes[dim])
        s += """Pixel Datatype: {dtype}""".format(dtype=self.pixel_type)
        return s
