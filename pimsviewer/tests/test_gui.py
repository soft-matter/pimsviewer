import sys
import unittest
from PyQt5.QtTest import QTest
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from pimsviewer.gui import GUI

class GuiTest(unittest.TestCase):
    app = None
    qapp = None

    def setUp(self):
        self.qapp = QApplication(sys.argv)
        self.app = GUI()

    def tearDown(self):
        self.app.close()
        self.qapp.exit()

    def test_init(self):
        self.assertEqual(self.app.windowTitle(), self.app.name)

if __name__ == "__main__":
    unittest.main()
