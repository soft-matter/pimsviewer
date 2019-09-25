import sys
from pimsviewer import GUI
from PyQt5.QtWidgets import QApplication
import numpy as np

import sys
import unittest
from PyQt5.QtTest import QTest
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QHBoxLayout, QSlider, QWidget, QAction, QApplication, QFileDialog, QLabel, QMainWindow, QMenu, QMessageBox, QScrollArea, QSizePolicy, QStatusBar, QVBoxLayout, QDockWidget, QPushButton, QStyle, QLineEdit)

from pimsviewer.gui import GUI
from pimsviewer.plugins import Plugin, ProcessingPlugin

class PluginsTest(unittest.TestCase):
    def test_process_function(self):
        app = QApplication(sys.argv)
        gui = GUI(extra_plugins=[ProcessingPlugin])
        
        self.assertTrue(len(gui.plugins) > 0)

        has_processing_plugin = False
        for p in gui.plugins:
            if isinstance(p, ProcessingPlugin):
                has_processing_plugin = True

        self.assertTrue(has_processing_plugin)

if __name__ == "__main__":
    unittest.main()

