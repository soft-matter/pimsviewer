import sys
from PyQt5.QtWidgets import QApplication

import unittest

from pimsviewer.gui import GUI
from pimsviewer.example_plugins import ProcessingPlugin, AnnotatePlugin

class PluginsTest(unittest.TestCase):
    def test_add_plugins(self):
        app = QApplication(sys.argv)
        gui = GUI(extra_plugins=[ProcessingPlugin, AnnotatePlugin])
        
        self.assertTrue(len(gui.plugins) > 1)

        has_processing_plugin = False
        has_annotate_plugin = False
        for p in gui.plugins:
            if isinstance(p, ProcessingPlugin):
                has_processing_plugin = True
            if isinstance(p, AnnotatePlugin):
                has_annotate_plugin = True

        self.assertTrue(has_processing_plugin)
        self.assertTrue(has_annotate_plugin)
        gui.close()
        app.exit()

if __name__ == "__main__":
    unittest.main()
