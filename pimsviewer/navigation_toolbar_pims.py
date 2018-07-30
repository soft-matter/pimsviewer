try:
    import tkinter as Tk
except ImportError: # Python 2
    import Tkinter as Tk

import os
from matplotlib import rcParams
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk
from matplotlib.backends._backend_tk import ToolTip
from matplotlib.widgets import SubplotTool

class NavigationToolbarPims(NavigationToolbar2Tk):
    def __init__(self, canvas, window, message_parent):
        self._message_parent = message_parent
        NavigationToolbar2Tk.__init__(self, canvas, window)

    def _init_toolbar(self):
        xmin, xmax = self.canvas.figure.bbox.intervalx
        height, width = 50, xmax-xmin
        Tk.Frame.__init__(self, master=self.window,
                          width=int(width), height=int(height),
                          borderwidth=2)

        self.update()  # Make axes menu

        for text, tooltip_text, image_file, callback in self.toolitems:
            if text is None:
                # Add a spacer; return value is unused.
                self._Spacer()
            else:
                button = self._Button(text=text, file=image_file,
                                      command=getattr(self, callback))
                if tooltip_text is not None:
                    ToolTip.createToolTip(button, tooltip_text)

        self.message = Tk.StringVar(master=self._message_parent)
        self._message_label = Tk.Label(master=self._message_parent, textvariable=self.message, width=40, anchor=Tk.W)

    def get_message_label(self):
        return self._message_label
