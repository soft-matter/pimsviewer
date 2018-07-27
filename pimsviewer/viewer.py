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

        # 5: Program specific code
        self.filename = filename
        self.figure, self.ax = self.create_figure()
        self.canvas = builder.get_object('Canvas_1')
        self.photo = None
        self.reader = None

        # 6: sliders
        self._slider_job = None
        self.slider_frame = self.builder.get_object('SliderFrame')
        self.sliders = {}
        self.configure_sliders()

        # 7: Connect callback functions
        builder.connect_callbacks(self)
        self.mainwindow.bind("<Configure>", self.resize)
        self.set_accelerators()

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
            if len(self.filename) == 0:
                return
        self.reader = pims.open(self.filename)
        self.show_frame()
        self.update_statusbar()
        self.init_sliders()

    def show_frame(self):
        frame_no = self.sliders['t']['current'] - 1
        channel_no = self.sliders['c']['current'] - 1

        if not hasattr(self.reader, 'sizes'):
            self.reader.sizes = {}
        if 'c' in self.reader.sizes:
            self.reader.bundle_axes = 'cyx'
            self.ax.imshow(self.reader[frame_no][channel_no])
        else:
            self.ax.imshow(self.reader[frame_no])
        self.draw_figure()

    def on_slider_change(self, event=None):
        if self._slider_job:
            self.mainwindow.after_cancel(self._slider_job)
        self._slider_job = self.mainwindow.after(200, self._on_slider_change)

    def _on_slider_change(self):
        for prop in self.sliders.keys():
            if prop in self.reader.sizes and self.reader.sizes[prop] > 1:
                value = int(round(self.sliders[prop]['slider'].get()))
                if value != self.sliders[prop]['current']:
                    self.sliders[prop]['value_label'].configure(text='%d/%d' % (value, self.reader.sizes[prop]))
                    self.sliders[prop]['value_label'].update()
                    self.sliders[prop]['current'] = value
        
        self.show_frame()
        self._slider_job = None

    def init_sliders(self):
        if self.reader is None:
            self.hide_all_sliders()

        if not hasattr(self.reader, 'sizes'):
            self.hide_all_sliders()

        for prop in self.sliders.keys():
            if prop not in self.reader.sizes or self.reader.sizes[prop] <= 1:
                self.sliders[prop]['frame'].grid_remove()
                self.sliders[prop]['frame'].update()
            else:
                self.sliders[prop]['frame'].grid()
                self.sliders[prop]['frame'].update()
                self.sliders[prop]['value_label'].configure(text='%d/%d' % (1, self.reader.sizes[prop]))
                self.sliders[prop]['value_label'].update()
                self.sliders[prop]['slider'].configure(from_=1, to=self.reader.sizes[prop])
                self.sliders[prop]['slider'].update()

    def hide_all_sliders(self):
        for prop in self.sliders.keys():
            self.sliders[prop]['frame'].grid_remove()

    def configure_sliders(self):
        self.sliders['c'] = {
                'frame': self.builder.get_object('ChannelFrame', self.slider_frame),
                'value_label': self.builder.get_object('ChannelValue'),
                'play_btn': self.builder.get_object('ChannelPlayBtn'),
                'slider': self.builder.get_object('ChannelScale'),
                'current': 1
        }

        self.sliders['t'] = {
                'frame': self.builder.get_object('TimeFrame', self.slider_frame),
                'value_label': self.builder.get_object('TimeValue'),
                'play_btn': self.builder.get_object('TimePlayBtn'),
                'slider': self.builder.get_object('TimeScale'),
                'current': 1
        }

        self.sliders['z'] = {
                'frame': self.builder.get_object('ZFrame', self.slider_frame),
                'value_label': self.builder.get_object('ZValue'),
                'play_btn': self.builder.get_object('ZPlayBtn'),
                'slider': self.builder.get_object('ZScale'),
                'current': 1
        }

        self.hide_all_sliders()

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

