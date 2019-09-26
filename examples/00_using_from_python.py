import sys
from pimsviewer import GUI
from PyQt5.QtWidgets import QApplication

filepath = 'path/to/file'

# Class names of extra plugins to add
plugins = []

app = QApplication(sys.argv)
gui = GUI(extra_plugins=plugins)
gui.open(fileName=filepath)
gui.show()

sys.exit(app.exec_())
