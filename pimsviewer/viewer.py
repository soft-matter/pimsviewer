import os
try:
    import tkinter as tk
except:
    import Tkinter as tk
import pygubu
from tkinter.filedialog import askopenfilename

CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))

class Viewer:
    def __init__(self, filename, reader_class):
        # 1: Create a builder
        self.builder = builder = pygubu.Builder()

        # 2: Load an ui file
        builder.add_from_file(os.path.join(CURRENT_DIR, 'interface.ui'))
        
        # 3: Create the toplevel widget.
        self.mainwindow = builder.get_object('Toplevel_1')
        self.frame = builder.get_object('Frame_1')
        self.frame.pack(fill=tk.BOTH, expand=True)

        # 4: Set main menu
        self.mainmenu = menu = builder.get_object('Menu_1', self.mainwindow)
        self.mainwindow.config(menu=menu)

        # 5: Connect callback functions
        builder.connect_callbacks(self)
        self.set_accelerators()

        # 6: Program specific code
        self.filename = None

    def quit(self, event=None):
        self.mainwindow.quit()

    def run(self):
        self.mainwindow.mainloop()

    def open_file(self, event=None):
        self.filename = askopenfilename()

    def set_accelerators(self):
        pass

