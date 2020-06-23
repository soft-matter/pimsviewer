import os
import numpy as np
from PyQt5 import uic
from PyQt5.QtCore import QDir, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QImage, QPainter, QPalette, QPixmap
from PyQt5.QtWidgets import (QHBoxLayout, QSlider, QWidget, QAction, QApplication, QFileDialog, QLabel, QMainWindow, QMenu, QMessageBox, QScrollArea, QSizePolicy, QStatusBar, QVBoxLayout, QDockWidget, QPushButton, QStyle, QLineEdit, QCheckBox, QInputDialog)

class Dimension(QWidget):

    _playing = False
    _size = 0
    _position = 0
    _mergeable = False
    _merge = False
    _playable = False
    _fps = 5.0
    _max_playback_fps = 5.0

    play_event = pyqtSignal(QWidget)

    def __init__(self, name, size=0):
        super(Dimension, self).__init__()

        self.name = name
        self._size = size

        dirname = os.path.dirname(os.path.realpath(__file__))
        uic.loadUi(os.path.join(dirname, 'dimension.ui'), self)

        self.playButton.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.playButton.clicked.connect(self.click_event)

        self.playTimer = QTimer()
        self.playTimer.timeout.connect(self.play_tick)

        self.posButton.pressed.connect(self.update_position_from_btn)

        self.slider.setMaximum(self.size-1)
        self.slider.valueChanged.connect(self.update_position_from_slider)

        self.mergeButton.clicked.connect(self.update_merge)

        if not self.mergeable:
            self.mergeButton.hide()

        self._merge = self.mergeButton.isChecked()

        self.fps = self._fps
        self.fpsButton.pressed.connect(self.fps_changed)

        self.hide()

    def merge_image_over_dimension(self, image):
        # problem here: could be two axes with same size
        # TODO: think of a clever fix for this
        try:
            ix = image.shape.index(self._size)
        except ValueError:
            return image

        if self.name != 'c':
            # I don't know what to do, sum over axis
            image = np.sum(image, axis=ix)

        return image

    def enable(self):
        if not self.playable:
            return

        self.setEnabled(True)
        self.playButton.setEnabled(True)
        self.posButton.setEnabled(True)
        self.slider.setEnabled(True)
        self.fpsButton.setEnabled(True)

        if self.mergeable:
            self.mergeButton.setEnabled(True)
            self.mergeButton.show()

        self.show()

    def disable(self):
        self.setEnabled(False)
        self.playButton.setEnabled(False)
        self.posButton.setEnabled(False)
        self.slider.setEnabled(False)
        self.fpsButton.setEnabled(False)
        self.mergeButton.setEnabled(False)

    def fps_changed(self):
        fps, ok = QInputDialog.getDouble(self, "Playback framerate", "New playback framerate", self.fps)

        if ok:
            self.fps = fps

    def click_event(self):
        if not self.playable:
            return

        if not self.playing:
            self.playing = True
        else:
            self.playing = False

    def play_tick(self):
        if not self.playing:
            return

        if self._fps > self._max_playback_fps:
            self.position += int(round(self._fps / self._max_playback_fps))
        else:
            self.position += 1

    @property
    def size(self):
        return self._size

    @size.setter
    def size(self, size):
        self._size = size
        self.position = 0
        self.playing = False
        self.slider.setMinimum(0)
        self.slider.setMaximum(self.size-1)

    @property
    def fps(self):
        return self._fps

    @fps.setter
    def fps(self, fps):
        fps = float(fps)

        self._fps = fps
        play_fps = fps if fps < self._max_playback_fps else self._max_playback_fps
        self.playTimer.setInterval(int(round(1000.0 / play_fps)))
        self.fpsButton.setText('%d fps' % self.fps)

    @property
    def playable(self):
        return self._playable

    @playable.setter
    def playable(self, playable):
        self._playable = bool(playable)

    @property
    def playing(self):
        return self._playing

    @playing.setter
    def playing(self, playing):
        self._playing = bool(playing)
        if self._playing:
            self.playTimer.start()
        else:
            self.playTimer.stop()

    @property
    def position(self):
        return self._position

    def update_position_from_slider(self):
        position = self.slider.value()
        if position >= 0:
            self.position = position

    def update_position_from_btn(self):
        position, ok = QInputDialog.getInt(self, "'%s' position" % self.name, "New '%s' position (0-%d)" % (self.name, self.size-1), self.position, 0, self.size-1)

        if ok:
            self.position = position

    @position.setter
    def position(self, position):
        old_position = self.position

        while position < 0:
            position += self.size

        if position < self.size:
            self._position = position
        else:
            self._position = position - self.size

        self.slider.setValue(self.position)
        self.posButton.setText('%s=%d' % (self.name, self.position))

        if old_position != self.position:
            self.play_event.emit(self)

    def update_merge(self):
        self.merge = self.mergeButton.isChecked()

    @property
    def merge(self):
        return self._merge

    @merge.setter
    def merge(self, merge):
        if not self.mergeable:
            merge = False

        if merge != self._merge:
            self._merge = bool(merge)
            self.mergeButton.setChecked(self._merge)
            self.play_event.emit(self)

    @property
    def mergeable(self):
        return self._mergeable

    @mergeable.setter
    def mergeable(self, mergeable):
        self._mergeable = bool(mergeable)
        if not mergeable:
            self.merge = False

    def __len__(self):
        return self.size

    def __str__(self):
        classname = self.__class__.__name__
        playing = "playing" if self.playing else "not playing"
        return "<%s %s of length %d (%s)>" % (classname, self.name, self.size, playing)

    def __repr__(self):
        return self.__str__()

