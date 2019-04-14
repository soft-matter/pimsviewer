import sys
import unittest
from PyQt5.QtTest import QTest
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from pimsviewer.gui import GUI

class GuiTest(unittest.TestCase):
    def setUp(self):
        app = QApplication(sys.argv)
        gui = GUI()

        self.app = gui

    def test_init(self):
        self.assertEqual(self.app.windowTitle(), self.app.name)

if __name__ == "__main__":
    unittest.main()
