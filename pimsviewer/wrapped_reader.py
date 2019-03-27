from pims import FramesSequenceND
import numpy as np

class WrappedReader(object):
    def __init__(self, reader):
        super(WrappedReader, self).__init__()
        self.reader = reader

    def __getattr__(self, attr):
        try:
            return self.reader.__getattr__(attr)
        except AttributeError:
            return self.get_fallback_function(attr)

    def get_fallback_function(self, attr):
        if attr == 'sizes':
            return self.fallback_sizes

        if attr == 'default_coords':
            return self.fallback_def_coords

        raise AttributeError("Attribute '%s' not found in WrappedReader" % attr)

    def __getitem__(self, key):
        return self.reader[key]

    def __len__(self):
        return len(self.reader)

    def __iter__(self):
        return iter(self.reader[:])

    def __enter__(self):
        return self.reader

    def __exit__(self):
        self.reader.close()

    def __repr__(self):
        return "<<WrappedReader: %s>>" % str(self.reader)

    @property
    def fallback_sizes(self):
        sizes = {}

        sizes['t'] = len(self.reader)

        frame_shape = self.reader.frame_shape
        to_process = np.arange(0, len(frame_shape), 1)

        if len(to_process) > 2:
            c_ix = np.argmin(frame_shape)
            sizes['c'] = frame_shape[c_ix]
            np.delete(to_process, c_ix)

        if len(to_process) == 3:
            sizes['z'] = frame_shape[-1]
            np.delete(to_process, -1)

        sizes['y'] = frame_shape[0]
        sizes['x'] = frame_shape[1]

        return sizes

    @property
    def fallback_def_coords(self):
        coords = self.fallback_sizes
        for dim in coords:
            coords[dim] = 0
        return coords

    @fallback_def_coords.setter
    def fallback_def_coords(self, value):
        pass




