from pims import FramesSequenceND
import numpy as np

class WrappedReader(object):
    def __init__(self, reader):
        super(WrappedReader, self).__init__()
        self.reader = reader

        self._fallback_sizes = {}
        self._fallback_axis_order = {}

    def __getattr__(self, attr):
        if hasattr(self.reader, attr):
            value = getattr(self.reader, attr)
            self.setattr_only_self(attr, value)
            return value
        else:
            return self.get_fallback_function(attr)

    def setattr_only_self(self, attr, value):
        self.__dict__[attr] = value

    def __setattr__(self, attr, value):
        self.setattr_only_self(attr, value)

        if attr not in ['reader', '_fallback_sizes', '_fallback_axis_order']:
            setattr(self.reader, attr, value)

    def get_fallback_function(self, attr):
        if attr == 'sizes':
            return self.fallback_sizes

        if attr == 'default_coords':
            return self.fallback_def_coords

        raise AttributeError("Attribute '%s' not found in WrappedReader" % attr)

    def __getitem__(self, key):
        if isinstance(self.reader, FramesSequenceND):
            return self.reader[key]
        else:
            # provide a fallback for the FramesSequenceND behaviour
            frame = self.reader[0]
            index_values = []
            index_order = []
            for dim in self.sizes:
                if dim == 't':
                    continue

                if dim in self.bundle_axes:
                    index_values.append(slice(None))
                    index_order.append(self.fallback_axis_order[dim])
                elif dim in self.iter_axes:
                    index_values.append(key)
                    index_order.append(self.fallback_axis_order[dim])
                else:
                    index_values.append(self.fallback_def_coords[dim])
                    index_order.append(self.fallback_axis_order[dim])

            index_order, index_values = (t for t in zip(*sorted(zip(index_order, index_values))))

            return frame[index_values]

    def __len__(self):
        return len(self.reader)

    def __iter__(self):
        return iter(self.reader[:])

    def __enter__(self):
        return self.reader

    def __exit__(self):
        self.close()

    def __repr__(self):
        return "<<WrappedReader: %s>>" % str(self.reader)

    def close(self):
        try:
            self.reader.close()
        except AttributeError:
            return

    @property
    def fallback_axis_order(self):
        if len(self._fallback_axis_order) > 0:
            return self._fallback_axis_order
        _ = self.fallback_sizes
        # set inside fallback_sizes()
        return self._fallback_axis_order

    @property
    def fallback_sizes(self):
        if len(self._fallback_sizes) > 0:
            return self._fallback_sizes

        order = {}
        sizes = {}

        sizes['t'] = len(self.reader)

        frame_shape = self.reader.frame_shape
        to_process = np.arange(0, len(frame_shape), 1)

        if len(to_process) > 2:
            c_ix = np.argmin(frame_shape)
            sizes['c'] = frame_shape[c_ix]
            order['c'] = c_ix
            to_process = np.delete(to_process, c_ix)

        if len(to_process) == 3:
            sizes['z'] = frame_shape[-1]
            order['z'] = to_process[-1]
            to_process = np.delete(to_process, -1)

        sizes['y'] = frame_shape[0]
        order['y'] = 0
        sizes['x'] = frame_shape[1]
        order['x'] = 1

        self._fallback_sizes = sizes
        self._fallback_axis_order = order

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
