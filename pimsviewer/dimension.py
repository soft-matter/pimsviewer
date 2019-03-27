from PyQt5.QtCore import QDir, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QImage, QPainter, QPalette, QPixmap
from PyQt5.QtWidgets import (QHBoxLayout, QSlider, QWidget, QAction, QApplication, QFileDialog, QLabel, QMainWindow, QMenu, QMessageBox, QScrollArea, QSizePolicy, QStatusBar, QVBoxLayout, QDockWidget, QPushButton, QStyle, QLineEdit, QCheckBox)

class Dimension(QWidget):

    _playing = False
    _size = 0
    _position = 0
    _mergeable = False
    _merge = True
    _playable = False
    _fps = 5.0

    play_event = pyqtSignal(QWidget)

    def __init__(self, name, size=0):
        super(Dimension, self).__init__()

        self.name = name
        self._size = size

        self.hbox = QHBoxLayout()
        self.hbox.addWidget(QLabel(self.name))

        self.playButton = QPushButton()
        self.playButton.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.playButton.setEnabled(False)
        self.playButton.setCheckable(True)
        self.playButton.clicked.connect(self.click_event)

        self.playTimer = QTimer()
        self.playTimer.setInterval(int(round(1000.0 / self.fps)))
        self.playTimer.timeout.connect(self.play_tick)

        self.hbox.addWidget(self.playButton)

        self.pos = QLineEdit()
        self.pos.setEnabled(False)
        self.pos.setFixedSize(30, 30)
        self.pos.textChanged[str].connect(self.update_position)
        self.hbox.addWidget(self.pos)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setSingleStep(1)
        self.slider.setPageStep(50)
        self.slider.setEnabled(False)
        self.slider.setMinimum(0)
        self.slider.setMaximum(self.size-1)
        self.slider.setTickPosition(QSlider.TicksBelow)
        self.slider.valueChanged.connect(self.update_position)
        self.hbox.addWidget(self.slider)

        self.merge_box = QCheckBox('Merge')
        self.merge_box.setChecked(True)
        self.merge_box.setEnabled(False)
        self.merge_box.stateChanged.connect(self.update_merge)
        if not self.mergeable:
            self.merge_box.hide()
        self.hbox.addWidget(self.merge_box)

        self.fps_edit = QLineEdit()
        self.fps_edit.setFixedSize(30, 30)
        self.fps_edit.setEnabled(False)
        self.fps_edit.setText('%.1f' % self.fps)
        self.fps_edit.textChanged[str].connect(self.fps_changed)
        self.hbox.addWidget(self.fps_edit)
        self.hbox.addWidget(QLabel('fps'))

        self.setLayout(self.hbox)
        self.hide()

    def enable(self):
        if not self.playable:
            return

        self.playButton.setEnabled(True)
        self.pos.setEnabled(True)
        self.slider.setEnabled(True)
        self.fps_edit.setEnabled(True)
        if self.mergeable:
            self.merge_box.setEnabled(True)
            self.merge_box.show()
        self.show()

    def disable(self):
        self.playButton.setEnabled(False)
        self.pos.setEnabled(False)
        self.slider.setEnabled(False)
        self.fps_edit.setEnabled(False)

    def fps_changed(self, text):
        self.fps = float(text)

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

        if fps > 10.0:
            fps = 10.0

        self._fps = fps
        self.playTimer.setInterval(int(round(1000.0 / self._fps)))

    @property
    def mergeable(self):
        return self._mergeable

    @mergeable.setter
    def mergeable(self, mergeable):
        self._mergeable = bool(mergeable)

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

    def update_position(self, position):
        try:
            position = int(round(float(position)))
        except ValueError:
            return
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
        self.pos.setText('%d' % self.position)

        if old_position != self.position:
            self.play_event.emit(self)

    def update_merge(self, state):
        merge = (state == Qt.Checked)
        if merge != self.merge:
            self.merge = merge
            self.play_event.emit(self)

    @property
    def merge(self):
        return self._merge

    @merge.setter
    def merge(self, merge):
        self._merge = bool(merge)
        self.merge_box.setChecked(self._merge)

    def should_set_default_coord(self):
        if not self.mergeable and self.playable:
            return True

        if self.mergeable and not self.merge:
            return True

        return False

    def __len__(self):
        return self.size

    def __str__(self):
        classname = self.__class__.__name__
        playing = "playing" if self.playing else "not playing"
        return "<%s %s of length %d (%s)>" % (classname, self.name, self.size, playing)

    def __repr__(self):
        return self.__str__()

