import os
try:
    import tkinter as tk
except:
    import Tkinter as tk
import pygubu
from tkinter.filedialog import askopenfilename
import matplotlib as mpl
import matplotlib.backends.tkagg as tkagg
from matplotlib.backends.backend_agg import FigureCanvasAgg
import pims

from nd2reader import ND2Reader

CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
dpi = 300

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

        self.statusbar = builder.get_object('StatusBar')

        # 5: Connect callback functions
        builder.connect_callbacks(self)
        self.mainwindow.bind("<Configure>", self.resize)
        self.set_accelerators()

        # 6: Program specific code
        self.filename = filename
        self.figure, self.ax = self.create_figure()
        self.canvas = builder.get_object('Canvas_1')
        self.photo = None
        self.reader = None

        # 7: sliders
        self.frame_scale = self.builder.get_object('ScaleFrame')
        self.frame_scale_label = self.builder.get_object('ScaleFrameLabel')
        self.frame_scale.configure(command=self.change_frame_and_channel)
        self.frame_scale.update()
        self._job_frame = None
        self.channel_scale = self.builder.get_object('ScaleColor')
        self.channel_scale_label = self.builder.get_object('ScaleColorLabel')
        self.channel_scale.configure(command=self.change_frame_and_channel)
        self.channel_scale.update()
        self._job_channel = None

        if self.filename is not None:
            self.open_file()

    def create_figure(self):
        fig = mpl.figure.Figure(figsize=(200/dpi, 200/dpi), dpi=dpi)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.axis('off')
        return fig, ax

    def quit(self, event=None):
        self.mainwindow.quit()

    def run(self):
        self.mainwindow.mainloop()

    def open_file(self, event=None):
        if event is not None:
            self.filename = askopenfilename()
        self.reader = pims.open(self.filename)
        self.show_frame()
        self.update_statusbar()
        self.update_controls()

    def show_frame(self, frame_no=0, channel_no=0):
        if 'c' in self.reader.sizes:
            self.reader.bundle_axes = 'cyx'
            self.ax.imshow(self.reader[frame_no][channel_no])
        else:
            self.ax.imshow(self.reader[frame_no])
        self.draw_figure()

    def update_controls(self):
        sizes = self.reader.sizes
        if 't' in sizes:
            self.frame_scale.configure(from_=0, to=sizes['t']-1, value=0)
        if 'c' in sizes:
            self.channel_scale.configure(from_=0, to=sizes['c']-1, value=0)

        self._change_frame_and_channel()

    def change_frame_and_channel(self, event=None):
        if self._job:
            self.mainwindow.after_cancel(self._job)
        self._job = self.mainwindow.after(200, self._change_frame_and_channel)

    def _change_frame_and_channel(self):
        frame_no = round(self.frame_scale.get())
        channel_no = round(self.channel_scale.get())
        self.show_frame(frame_no=frame_no, channel_no=channel_no)
        self.frame_scale_label.configure(text='Frame %d/%d' % (frame_no+1, self.reader.sizes['t']))
        self.frame_scale_label.update()
        self.channel_scale_label.configure(text='Channel %d/%d' % (channel_no+1, self.reader.sizes['c']))
        self.channel_scale_label.update()
        self._job = None

    def update_statusbar(self):
        if self.filename is not None:
            text = 'Current file: "%s"' % self.filename
        else:
            text = 'Ready'

        self.statusbar.configure(text=text)
        self.statusbar.update()

    def draw_figure(self):
        cpw = self.canvas.winfo_width()
        cph = self.canvas.winfo_height()
        self.figure.set_size_inches(cpw/dpi, cph/dpi, forward=True)
        figure_canvas_agg = FigureCanvasAgg(self.figure)
        figure_canvas_agg.draw()
        figure_x, figure_y, figure_w, figure_h = self.figure.bbox.bounds
        figure_w, figure_h = int(figure_w), int(figure_h)
        self.photo = tk.PhotoImage(master=self.canvas, width=figure_w, height=figure_h)

        self.canvas.create_image(figure_w/2, figure_h/2, image=self.photo)
        tkagg.blit(self.photo, figure_canvas_agg.get_renderer()._renderer, colormode=2)

    def set_accelerators(self):
        self.mainwindow.bind_all("<Control-q>", self.quit)
        self.mainwindow.bind_all("<Control-o>", self.open_file)

    def resize(self, event=None):
        self.draw_figure()

