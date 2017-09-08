from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import six
from pimsviewer.qt import Qt, QtWidgets, QtCore, QtGui, Signal
from time import time
import math
import numpy as np

from skimage.viewer.widgets import BaseWidget, CheckBox, Text, ComboBox


class DockWidget(QtWidgets.QDockWidget):
    """A QDockWidget that emits a signal when closed."""
    close_event_signal = Signal()
    def closeEvent(self, event):
        self.close_event_signal.emit()
        super(DockWidget, self).closeEvent(event)


class VideoTimer(QtCore.QTimer):
    next_frame = Signal(int)
    def __init__(self, *args, **kwargs):
        super(VideoTimer, self).__init__(*args, **kwargs)
        self.timeout.connect(self.update)
        self.index = None
        self._len = None
        self.start_time = None
        self.start_index = None

    @property
    def fps(self):
        return 1 / self._interval
    @fps.setter
    def fps(self, value):
        if value is None or not np.isfinite(value):
            value = 25.
        self._interval = 1 / value
        self.setInterval(abs(self._interval) * 1000)
        self.reset(self.index) # restart index calculation because of different fps

    def start(self, index, length):
        self.start_index = index
        self.start_time = time()
        self._len = length
        super(VideoTimer, self).start()

    def stop(self):
        super(VideoTimer, self).stop()
        self.start_index = None
        self.start_time = None
        self._len = None

    def reset(self, index):
        if self.start_time is not None:
            self.start_time = time()
            self.start_index = index

    def update(self):
        self.index = (int((time() - self.start_time) // self._interval) +
                      self.start_index) % self._len
        self.next_frame.emit(self.index)


# copied from skimage.viewer.widgets with some slight changes
class Slider(BaseWidget):
    """Slider widget for adjusting numeric parameters.

    Parameters
    ----------
    name : str
        Name of slider parameter. If this parameter is passed as a keyword
        argument, it must match the name of that keyword argument (spaces are
        replaced with underscores). In addition, this name is displayed as the
        name of the slider.
    low, high : float
        Range of slider values.
    value : float
        Default slider value. If None, use midpoint between `low` and `high`.
    value_type : {'float' | 'int'}, optional
        Numeric type of slider value.
    ptype : {'kwarg' | 'arg' | 'plugin'}, optional
        Parameter type.
    callback : callable f(widget_name, value), optional
        Callback function called in response to slider changes.
        *Note:* This function is typically set (overridden) when the widget is
        added to a plugin.
    orientation : {'horizontal' | 'vertical'}, optional
        Slider orientation.
    update_on : {'release' | 'move'}, optional
        Control when callback function is called: on slider move or release.
    """
    def __init__(self, name, low=0.0, high=1.0, value=None, value_type='float',
                 ptype='kwarg', callback=None, max_edit_width=60,
                 orientation='horizontal', update_on='release'):
        super(Slider, self).__init__(name, ptype, callback)

        if value is None:
            value = (high - low) / 2.

        # Set widget orientation
        #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        if orientation == 'vertical':
            self.slider = QtWidgets.QSlider(Qt.Vertical)
            alignment = QtCore.Qt.AlignHCenter
            align_text = QtCore.Qt.AlignHCenter
            align_value = QtCore.Qt.AlignHCenter
            self.layout = QtWidgets.QVBoxLayout(self)
        elif orientation == 'horizontal':
            self.slider = QtWidgets.QSlider(Qt.Horizontal)
            alignment = QtCore.Qt.AlignVCenter
            align_text = QtCore.Qt.AlignLeft
            align_value = QtCore.Qt.AlignRight
            self.layout = QtWidgets.QHBoxLayout(self)
        else:
            msg = "Unexpected value %s for 'orientation'"
            raise ValueError(msg % orientation)
        #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

        # Set slider behavior for float and int values.
        #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        if value_type == 'float':
            # divide slider into 1000 discrete values
            slider_max = 1000
            self._scale = float(high - low) / slider_max
            self.slider.setRange(0, slider_max)
            self.value_fmt = '%2.2f'
        elif value_type == 'int':
            self.slider.setRange(low, high)
            self.value_fmt = '%d'
        else:
            msg = "Expected `value_type` to be 'float' or 'int'; received: %s"
            raise ValueError(msg % value_type)
        #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

        self.value_type = value_type
        self._low = low
        self._high = high
        # Update slider position to default value
        self.val = value

        if update_on == 'move':
            self.slider.valueChanged.connect(self._on_slider_changed)
        elif update_on == 'release':
            self.slider.sliderReleased.connect(self._on_slider_changed)
        else:
            raise ValueError("Unexpected value %s for 'update_on'" % update_on)
        self.slider.setFocusPolicy(QtCore.Qt.StrongFocus)

        self.name_label = QtWidgets.QLabel()
        self.name_label.setText(self.name)
        self.name_label.setAlignment(align_text)

        self.editbox = QtWidgets.QLineEdit()
        self.editbox.setMaximumWidth(max_edit_width)
        self.editbox.setText(self.value_fmt % self.val)
        self.editbox.setAlignment(align_value)
        self.editbox.editingFinished.connect(self._on_editbox_changed)

        self.layout.addWidget(self.name_label)
        self.layout.addWidget(self.slider)
        self.layout.addWidget(self.editbox)

    def _on_slider_changed(self):
        """Call callback function with slider's name and value as parameters"""
        self.val = self.val

    def _on_editbox_changed(self):
        """Validate input and set slider value"""
        try:
            value = float(self.editbox.text())
        except ValueError:
            self._bad_editbox_input()
            return
        if not self._low <= value <= self._high:
            self._bad_editbox_input()
            return

        self.val = value
        self._good_editbox_input()

    def _good_editbox_input(self):
        self.editbox.setStyleSheet("background-color: rgb(255, 255, 255)")

    def _bad_editbox_input(self):
        self.editbox.setStyleSheet("background-color: rgb(255, 200, 200)")

    @property
    def val(self):
        value = self.slider.value()
        if self.value_type == 'float':
            return value * self._scale + self._low
        else:
            return value

    @val.setter
    def val(self, value):
        try:
            self.editbox.setText(self.value_fmt % value)
        except AttributeError:
            pass
        if self.value_type == 'float':
            slider_value = (value - self._low) / self._scale
        else:
            slider_value = int(value)
        self.slider.setValue(slider_value)

        if self.callback is not None:
            self.callback(self.name, value)


class Button(BaseWidget):
    def __init__(self, name=None, caption='', callback=None):
        super(Button, self).__init__(name)
        self._button = QtWidgets.QPushButton(caption)
        self._button.setDefault(False)
        self.layout = QtWidgets.QHBoxLayout(self)
        self.layout.addWidget(self._button)
        if callback is not None:
            self.callback = callback
            self._button.clicked.connect(self.on_click)

    def on_click(self):
        self._button.clearFocus()
        self.callback()


class QWidgetMinSize(QtWidgets.QWidget):
    def __init__(self, min_size, *args, **kwargs):
        super(QWidgetMinSize, self).__init__(*args, **kwargs)
        self._min_size = QtCore.QSize(*min_size)
        self.setSizePolicy(QtGui.QSizePolicy.Preferred,
                           QtGui.QSizePolicy.Preferred)

    def minimumSizeHint(self):
        return self._min_size
